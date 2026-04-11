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
    "E": "Scheda INAIL",
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
        "Analisi basata su manuale di categoria e scheda INAIL. "
        "Verificare i dati tecnici specifici direttamente sulla macchina."
    ),
    "D": (
        "Manuale specifico e scheda INAIL non disponibili. "
        "Analisi basata su manuale di categoria. "
        "Le prescrizioni normative devono essere verificate in campo."
    ),
    "E": (
        "Manuale del produttore non disponibile. "
        "Dati tecnici operativi basati su scheda INAIL. "
        "Verificare i componenti specifici direttamente in campo."
    ),
    "F": (
        "Nessuna fonte documentale disponibile per questa macchina. "
        "La scheda è generata da AI sulla base della categoria macchina e del corpus normativo. "
        "Tutti i dati tecnici devono essere verificati direttamente in campo. "
        "Non utilizzare le prescrizioni senza verifica."
    ),
}


@dataclass
class SourceContext:
    strategy: str       # 'A'..'F'
    badge_label: str
    badge_color: str
    disclaimer: str
    affidabilita: int   # 0-100
    fonte_tipo: str     # backward compat con SafetyCard.fonte_tipo


def resolve_sources(
    inail_bytes: Optional[bytes],
    producer_bytes: Optional[bytes],
    producer_source_label: Optional[str] = None,
) -> SourceContext:
    """
    Determina la strategia A–F in base alle fonti disponibili.

    Args:
        inail_bytes: bytes della scheda INAIL (None se non disponibile)
        producer_bytes: bytes del manuale produttore (None se non disponibile)
        producer_source_label: etichetta fonte produttore — se contiene "categoria"
                               indica un manuale di categoria simile (non specifico)
    """
    is_category = "categoria" in (producer_source_label or "").lower()
    has_inail = inail_bytes is not None
    has_producer = producer_bytes is not None

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

    return SourceContext(
        strategy=strategy,
        badge_label=_BADGE_LABELS[strategy],
        badge_color=_BADGE_COLORS[strategy],
        disclaimer=_DISCLAIMERS[strategy],
        affidabilita=_AFFIDABILITA[strategy],
        fonte_tipo=_FONTE_TIPO[strategy],
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
    }
