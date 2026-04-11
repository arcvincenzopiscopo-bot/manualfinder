"""
Indicizzazione e gestione del corpus normativo in ChromaDB.

Modello: paraphrase-multilingual-MiniLM-L12-v2 (stesso modello per indicizzazione e query).
Questo elimina il rischio di mismatch embedding e mantiene RAM < 150MB su Render.

Cartelle corpus:
  - Primaria:    corpus/raw/   (normativa EU + quaderni extra)
  - Secondaria:  pdf manuali/  (le 22 schede INAIL esistenti — scansionate automaticamente)
  - ChromaDB:    corpus/chroma_db/
  - Su Render:   /opt/render/project/data/corpus_raw/ + /opt/render/project/data/chroma_db/

La cartella "pdf manuali/" è già presente nel progetto con le 22 schede INAIL.
Viene inclusa automaticamente nel corpus — l'utente non deve copiare i PDF.
Per la Direttiva Macchine e altri documenti normativi: corpus/raw/normativa/
"""
import os
import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Path resolution ──────────────────────────────────────────────────────────
_IS_RENDER = bool(os.environ.get("RENDER"))

if _IS_RENDER:
    CHROMA_PATH = "/opt/render/project/data/chroma_db"
    CORPUS_PATH = "/opt/render/project/data/corpus_raw"
    # Su Render i PDF INAIL sono inclusi nel deploy (gittracked)
    _HERE_RENDER = Path(__file__).parent  # backend/app/services/
    _PROJECT_ROOT_RENDER = _HERE_RENDER.parent.parent.parent  # manualfinder/
    PDF_MANUALI_PATH = str(_PROJECT_ROOT_RENDER / "pdf manuali")
else:
    _HERE = Path(__file__).parent  # backend/app/services/
    _PROJECT_ROOT = _HERE.parent.parent.parent  # manualfinder/
    CHROMA_PATH = str(_PROJECT_ROOT / "corpus" / "chroma_db")
    CORPUS_PATH = str(_PROJECT_ROOT / "corpus" / "raw")
    # Cartella esistente con le 22 schede INAIL (git-tracked)
    PDF_MANUALI_PATH = str(_PROJECT_ROOT / "pdf manuali")

# Modello unico per indicizzazione e query — zero mismatch
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

COLLECTION_NAME = "corpus_normativo"

# ─── Manifest fonti note ──────────────────────────────────────────────────────
# Mappatura filename → metadati. Per i quaderni INAIL la fonte viene
# estratta dal nome del file automaticamente se non in questo manifest.
CORPUS_MANIFEST: dict = {
    "direttiva_macchine_2006_42.pdf": {
        "fonte": "Direttiva Macchine 2006/42/CE",
        "tipo": "normativa_EU",
        "valid_until": "2027-01-19",
    },
    # Regolamento 2023/1230/UE — STANDBY fino al 20/01/2027
    # "regolamento_macchine_2023_1230.pdf": {
    #     "fonte": "Regolamento Macchine 2023/1230/UE",
    #     "tipo": "normativa_EU",
    #     "valid_from": "2027-01-20",
    # },
}


# ─── Client ChromaDB (lazy, con graceful failure) ─────────────────────────────

def _is_available() -> bool:
    """Verifica se chromadb e sentence-transformers sono installati."""
    try:
        import chromadb  # noqa: F401
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def get_chroma_client():
    """Ritorna un PersistentClient ChromaDB. Raises ImportError se non disponibile."""
    import chromadb
    os.makedirs(CHROMA_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_PATH)


def get_collection(model: str = EMBEDDING_MODEL):
    """
    Ritorna (o crea) la collection ChromaDB con la funzione di embedding specificata.
    Ritorna None se chromadb non è disponibile.
    """
    if not _is_available():
        return None
    try:
        from chromadb.utils import embedding_functions
        client = get_chroma_client()
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model
        )
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        logger.warning("ChromaDB collection non disponibile: %s", e)
        return None


# ─── Estrazione testo PDF ─────────────────────────────────────────────────────

def _pdf_to_pages(pdf_path: str) -> list[dict]:
    """
    Estrae il testo di ogni pagina da un PDF.
    Usa fitz (PyMuPDF) — già dipendenza del progetto.
    """
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            pages.append({"text": text, "page": i + 1})
    doc.close()
    return pages


