"""
Servizio RAG semantico per il corpus normativo (Direttiva Macchine + Quaderni INAIL).

Retrieval:
- Usa ChromaDB già popolato (indicizzato in locale con GUI o CLI)
- Modello MiniLM per embeddare la query (stesso modello usato per indicizzazione)
- Fallback silenzioso: se DB vuoto o non disponibile → lista vuota, nessun crash

Non sostituisce l'analisi del PDF manuale produttore — aggiunge solo
contesto normativo al prompt dell'AI.
"""
import logging
from typing import Optional

from app.services.corpus_indexer import get_collection, is_corpus_available, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Cache singleton della collection (evita reload ad ogni chiamata)
_collection_cache = None


def _get_collection():
    global _collection_cache
    if _collection_cache is None:
        _collection_cache = get_collection(model=EMBEDDING_MODEL)
    return _collection_cache


def invalidate_cache():
    """Invalida la cache in memoria — chiamare dopo upload di un nuovo ChromaDB."""
    global _collection_cache
    _collection_cache = None


def retrieve_normative_context(
    machine_type: str,
    query_aspects: Optional[list[str]] = None,
    n_results: int = 8,
) -> list[dict]:
    """
    Recupera chunk normativi rilevanti per un tipo di macchina dal corpus ChromaDB.

    Args:
        machine_type: tipo macchina (es. "escavatore idraulico")
        query_aspects: aspetti aggiuntivi da cercare (rischi, dispositivi, ecc.)
        n_results: numero massimo di chunk per query

    Returns:
        Lista di dict: [{text, fonte, tipo, filename}]
        Lista vuota se corpus non disponibile o non pertinente.
    """
    collection = _get_collection()
    if collection is None:
        return []

    try:
        count = collection.count()
    except Exception:
        return []

    if count == 0:
        return []

    # Query multiple per coprire diversi aspetti
    queries = [f"sicurezza {machine_type}"]
    if query_aspects:
        queries += [f"{aspect} {machine_type}" for aspect in query_aspects]

    seen_ids: set = set()
    chunks: list[dict] = []

    for query in queries:
        try:
            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning("RAG query fallita ('%s'): %s", query, e)
            continue

        for doc, meta, dist in zip(
            results.get("documents", [[]])[0],
            results.get("metadatas", [[]])[0],
            results.get("distances", [[]])[0],
        ):
            chunk_id = meta.get("file_hash", "") + str(meta.get("chunk_index", ""))
            # Deduplicazione + soglia rilevanza coseno (< 0.5 = abbastanza simile)
            if chunk_id not in seen_ids and dist < 0.5:
                seen_ids.add(chunk_id)
                chunks.append({
                    "text": doc,
                    "fonte": meta.get("fonte", ""),
                    "tipo": meta.get("tipo", ""),
                    "filename": meta.get("filename", ""),
                    "distance": dist,
                })

    # Ordina per tipo: normativa EU prima, poi nazionale, poi quaderni INAIL
    priority = {"normativa_EU": 0, "legge_nazionale": 1, "quaderno_inail": 2}
    chunks.sort(key=lambda c: (priority.get(c["tipo"], 9), c.get("distance", 1.0)))

    # Rimuovi il campo distance dall'output (interno)
    for chunk in chunks:
        chunk.pop("distance", None)

    logger.debug(
        "RAG retrieve: macchina='%s', query=%d, chunks=%d (corpus: %d)",
        machine_type, len(queries), len(chunks), count
    )
    return chunks


def format_context_for_prompt(chunks: list[dict]) -> str:
    """
    Formatta i chunk RAG come blocco testo per il prompt AI.
    Ritorna stringa vuota se non ci sono chunk.
    """
    if not chunks:
        return ""
    lines = ["## ESTRATTI NORMATIVI DISPONIBILI (Direttiva Macchine + Quaderni INAIL)\n"]
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[{i}] FONTE: {chunk['fonte']}")
        lines.append(chunk["text"])
        lines.append("")
    lines.append(
        "ISTRUZIONE VINCOLANTE: Usa ESCLUSIVAMENTE questi estratti per i riferimenti "
        "alla Direttiva Macchine e ai Quaderni INAIL. "
        "Se un rischio non trova copertura negli estratti, scrivi "
        "'riferimento non disponibile nel corpus' invece di inventare. "
        "Non citare articoli della Direttiva Macchine non presenti qui."
    )
    return "\n".join(lines)


