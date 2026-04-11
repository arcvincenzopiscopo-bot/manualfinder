"""
Punto unico di ingresso per il contesto normativo dell'analisi.

Combina:
  1. Dizionario D.Lgs 81/08 hardcoded (sempre attivo, zero allucinazioni)
  2. RAG semantico ChromaDB: Direttiva Macchine + Quaderni INAIL (attivo se corpus disponibile)

Il flusso del manuale produttore rimane invariato — questo modulo
aggiunge solo il contesto normativo al prompt, non sostituisce l'analisi del PDF.

Fallback gerarchico:
  dizionario D.Lgs → RAG ChromaDB → stringa vuota (mai crash)
"""
import logging
from typing import Optional

from app.data.riferimenti_normativi import (
    get_riferimenti_per_tipo,
    format_for_prompt as format_dlgs,
)
from app.services.rag_service import retrieve_for_machine, get_retrieval_metadata

logger = logging.getLogger(__name__)


def get_full_normative_context(machine_type: str) -> str:
    """
    Contesto normativo completo per il prompt dell'AI.

    Struttura dell'output:
      [Blocco D.Lgs 81/08 — sempre presente se machine_type non è vuoto]
      ---
      [Blocco RAG Direttiva + INAIL — solo se corpus disponibile]

    Returns:
        Stringa pronta per essere anteposta al prompt, o "" se entrambe vuote.
    """
    # 1. Lookup strutturato D.Lgs 81/08 (zero dipendenze esterne)
    riferimenti = get_riferimenti_per_tipo(machine_type or "")
    dlgs_block = format_dlgs(riferimenti)

    # 2. RAG semantico (fallback silenzioso se corpus vuoto o non disponibile)
    rag_block = ""
    try:
        rag_block = retrieve_for_machine(machine_type or "")
    except Exception as e:
        logger.debug("RAG non disponibile per '%s': %s", machine_type, e)

    blocks = [b for b in [dlgs_block, rag_block] if b]
    if not blocks:
        return ""

    return "\n\n---\n\n".join(blocks)


def get_normative_metadata(machine_type: str) -> dict:
    """
    Metadati sulle fonti normative usate — per logging e osservabilità.
    Usato da analysis_service per includere nei log strutturati.
    """
    riferimenti = get_riferimenti_per_tipo(machine_type or "")
    rag_meta = get_retrieval_metadata(machine_type or "")

    return {
        "machine_type": machine_type,
        "dlgs_refs": len(riferimenti),
        "dlgs_articles": [r["norma"] for r in riferimenti],
        **rag_meta,
    }


def enrich_card_with_sources(card: dict, machine_type: str) -> dict:
    """
    Popola i campi fonte_* della SafetyCard solo se vuoti.
    Non sovrascrive mai ciò che l'AI ha già valorizzato.

    Campi target (già esistenti in responses.py):
      fonte_rischi, fonte_protezione, fonte_raccomandazioni, fonte_residui
    """
    riferimenti = get_riferimenti_per_tipo(machine_type or "")
    has_dlgs = bool(riferimenti)

    has_direttiva = False
    has_inail = False
    try:
        rag_meta = get_retrieval_metadata(machine_type or "")
        has_direttiva = rag_meta.get("has_direttiva", False)
        has_inail = rag_meta.get("has_inail", False)
    except Exception:
        pass

    # Componi etichetta fonti per ciascun campo
    def _build_fonte_label(include_dlgs: bool, include_direttiva: bool, include_inail: bool) -> Optional[str]:
        parts = []
        if include_dlgs:
            parts.append("D.Lgs 81/08")
        if include_direttiva:
            parts.append("Direttiva Macchine 2006/42/CE")
        if include_inail:
            parts.append("Quaderno INAIL")
        return " + ".join(parts) if parts else None

    if not card.get("fonte_rischi"):
        label = _build_fonte_label(has_dlgs, has_direttiva, has_inail)
        if label:
            card["fonte_rischi"] = label

    if not card.get("fonte_protezione"):
        label = _build_fonte_label(has_dlgs, has_direttiva, False)
        if label:
            card["fonte_protezione"] = label

    if not card.get("fonte_raccomandazioni"):
        if has_inail:
            card["fonte_raccomandazioni"] = "Quaderno INAIL"

    if not card.get("fonte_residui") and has_dlgs:
        card["fonte_residui"] = "D.Lgs 81/08"

    return card