def _file_hash(path: str) -> str:
    """SHA-256 del file per skip duplicati."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _filename_to_fonte(filename: str) -> str:
    """Estrae un nome leggibile dal filename del quaderno INAIL."""
    name = filename.replace(".pdf", "").replace("_", " ")
    # "Scheda 6 - ESCAVATORE IDRAULICO" → "Quaderno INAIL — Escavatore Idraulico"
    if " - " in name:
        parts = name.split(" - ", 1)
        categoria = parts[1].title()
        return f"Quaderno INAIL — {categoria}"
    return f"Quaderno INAIL — {name.title()}"


# ─── Indicizzazione ───────────────────────────────────────────────────────────

def index_document(
    pdf_path: str,
    metadata_override: Optional[dict] = None,
    model: str = EMBEDDING_MODEL,
    progress_callback=None,
) -> dict:
    """
    Indicizza un singolo PDF nel corpus ChromaDB.

    Args:
        pdf_path: path assoluto al PDF
        metadata_override: override metadati (fonte, tipo, ecc.)
        model: modello embedding (default EMBEDDING_MODEL)
        progress_callback: callable(msg: str) per UI progress

    Returns:
        dict: {chunks, skipped, reason?}
    """
    collection = get_collection(model=model)
    if collection is None:
        return {"chunks": 0, "skipped": True, "reason": "chromadb non disponibile"}

    filename = os.path.basename(pdf_path)
    if progress_callback:
        progress_callback(f"Calcolo hash: {filename}")

    file_hash = _file_hash(pdf_path)

    # Skip se già indicizzato con stesso hash
    try:
        existing = collection.get(where={"file_hash": file_hash}, limit=1)
        if existing["ids"]:
            return {"chunks": 0, "skipped": True, "reason": "già indicizzato (hash identico)"}
    except Exception:
        pass

    # Rimuovi versione precedente se esiste con hash diverso
    try:
        collection.delete(where={"filename": filename})
    except Exception:
        pass

    # Metadati fonte
    base_meta = CORPUS_MANIFEST.get(filename, {
        "fonte": _filename_to_fonte(filename),
        "tipo": "quaderno_inail",
    })
    if metadata_override:
        base_meta.update(metadata_override)

    # Estrazione testo
    if progress_callback:
        progress_callback(f"Estrazione testo: {filename}")
    try:
        pages = _pdf_to_pages(pdf_path)
    except Exception as e:
        return {"chunks": 0, "skipped": True, "reason": f"errore lettura PDF: {e}"}

    if not pages:
        return {"chunks": 0, "skipped": True, "reason": "PDF senza testo estraibile"}

    full_text = "\n".join(f"[PAG {p['page']}] {p['text']}" for p in pages)

    # Chunking
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=60,
            separators=["\n\n", "\n", "Art.", "Articolo", "Allegato", ". "],
        )
        chunks = splitter.split_text(full_text)
    except ImportError:
        # Fallback chunking semplice se langchain non disponibile
        chunks = [full_text[i:i+400] for i in range(0, len(full_text), 340)]

    if not chunks:
        return {"chunks": 0, "skipped": True, "reason": "nessun chunk prodotto"}

    # Inserimento in batch
    if progress_callback:
        progress_callback(f"Calcolo embeddings ({len(chunks)} chunk): {filename}")

    ids, texts, metadatas = [], [], []
    for i, chunk in enumerate(chunks):
        ids.append(f"{file_hash}_{i}")
        texts.append(chunk)
        metadatas.append({
            **base_meta,
            "filename": filename,
            "file_hash": file_hash,
            "chunk_index": i,
        })

    BATCH = 100
    try:
        for start in range(0, len(ids), BATCH):
            collection.add(
                ids=ids[start:start + BATCH],
                documents=texts[start:start + BATCH],
                metadatas=metadatas[start:start + BATCH],
            )
    except Exception as e:
        return {"chunks": 0, "skipped": True, "reason": f"errore inserimento: {e}"}

    logger.info("Indicizzato %s: %d chunk (fonte: %s)", filename, len(chunks), base_meta.get("fonte"))
    return {"chunks": len(chunks), "skipped": False}


def index_all_corpus(
    model: str = EMBEDDING_MODEL,
    progress_callback=None,
) -> dict:
    """
    Indicizza tutti i PDF da due sorgenti:
    1. corpus/raw/           — normativa EU + quaderni extra aggiunti dall'utente
    2. pdf manuali/          — le 22 schede INAIL esistenti (git-tracked, già presenti)

    Salta i file già indicizzati con hash identico.
    """
    results = {}

    # Raccogli PDF da tutte le sorgenti disponibili
    pdf_files: list[tuple[str, dict]] = []  # (path, metadata_override)

    # Sorgente 1: corpus/raw/ (normativa EU + extra)
    if os.path.exists(CORPUS_PATH):
        for root, _, files in os.walk(CORPUS_PATH):
            for filename in files:
                if filename.lower().endswith(".pdf"):
                    # Determina tipo in base alla sottocartella
                    rel = os.path.relpath(root, CORPUS_PATH)
                    tipo = "normativa_EU" if "normativa" in rel.lower() else "quaderno_inail"
                    pdf_files.append((os.path.join(root, filename), {"tipo": tipo}))
    else:
        logger.info("corpus/raw/ non trovato, uso solo pdf manuali/")

    # Sorgente 2: pdf manuali/ (schede INAIL già presenti nel progetto)
    if os.path.exists(PDF_MANUALI_PATH):
        for root, _, files in os.walk(PDF_MANUALI_PATH):
            for filename in files:
                if filename.lower().endswith(".pdf"):
                    full_path = os.path.join(root, filename)
                    # Non reindicizzare se già trovato in corpus/raw/
                    already = any(os.path.basename(p) == filename for p, _ in pdf_files)
                    if not already:
                        pdf_files.append((full_path, {"tipo": "quaderno_inail"}))
    else:
        logger.debug("pdf manuali/ non trovato: %s", PDF_MANUALI_PATH)

    if not pdf_files:
        logger.warning("Nessun PDF trovato in corpus/raw/ né in pdf manuali/")
        return results

    if progress_callback:
        progress_callback(f"Trovati {len(pdf_files)} PDF da esaminare")

    for path, meta_override in pdf_files:
        filename = os.path.basename(path)
        results[filename] = index_document(
            path,
            metadata_override=meta_override,
            model=model,
            progress_callback=progress_callback,
        )

    return results


# ─── Statistiche ─────────────────────────────────────────────────────────────

def get_index_stats() -> dict:
    """
    Statistiche del corpus indicizzato.
    Ritorna struttura valida anche se ChromaDB non disponibile.
    """
    if not _is_available():
        return {"total_chunks": 0, "fonti": [], "available": False}

    collection = get_collection()
    if collection is None:
        return {"total_chunks": 0, "fonti": [], "available": False}

    try:
        count = collection.count()
        if count == 0:
            return {"total_chunks": 0, "fonti": [], "available": True}

        all_meta = collection.get(include=["metadatas"])
        fonti_seen = {}
        for m in (all_meta.get("metadatas") or []):
            fonte = m.get("fonte", "sconosciuta")
            filename = m.get("filename", "")
            if fonte not in fonti_seen:
                fonti_seen[fonte] = {"fonte": fonte, "filename": filename, "tipo": m.get("tipo", "")}

        return {
            "total_chunks": count,
            "fonti": list(fonti_seen.values()),
            "available": True,
        }
    except Exception as e:
        logger.warning("Errore get_index_stats: %s", e)
        return {"total_chunks": 0, "fonti": [], "available": False, "error": str(e)}


def is_corpus_available() -> bool:
    """True se ChromaDB è disponibile e non vuoto."""
    if not _is_available():
        return False
    collection = get_collection()
    if collection is None:
        return False
    try:
        return collection.count() > 0
    except Exception:
        return False


def cleanup_orphaned_documents() -> dict:
    """
    Rimuove da ChromaDB i chunk di file che non esistono più su disco.

    Scansiona tutti i metadati nella collection e confronta il campo 'filepath'
    con i file presenti in CORPUS_PATH e PDF_MANUALI_PATH. I chunk di file non
    più presenti vengono eliminati.

    Ritorna { "removed_files": [...], "removed_chunks": int, "error": str|None }
    """
    collection = get_collection()
    if collection is None:
        return {"removed_files": [], "removed_chunks": 0, "error": "ChromaDB non disponibile"}

    try:
        all_data = collection.get(include=["metadatas", "ids"])
        metadatas = all_data.get("metadatas") or []
        ids = all_data.get("ids") or []
    except Exception as e:
        return {"removed_files": [], "removed_chunks": 0, "error": str(e)}

    # Raggruppa gli ID per filepath
    filepath_to_ids: dict[str, list[str]] = {}
    for meta, chunk_id in zip(metadatas, ids):
        fp = meta.get("filepath", "")
        if fp:
            filepath_to_ids.setdefault(fp, []).append(chunk_id)

    # Determina quali filepath non esistono più su disco
    removed_files = []
    ids_to_delete: list[str] = []
    for filepath, chunk_ids in filepath_to_ids.items():
        if not os.path.exists(filepath):
            removed_files.append(filepath)
            ids_to_delete.extend(chunk_ids)

    if not ids_to_delete:
        logger.info("corpus_indexer.cleanup_orphaned: nessun chunk orfano trovato")
        return {"removed_files": [], "removed_chunks": 0, "error": None}

    try:
        # ChromaDB limita il batch delete a ~41000 id per volta
        BATCH = 5000
        for i in range(0, len(ids_to_delete), BATCH):
            collection.delete(ids=ids_to_delete[i:i + BATCH])
        logger.info(
            "corpus_indexer.cleanup_orphaned: rimossi %d chunk da %d file eliminati",
            len(ids_to_delete), len(removed_files),
        )
        return {"removed_files": removed_files, "removed_chunks": len(ids_to_delete), "error": None}
    except Exception as e:
        logger.error("corpus_indexer.cleanup_orphaned: errore delete: %s", e)
        return {"removed_files": [], "removed_chunks": 0, "error": str(e)}
