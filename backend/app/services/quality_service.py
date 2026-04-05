"""
Quality Logger per ManualFinder.

Valuta ogni scheda di sicurezza generata con regole deterministiche (zero costo AI)
e accumula le criticità in un log in-memory scaricabile via GET /analyze/quality-log.

Obiettivo: raccogliere dati reali di produzione per migliorare prompts e logica
di ricerca in modo sistematico, invece di ottimizzare su singoli casi sintetici.

Il log si azzera al restart del server (Render ephemeral filesystem).
Consultalo periodicamente via: GET https://manualfinder.onrender.com/analyze/quality-log
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# ── Log in-memory ────────────────────────────────────────────────────────────
_quality_log: list[dict] = []
_MAX_LOG_ENTRIES = 500  # evita memory leak su long-running instances


# ── Lookup tables per regole normative ───────────────────────────────────────

# Macchine per cui ci aspettiamo SEMPRE di trovare un manuale produttore reale
_SHOULD_HAVE_MANUAL = {
    "escavatore", "escavatori", "gru mobile", "gru a torre", "gru su autocarro",
    "carrello elevatore", "muletto", "sollevatore telescopico", "telehandler",
    "piattaforma aerea", "ple", "piattaforma elevabile",
    "pompa calcestruzzo", "autobetonpompa",
    "pala caricatrice", "pala meccanica",
    "pressa piegatrice", "piegatrice",
}

# Macchine NON coperte dall'Accordo Stato-Regioni 2012 — abilitazione deve essere null
_NO_PATENTINO = {
    "compressore", "motocompressore", "gruppo elettrogeno", "generatore",
    "piastra vibrante", "costipatore",
    "rullo compattatore", "rullo compressore",
    "bulldozer", "apripista",
    "betoniera", "betonpompa",
    "saldatrice", "saldatrice mig", "saldatrice tig",
    "pressa", "pressa idraulica", "pressa piegatrice", "piegatrice",
    "punzonatrice", "cesoie", "tranciatrice",
    "tornio", "fresatrice", "rettificatrice",
    "laser", "macchina taglio laser",
}

# Macchine soggette a verifiche Allegato VII D.Lgs. 81/08
_SHOULD_HAVE_VERIFICHE = {
    "carrello elevatore", "muletto", "sollevatore telescopico", "telehandler",
    "gru mobile", "gru a torre", "gru su autocarro", "camion gru",
    "piattaforma aerea", "ple", "piattaforma elevabile",
    "pompa calcestruzzo", "autobetonpompa",
    "terna", "terne", "retroescavatore",
    "argano", "verricello", "montacarichi",
}

# Macchine per cui verifiche_periodiche deve essere null
_NO_VERIFICHE = {
    "piastra vibrante", "costipatore",
    "rullo compattatore", "rullo compressore",
    "bulldozer", "apripista",
    "compressore", "motocompressore",
    "saldatrice", "betoniera",
    "escavatore",  # puro, senza funzione di sollevamento
}


# ── Valutazione qualità ───────────────────────────────────────────────────────

def evaluate(
    brand: str,
    model: str,
    machine_type: Optional[str],
    safety_card,
    producer_match_type: str = "unknown",
    producer_pages: int = 0,
    inail_url: Optional[str] = None,
    producer_url: Optional[str] = None,
) -> list[dict]:
    """
    Valuta la qualità della scheda con regole deterministiche.
    Ritorna una lista di issue, ognuno con: type, severity, message.
    Severità: "high" | "medium" | "low"
    """
    issues: list[dict] = []
    mt = (machine_type or "").lower().strip()

    def _issue(type_: str, severity: str, message: str):
        issues.append({"type": type_, "severity": severity, "message": message})

    # ── Contenuto ────────────────────────────────────────────────────────────

    n_rischi = len(getattr(safety_card, "rischi_principali", None) or [])
    n_checklist = len(getattr(safety_card, "checklist", None) or [])
    n_dispositivi = len(getattr(safety_card, "dispositivi_sicurezza", None) or [])
    fonte_tipo = getattr(safety_card, "fonte_tipo", "") or ""

    if n_rischi == 0:
        _issue("empty_rischi", "high",
               "Nessun rischio estratto — il documento potrebbe essere un catalogo o non pertinente")

    if n_checklist == 0:
        _issue("empty_checklist", "medium",
               "Nessuna voce checklist — il documento non contiene istruzioni ispettive")

    if n_dispositivi == 0 and fonte_tipo != "fallback_ai":
        _issue("empty_dispositivi", "low",
               "Nessun dispositivo di sicurezza estratto dal documento")

    # ── Fonte ─────────────────────────────────────────────────────────────────

    if fonte_tipo == "fallback_ai" and mt in _SHOULD_HAVE_MANUAL:
        _issue("expected_manual_not_found", "medium",
               f"Nessun manuale trovato per '{machine_type}' — atteso per questa categoria")

    if producer_match_type == "category" and mt in _SHOULD_HAVE_MANUAL and producer_pages < 40:
        _issue("low_quality_category_pdf", "medium",
               f"Manuale produttore di categoria simile e corto ({producer_pages} pag.) "
               "— rischio di contenuto non specifico per il modello")

    if producer_match_type == "unrelated":
        _issue("unrelated_producer_pdf", "high",
               "Il PDF produttore è stato classificato come 'unrelated' ma è stato usato lo stesso")

    # Rileva URL sospetti nel producer (cataloghi, datasheet, spec sheet)
    suspicious_url_fragments = [
        "tooling", "catalog", "catalogue", "spare", "ricambi", "datasheet",
        "spec-sheet", "spec_sheet", "brochure", "listino",
    ]
    if producer_url:
        url_lower = producer_url.lower()
        for frag in suspicious_url_fragments:
            if frag in url_lower:
                _issue("suspicious_producer_url", "medium",
                       f"URL produttore contiene '{frag}' — potrebbe essere un catalogo, non un manuale d'uso: {producer_url[:80]}")
                break

    # ── Campi normativi ───────────────────────────────────────────────────────

    abilitazione = getattr(safety_card, "abilitazione_operatore", None) or ""
    verifiche = getattr(safety_card, "verifiche_periodiche", None)

    # Abilitazione citata per macchine NON coperte dall'Accordo S-R 2012
    if mt in _NO_PATENTINO and abilitazione:
        ab_lower = abilitazione.lower()
        if "accordo stato" in ab_lower or "accordo s-r" in ab_lower or "patentino" in ab_lower:
            _issue("wrong_abilitazione_cited", "medium",
                   f"'{machine_type}' NON è coperta dall'Accordo S-R 2012 ma l'abilitazione la cita: "
                   f"{abilitazione[:120]}")

    # Verifiche_periodiche NULL per macchine soggette ad Allegato VII
    if verifiche is None and mt in _SHOULD_HAVE_VERIFICHE:
        _issue("missing_verifiche_allegato7", "high",
               f"'{machine_type}' è soggetta a verifiche Allegato VII ma il campo è NULL")

    # Verifiche_periodiche NON-NULL per macchine non soggette
    if verifiche is not None and mt in _NO_VERIFICHE:
        _issue("spurious_verifiche", "low",
               f"'{machine_type}' NON è soggetta ad Allegato VII ma verifiche_periodiche è valorizzato")

    # ── Sanity checks semantici ───────────────────────────────────────────────

    # Il primo rischio NON deve menzionare una macchina diversa nella stessa categoria
    rischi = getattr(safety_card, "rischi_principali", None) or []
    if rischi and mt:
        first_risk_text = ""
        r0 = rischi[0]
        if isinstance(r0, dict):
            first_risk_text = (r0.get("testo") or "").lower()
        elif isinstance(r0, str):
            first_risk_text = r0.lower()

        # Coppie: se la macchina è X, il primo rischio NON dovrebbe menzionare Y
        wrong_mentions = {
            "carrello elevatore": ["gru a torre", "ribaltamento della gru"],
            "muletto": ["gru a torre", "ribaltamento della gru"],
            "piattaforma aerea": ["gru a torre", "ribaltamento della gru"],
            "escavatore": ["gru a torre"],
            "compressore": ["gru", "sollevamento", "ribaltamento del mezzo"],
        }
        for wrong_phrase in wrong_mentions.get(mt, []):
            if wrong_phrase in first_risk_text:
                _issue("wrong_category_content", "high",
                       f"Il rischio principale menziona '{wrong_phrase}' per una macchina di tipo "
                       f"'{machine_type}' — probabile documento sbagliato: {first_risk_text[:100]}")
                break

    return issues


# ── API pubblica ──────────────────────────────────────────────────────────────

def log_analysis(
    brand: str,
    model: str,
    machine_type: Optional[str],
    safety_card,
    producer_match_type: str = "unknown",
    producer_pages: int = 0,
    inail_url: Optional[str] = None,
    producer_url: Optional[str] = None,
) -> None:
    """
    Valuta e logga la qualità dell'analisi. Non-blocking, non solleva eccezioni.
    Da chiamare al termine di ogni pipeline SSE.
    """
    try:
        issues = evaluate(
            brand=brand, model=model, machine_type=machine_type,
            safety_card=safety_card,
            producer_match_type=producer_match_type,
            producer_pages=producer_pages,
            inail_url=inail_url,
            producer_url=producer_url,
        )

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "macchina": f"{brand} {model}",
            "machine_type": machine_type or "",
            "fonte_tipo": getattr(safety_card, "fonte_tipo", ""),
            "producer_url": (producer_url or "")[:120],
            "inail_url": (inail_url or "")[:120],
            "producer_match": producer_match_type,
            "producer_pages": producer_pages,
            "n_rischi": len(getattr(safety_card, "rischi_principali", None) or []),
            "n_checklist": len(getattr(safety_card, "checklist", None) or []),
            "has_abilitazione": getattr(safety_card, "abilitazione_operatore", None) is not None,
            "has_verifiche": getattr(safety_card, "verifiche_periodiche", None) is not None,
            "issues": issues,
            "n_issues": len(issues),
            "has_high": any(i["severity"] == "high" for i in issues),
        }

        _quality_log.append(entry)

        # Rotazione FIFO per evitare memory leak
        if len(_quality_log) > _MAX_LOG_ENTRIES:
            _quality_log.pop(0)

        if issues:
            logger.info(
                "QualityLog [%s %s / %s]: %d issue(s) — %s",
                brand, model, machine_type or "?",
                len(issues),
                "; ".join(i["message"][:60] for i in issues),
            )

    except Exception as e:
        logger.warning("quality_service.log_analysis failed (non-critical): %s", e)


def get_log(only_with_issues: bool = False, min_severity: str = "low") -> list[dict]:
    """Restituisce il log, opzionalmente filtrato."""
    severity_order = {"low": 0, "medium": 1, "high": 2}
    min_sev = severity_order.get(min_severity, 0)

    result = []
    for entry in reversed(_quality_log):  # più recenti prima
        if only_with_issues and entry["n_issues"] == 0:
            continue
        if min_sev > 0:
            max_sev = max(
                (severity_order.get(i["severity"], 0) for i in entry["issues"]),
                default=-1,
            )
            if max_sev < min_sev:
                continue
        result.append(entry)
    return result


def get_summary() -> dict:
    """Statistiche aggregate del log corrente."""
    if not _quality_log:
        return {"total": 0, "with_issues": 0, "issue_types": {}}

    total = len(_quality_log)
    with_issues = sum(1 for e in _quality_log if e["n_issues"] > 0)
    issue_counts: dict[str, int] = {}
    for entry in _quality_log:
        for issue in entry["issues"]:
            t = issue["type"]
            issue_counts[t] = issue_counts.get(t, 0) + 1

    sorted_issues = dict(sorted(issue_counts.items(), key=lambda x: -x[1]))
    return {
        "total_analyses": total,
        "with_issues": with_issues,
        "issue_rate": round(with_issues / total, 2) if total else 0,
        "issue_type_counts": sorted_issues,
    }
