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

# ── Labels e colori per badge UI ────────────────────────────────────────────────

_BADGE_LABELS: dict[str, str] = {
    "A": "Manuale produttore",
    "B": "Manuale produttore + INAIL",
    "C": "Manuale categoria + INAIL",
    "D": "Manuale categoria",
    "E": "Quaderno INAIL",
    "F": "AI inference",
}

_BADGE_COLORS: dict[str, str] = {
    "A": "#16a34a",   # verde — manuale specifico, alta affidabilità
    "B": "#16a34a",   # verde — massima affidabilità
    "C": "#d97706",   # arancione — affidabilità media
    "D": "#d97706",   # arancione
    "E": "#0369a1",   # blu — solo normativa INAIL
    "F": "#dc2626",   # rosso — solo AI inference
}

_AFFIDABILITA: dict[str, int] = {
    "A": 95,
    "B": 90,
    "C": 65,
    "D": 55,
    "E": 70,
    "F": 30,
}

# Fonte tipo backward-compat con SafetyCard.fonte_tipo
_FONTE_TIPO: dict[str, str] = {
    "A": "pdf",
    "B": "inail+produttore",
    "C": "inail+produttore",
    "D": "pdf",
    "E": "inail",
    "F": "fallback_ai",
}

_DISCLAIMERS: dict[str, str] = {
    "A": "",
    "B": "",
    "C": (
        "Manuale specifico del produttore non disponibile. "
        "Analisi basata su manuale di categoria e quaderno INAIL. "
        "Verificare i dati tecnici specifici direttamente sulla macchina."
    ),
    "D": (
        "Manuale specifico e quaderno INAIL non disponibili. "
        "Analisi basata su manuale di categoria. "
        "Le prescrizioni normative devono essere verificate in campo."
    ),
    "E": (
        "Manuale del produttore non disponibile. "
        "Dati tecnici operativi basati su quaderno INAIL. "
        "Verificare i componenti specifici direttamente in campo."
    ),
    "F_no_rag": (
        "Nessuna fonte documentale disponibile per questa macchina. "
        "La scheda è generata interamente da AI sulla base della categoria macchina. "
        "Tutti i dati tecnici devono essere verificati direttamente in campo. "
        "Non utilizzare le prescrizioni senza verifica."
    ),
    "F_rag": (
        "Nessun PDF disponibile per questa macchina. "
        "La scheda è generata da AI supportata dal corpus normativo indicizzato "
        "(D.Lgs. 81/08 + quaderni INAIL). "
        "I dati tecnici specifici devono comunque essere verificati in campo."
    ),
    # "F" è un alias dinamico — viene scelto tra F_no_rag e F_rag in resolve_sources()
    "F": (
        "Nessuna fonte documentale disponibile per questa macchina. "
        "La scheda è generata da AI sulla base della categoria macchina e del corpus normativo. "
        "Tutti i dati tecnici devono essere verificati direttamente in campo. "
        "Non utilizzare le prescrizioni senza verifica."
    ),
}


@dataclass
class SourceContext:
    strategy: str         # 'A'..'F'
    badge_label: str
    badge_color: str
    disclaimer: str
    affidabilita: int     # 0-100
    fonte_tipo: str       # backward compat con SafetyCard.fonte_tipo
    inail_is_local: bool  # True se il PDF INAIL viene dalla cartella locale (prevalidato admin)
    rag_has_inail: bool   # True se nel corpus RAG ci sono chunk di quaderni INAIL per questo tipo


def resolve_sources(
    inail_bytes: Optional[bytes],
    producer_bytes: Optional[bytes],
    producer_source_label: Optional[str] = None,
    inail_url: Optional[str] = None,
    rag_has_inail: bool = False,
) -> SourceContext:
    """
    Determina la strategia A–F in base alle fonti disponibili.

    Args:
        inail_bytes:           bytes della scheda INAIL (None se non disponibile)
        producer_bytes:        bytes del manuale produttore (None se non disponibile)
        producer_source_label: etichetta fonte produttore — se contiene "categoria"
                               indica un manuale di categoria simile (non specifico)
        inail_url:             URL/path della fonte INAIL; se inizia con "/manuals/local/"
                               è un quaderno prevalidato dall'admin
        rag_has_inail:         True se il corpus RAG contiene chunk di quaderni INAIL
                               per questo tipo macchina
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

    # Disclaimer F dipende dalla disponibilità del corpus RAG
    if strategy == "F":
        disclaimer = _DISCLAIMERS["F_rag"] if rag_has_inail else _DISCLAIMERS["F_no_rag"]
    else:
        disclaimer = _DISCLAIMERS[strategy]

    return SourceContext(
        strategy=strategy,
        badge_label=_BADGE_LABELS[strategy],
        badge_color=_BADGE_COLORS[strategy],
        disclaimer=disclaimer,
        affidabilita=_AFFIDABILITA[strategy],
        fonte_tipo=_FONTE_TIPO[strategy],
        inail_is_local=inail_is_local,
        rag_has_inail=rag_has_inail,
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
    }