def retrieve_for_machine(machine_type: str) -> str:
    """
    Shortcut: recupera e formatta contesto RAG per una macchina.
    Ritorna stringa vuota se corpus non disponibile — fallback silenzioso.
    """
    try:
        chunks = retrieve_normative_context(
            machine_type=machine_type,
            query_aspects=[
                "rischi principali",
                "dispositivi protezione collettiva",
                "verifiche periodiche obbligatorie",
                "requisiti essenziali sicurezza",
                "attrezzature intercambiabili",
                "abilitazione operatore patentino",
            ],
        )
        return format_context_for_prompt(chunks)
    except Exception as e:
        logger.warning("retrieve_for_machine fallback silenzioso: %s", e)
        return ""  # analisi procede senza RAG


def rag_find_inail_filename(machine_name: str, distance_threshold: float = 0.55) -> str | None:
    """
    Cerca nel corpus ChromaDB il quaderno INAIL semanticamente più simile
    al nome della macchina. Ritorna il filename esatto del PDF o None.

    Usato nell'associazione automatica dei quaderni INAIL come passo intermedio
    tra l'alias table (esatta ma limitata) e la chiamata AI (costosa).
    Vantaggi rispetto all'AI:
    - Nessun costo API — puro calcolo locale MiniLM
    - Ritorna direttamente il filename, nessun doppio lookup
    - Capisce sinonimi e famiglie di macchine grazie agli embeddings

    Args:
        machine_name: nome del tipo macchina (es. "escavatore cingolato")
        distance_threshold: distanza coseno massima accettabile (< 1.0; default 0.55)

    Returns:
        Filename del quaderno INAIL (es. "Scheda 6 - ESCAVATORE IDRAULICO.pdf") o None.
    """
    collection = _get_collection()
    if collection is None:
        return None

    try:
        count = collection.count()
        if count == 0:
            return None

        queries = [
            f"attrezzatura da lavoro {machine_name}",
            f"sicurezza {machine_name} cantiere",
        ]

        best_filename: str | None = None
        best_dist = float("inf")

        for query_text in queries:
            try:
                results = collection.query(
                    query_texts=[query_text],
                    n_results=min(5, count),
                    where={"tipo": "quaderno_inail"},
                    include=["metadatas", "distances"],
                )
            except Exception as e:
                logger.warning("rag_find_inail_filename query fallita ('%s'): %s", query_text, e)
                continue

            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]

            for meta, dist in zip(metas, dists):
                if dist < best_dist:
                    best_dist = dist
                    best_filename = meta.get("filename")

        if best_filename and best_dist < distance_threshold:
            logger.debug(
                "rag_find_inail_filename: '%s' → '%s' (dist=%.3f)",
                machine_name, best_filename, best_dist,
            )
            return best_filename

        logger.debug(
            "rag_find_inail_filename: '%s' → nessuna corrispondenza (best_dist=%.3f)",
            machine_name, best_dist if best_dist < float("inf") else -1,
        )
        return None

    except Exception as e:
        logger.warning("rag_find_inail_filename fallback silenzioso: %s", e)
        return None


def get_retrieval_metadata(machine_type: str) -> dict:
    """
    Metadati del retrieval per logging/osservabilità.
    Usato da analysis_service per loggare le fonti usate.
    """
    if not is_corpus_available():
        return {
            "rag_available": False,
            "rag_chunks": 0,
            "rag_sources": [],
        }

    try:
        chunks = retrieve_normative_context(machine_type=machine_type, n_results=5)
        return {
            "rag_available": True,
            "rag_chunks": len(chunks),
            "rag_sources": list({c["fonte"] for c in chunks}),
            "has_direttiva": any(c["tipo"] == "normativa_EU" for c in chunks),
            "has_inail": any(c["tipo"] == "quaderno_inail" for c in chunks),
        }
    except Exception:
        return {
            "rag_available": False,
            "rag_chunks": 0,
            "rag_sources": [],
        }
