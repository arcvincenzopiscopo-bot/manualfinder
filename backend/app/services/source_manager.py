"""
Source Manager: determina la strategia di analisi A–F in base alle fonti disponibili.

Strategia:
  A — Manuale specifico produttore (senza INAIL)
  B — Manuale produttore + scheda INAIL (best case)
  C — Manuale di categoria + scheda INAIL
  D — Solo manuale di categoria
  E — Solo scheda INAIL (senza manuale produttore)
  F — AI inference (nessun documento disponibile)
"""
from dataclasses import dataclass
from typing import Optional

from app.services import config_service

# ── Fallback statici (usati se DB non disponibile) ───────────────────────────
_FB_BADGE_LABELS = {"A":"Manuale produttore","B":"Manuale produttore + INAIL",
                    "C":"Manuale categoria + INAIL","D":"Manuale categoria",
                    "E":"Quaderno INAIL","E_local":"Quaderno INAIL Locale","F":"AI inference"}
_FB_BADGE_COLORS = {"A":"#16a34a","B":"#16a34a","C":"#d97706",
                    "D":"#d97706","E":"#0369a1","E_local":"#0369a1","F":"#dc2626"}
_FB_AFFIDABILITA = {"A":95,"B":90,"C":65,"D":55,"E":70,"E_local":82,"F":30}
_FB_FONTE_TIPO   = {"A":"pdf","B":"inail+produttore","C":"inail+produttore",
                    "D":"pdf","E":"inail","E_local":"inail","F":"fallback_ai"}
_FB_DISCLAIMERS  = {
    "A":"","B":"",
    "C":"Manuale specifico del produttore non disponibile. Analisi basata su manuale di categoria e quaderno INAIL. Verificare i dati tecnici specifici direttamente sulla macchina.",
    "D":"Manuale specifico e quaderno INAIL non disponibili. Analisi basata su manuale di categoria. Le prescrizioni normative devono essere verificate in campo.",
    "E":"Manuale del produttore non disponibile. Dati tecnici operativi basati su quaderno INAIL. Verificare i componenti specifici direttamente in campo.",
    "E_local":"Quaderno INAIL locale prevalidato disponibile. Manuale del produttore non disponibile: i dati tecnici specifici di questo modello devono essere verificati direttamente in campo.",
    "F_no_rag":"Nessuna fonte documentale disponibile per questa macchina. La scheda è generata interamente da AI sulla base della categoria macchina. Tutti i dati tecnici devono essere verificati direttamente in campo. Non utilizzare le prescrizioni senza verifica.",
    "F_rag":"Nessun PDF disponibile per questa macchina. La scheda è generata da AI supportata dal corpus normativo indicizzato (D.Lgs. 81/08 + quaderni INAIL). I dati tecnici specifici devono comunque essere verificati in campo.",
    "F":"Nessuna fonte documentale disponibile per questa macchina. La scheda è generata da AI sulla base della categoria macchina e del corpus normativo. Tutti i dati tecnici devono essere verificati direttamente in campo. Non utilizzare le prescrizioni senza verifica.",
}


def _badge_labels() -> dict:  return config_service.get_map("badge_labels", _FB_BADGE_LABELS)
def _badge_colors() -> dict:  return config_service.get_map("badge_colors", _FB_BADGE_COLORS)
def _affidabilita() -> dict:  return config_service.get_map("affidabilita", _FB_AFFIDABILITA)
def _fonte_tipo()   -> dict:  return config_service.get_map("fonte_tipo",   _FB_FONTE_TIPO)
def _disclaimers()  -> dict:  return config_service.get_map("disclaimers",  _FB_DISCLAIMERS)


@dataclass
class SourceContext:
    strategy: str                  # 'A'..'F'
    badge_label: str
    badge_color: str
    disclaimer: str
    affidabilita: int              # 0-100
    fonte_tipo: str                # backward compat con SafetyCard.fonte_tipo
    inail_is_local: bool           # True se il PDF INAIL viene dalla cartella locale (prevalidato admin)
    rag_has_inail: bool            # True se nel corpus RAG ci sono chunk di quaderni INAIL per questo tipo
    similar_category_local: bool = False  # True se il manuale produttore è un PDF locale di categoria simile


def resolve_sources(
    inail_bytes: Optional[bytes],
    producer_bytes: Optional[bytes],
    producer_source_label: Optional[str] = None,
    inail_url: Optional[str] = None,
    rag_has_inail: bool = False,
    similar_category_local: bool = False,
) -> SourceContext:
    """
    Determina la strategia A–F in base alle fonti disponibili.

    Args:
        inail_bytes:            bytes della scheda INAIL (None se non disponibile)
        producer_bytes:         bytes del manuale produttore (None se non disponibile)
        producer_source_label:  etichetta fonte produttore — se contiene "categoria"
                                indica un manuale di categoria simile (non specifico)
        inail_url:              URL/path della fonte INAIL; se inizia con "/manuals/local/"
                                è un quaderno prevalidato dall'admin
        rag_has_inail:          True se il corpus RAG contiene chunk di quaderni INAIL
                                per questo tipo macchina
        similar_category_local: True se il manuale "produttore" è in realtà un PDF locale
                                di categoria simile (fallback locale)
    """
    is_category = "categoria" in (producer_source_label or "").lower()
    has_inail = inail_bytes is not None
    has_producer = producer_bytes is not None
    inail_is_local = bool(inail_url and inail_url.startswith("/manuals/local/"))

    if has_producer and has_inail and not is_category:
        strategy = "B"
    elif has_producer and not is_category:
        strategy = "A"
    elif has_producer and has_inail and is_category:
        strategy = "C"
    elif has_producer and is_category:
        strategy = "D"
    elif has_inail:
        strategy = "E"
    else:
        strategy = "F"

    # Sceglie la variante label/badge/affidabilità per strategia E con INAIL locale:
    # "E_local" ha affidabilità 82 (vs 70 online) e disclaimer dedicato.
    strategy_key = strategy
    if strategy == "E" and inail_is_local:
        strategy_key = "E_local"

    discs = _disclaimers()
    # Disclaimer F dipende dalla disponibilità del corpus RAG
    if strategy == "F":
        disclaimer = discs.get("F_rag") if rag_has_inail else discs.get("F_no_rag")
        disclaimer = disclaimer or discs.get("F", "")
    else:
        disclaimer = discs.get(strategy_key, discs.get(strategy, ""))

    return SourceContext(
        strategy=strategy,
        badge_label=_badge_labels().get(strategy_key, _badge_labels().get(strategy, strategy)),
        badge_color=_badge_colors().get(strategy_key, _badge_colors().get(strategy, "#6b7280")),
        disclaimer=disclaimer,
        affidabilita=_affidabilita().get(strategy_key, _affidabilita().get(strategy, 50)),
        fonte_tipo=_fonte_tipo().get(strategy_key, _fonte_tipo().get(strategy, "")),
        inail_is_local=inail_is_local,
        rag_has_inail=rag_has_inail,
        similar_category_local=similar_category_local,
    )


def source_context_to_dict(ctx: SourceContext) -> dict:
    """Serializza SourceContext in dict per inclusione in SafetyCard.source_metadata."""
    return {
        "strategy": ctx.strategy,
        "badge_label": ctx.badge_label,
        "badge_color": ctx.badge_color,
        "disclaimer": ctx.disclaimer,
        "affidabilita": ctx.affidabilita,
        "fonte_tipo": ctx.fonte_tipo,
        "inail_is_local": ctx.inail_is_local,
        "rag_has_inail": ctx.rag_has_inail,
        "similar_category_local": ctx.similar_category_local,
    }
