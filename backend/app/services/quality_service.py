"""
Quality Logger per ManualFinder.

Valuta ogni scheda di sicurezza generata con regole deterministiche (zero costo AI)
e persiste le entry su Supabase (tabella quality_log).
Fallback in-memory se DATABASE_URL non è configurata.

Consultalo via: GET https://manualfinder.onrender.com/analyze/quality-log
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)

# ── Fallback in-memory (se DB non disponibile) ───────────────────────────────
_quality_log: list[dict] = []
_MAX_LOG_ENTRIES = 500


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_conn():
    from app.config import settings
    import psycopg2
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL non configurata")
    return psycopg2.connect(settings.database_url)


def _db_available() -> bool:
    from app.config import settings
    return bool(settings.database_url)


# ── Dati seed per i flag machine_types (usati SOLO da _seed_machine_type_flags_if_needed) ──
# A runtime si usano i flag da machine_types DB tramite get_flags(machine_type_id).

_SHOULD_HAVE_MANUAL_SEED = {
    "escavatore", "gru mobile", "gru a torre", "gru su autocarro",
    "carrello elevatore", "sollevatore telescopico",
    "piattaforma aerea",
    "pompa calcestruzzo",
    "pala caricatrice",
    "pressa piegatrice",
}

# Macchine utensili da officina — non da cantiere/edilizia
_IS_OFFICINA_SEED = {
    "pressa piegatrice", "punzonatrice", "macchina taglio laser",
    "sega circolare", "centro di lavoro CNC", "tornio", "fresatrice",
    "saldatrice",
}


def _seed_machine_type_flags_if_needed() -> None:
    """
    Popola should_have_manual e is_officina su machine_types, solo se tutti a false (primo run).
    Idempotente: eseguita solo se necessario.
    """
    if not _db_available():
        return
    try:
        import psycopg2
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM machine_types WHERE should_have_manual = true")
            already_manual = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM machine_types WHERE is_officina = true")
            already_officina = cur.fetchone()[0]
        if already_manual > 0 and already_officina > 0:
            conn.close()
            logger.info(
                "quality_service: flag già valorizzati (should_have_manual=%d, is_officina=%d)",
                already_manual, already_officina,
            )
            return
        from app.services.machine_type_service import resolve_machine_type_id
        updated_manual = updated_officina = 0
        with conn.cursor() as cur:
            if already_manual == 0:
                for type_name in _SHOULD_HAVE_MANUAL_SEED:
                    mt_id = resolve_machine_type_id(type_name)
                    if mt_id:
                        cur.execute(
                            "UPDATE machine_types SET should_have_manual = true WHERE id = %s",
                            (mt_id,),
                        )
                        updated_manual += 1
            if already_officina == 0:
                for type_name in _IS_OFFICINA_SEED:
                    mt_id = resolve_machine_type_id(type_name)
                    if mt_id:
                        cur.execute(
                            "UPDATE machine_types SET is_officina = true WHERE id = %s",
                            (mt_id,),
                        )
                        updated_officina += 1
        conn.commit()
        conn.close()
        logger.info(
            "quality_service: seed flag completato (should_have_manual=%d, is_officina=%d)",
            updated_manual, updated_officina,
        )
    except Exception as e:
        logger.warning("quality_service: _seed_machine_type_flags_if_needed fallito: %s", e)


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
    machine_type_id: Optional[int] = None,
) -> list[dict]:
    issues: list[dict] = []

    def _issue(type_: str, severity: str, message: str):
        issues.append({"type": type_, "severity": severity, "message": message})

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

    # Recupera flag normativi dal DB tramite ID (fail-safe)
    flags: dict = {}
    if machine_type_id is not None:
        try:
            from app.services.machine_type_service import get_flags
            flags = get_flags(machine_type_id)
        except Exception:
            pass

    should_have_manual = flags.get("should_have_manual", False)
    requires_patentino = flags.get("requires_patentino", True)   # conservativo se sconosciuto
    requires_verifiche = flags.get("requires_verifiche", None)   # None = sconosciuto

    if fonte_tipo == "fallback_ai" and should_have_manual:
        _issue("expected_manual_not_found", "medium",
               f"Nessun manuale trovato per '{machine_type}' — atteso per questa categoria")

    if producer_match_type == "category" and should_have_manual and producer_pages < 40:
        _issue("low_quality_category_pdf", "medium",
               f"Manuale produttore di categoria simile e corto ({producer_pages} pag.) "
               "— rischio di contenuto non specifico per il modello")

    # "unrelated" è un falso positivo se la fonte usata è fallback_ai o inail:
    # significa che il PDF è stato correttamente scartato dalla pipeline.
    if producer_match_type == "unrelated" and fonte_tipo not in ("fallback_ai", "inail"):
        _issue("unrelated_producer_pdf", "high",
               "Il PDF produttore è stato classificato come 'unrelated' ma è stato usato lo stesso")

    suspicious_url_fragments = [
        "tooling", "catalog", "catalogue", "catalogo", "spare", "ricambi", "datasheet",
        "spec-sheet", "spec_sheet", "brochure", "listino",
        "environmental", "declaration", "/epd/", "sustainability", "emissions",
        "press-release", "/news/", "flyer", "promo",
    ]
    if producer_url:
        url_lower = producer_url.lower()
        for frag in suspicious_url_fragments:
            if frag in url_lower:
                _issue("suspicious_producer_url", "medium",
                       f"URL produttore contiene '{frag}' — potrebbe essere un catalogo, non un manuale d'uso: {producer_url[:80]}")
                break

    abilitazione = getattr(safety_card, "abilitazione_operatore", None) or ""
    verifiche = getattr(safety_card, "verifiche_periodiche", None)

    # Check abilitazione: solo quando abbiamo un ID e sappiamo che NON richiede patentino
    if machine_type_id is not None and not requires_patentino and abilitazione:
        ab_lower = abilitazione.lower()
        if "accordo stato" in ab_lower or "accordo s-r" in ab_lower or "patentino" in ab_lower:
            _issue("wrong_abilitazione_cited", "medium",
                   f"'{machine_type}' NON è coperta dall'Accordo S-R 2012 ma l'abilitazione la cita: "
                   f"{abilitazione[:120]}")

    # Check verifiche: solo quando abbiamo un ID con flag esplicito
    if machine_type_id is not None and requires_verifiche is not None:
        if verifiche is None and requires_verifiche:
            _issue("missing_verifiche_allegato7", "high",
                   f"'{machine_type}' è soggetta a verifiche Allegato VII ma il campo è NULL")
        if verifiche is not None and not requires_verifiche:
            _issue("spurious_verifiche", "low",
                   f"'{machine_type}' NON è soggetta ad Allegato VII ma verifiche_periodiche è valorizzato")

    mt = (machine_type or "").lower().strip()
    rischi = getattr(safety_card, "rischi_principali", None) or []
    if rischi and mt:
        first_risk_text = ""
        r0 = rischi[0]
        if isinstance(r0, dict):
            first_risk_text = (r0.get("testo") or "").lower()
        elif isinstance(r0, str):
            first_risk_text = r0.lower()
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
    machine_type_id: Optional[int] = None,
) -> None:
    try:
        # Auto-resolve machine_type_id se non fornito
        if machine_type_id is None and machine_type:
            try:
                from app.services.machine_type_service import resolve_machine_type_id
                machine_type_id = resolve_machine_type_id(machine_type)
            except Exception:
                pass

        issues = evaluate(
            brand=brand, model=model, machine_type=machine_type,
            safety_card=safety_card,
            producer_match_type=producer_match_type,
            producer_pages=producer_pages,
            inail_url=inail_url,
            producer_url=producer_url,
            machine_type_id=machine_type_id,
        )

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "macchina": f"{brand} {model}",
            "machine_type": machine_type or "",
            "machine_type_id": machine_type_id,
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

        if _db_available():
            _db_insert(entry)
        else:
            _quality_log.append(entry)
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


def _db_insert(entry: dict) -> None:
    import psycopg2
    import psycopg2.extras
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO quality_log (
                    ts, macchina, machine_type, machine_type_id, fonte_tipo,
                    producer_url, inail_url, producer_match, producer_pages,
                    n_rischi, n_checklist, has_abilitazione, has_verifiche,
                    issues, n_issues, has_high
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    entry["ts"], entry["macchina"], entry["machine_type"],
                    entry.get("machine_type_id"), entry["fonte_tipo"],
                    entry["producer_url"], entry["inail_url"], entry["producer_match"], entry["producer_pages"],
                    entry["n_rischi"], entry["n_checklist"], entry["has_abilitazione"], entry["has_verifiche"],
                    json.dumps(entry["issues"]), entry["n_issues"], entry["has_high"],
                ),
            )
            conn.commit()


def get_log(only_with_issues: bool = False, min_severity: str = "low") -> list[dict]:
    if _db_available():
        return _db_get_log(only_with_issues=only_with_issues, min_severity=min_severity)
    # fallback in-memory
    severity_order = {"low": 0, "medium": 1, "high": 2}
    min_sev = severity_order.get(min_severity, 0)
    result = []
    for entry in reversed(_quality_log):
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


def _db_get_log(only_with_issues: bool = False, min_severity: str = "low") -> list[dict]:
    import psycopg2.extras
    severity_order = {"low": 0, "medium": 1, "high": 2}
    min_sev = severity_order.get(min_severity, 0)

    conditions = []
    if only_with_issues:
        conditions.append("n_issues > 0")
    if min_sev == 1:
        # medium o high: almeno un issue medium/high nel JSONB
        conditions.append(
            "issues @> '[{\"severity\":\"medium\"}]'::jsonb OR issues @> '[{\"severity\":\"high\"}]'::jsonb"
        )
    elif min_sev == 2:
        conditions.append("has_high = true")

    where = f"WHERE {' AND '.join(f'({c})' for c in conditions)}" if conditions else ""
    sql = f"SELECT * FROM quality_log {where} ORDER BY ts DESC LIMIT 500"

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    result = []
    for row in rows:
        entry = dict(row)
        entry["id"] = str(entry["id"])
        entry["ts"] = entry["ts"].isoformat() if hasattr(entry["ts"], "isoformat") else entry["ts"]
        # issues è già una lista da JSONB
        if isinstance(entry["issues"], str):
            entry["issues"] = json.loads(entry["issues"])
        result.append(entry)
    return result


def get_summary() -> dict:
    if _db_available():
        return _db_get_summary()
    # fallback in-memory
    if not _quality_log:
        return {"total": 0, "with_issues": 0, "issue_types": {}}
    total = len(_quality_log)
    with_issues = sum(1 for e in _quality_log if e["n_issues"] > 0)
    issue_counts: dict[str, int] = {}
    for entry in _quality_log:
        for issue in entry["issues"]:
            t = issue["type"]
            issue_counts[t] = issue_counts.get(t, 0) + 1
    return {
        "total_analyses": total,
        "with_issues": with_issues,
        "issue_rate": round(with_issues / total, 2) if total else 0,
        "issue_type_counts": dict(sorted(issue_counts.items(), key=lambda x: -x[1])),
    }


def _db_get_summary() -> dict:
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM quality_log")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM quality_log WHERE n_issues > 0")
            with_issues = cur.fetchone()[0]
            cur.execute(
                """
                SELECT issue->>'type' AS itype, COUNT(*) AS cnt
                FROM quality_log, jsonb_array_elements(issues) AS issue
                GROUP BY itype
                ORDER BY cnt DESC
                """
            )
            issue_counts = {row[0]: row[1] for row in cur.fetchall()}

    return {
        "total_analyses": total,
        "with_issues": with_issues,
        "issue_rate": round(with_issues / total, 2) if total else 0,
        "issue_type_counts": issue_counts,
    }


async def generate_improvement_report() -> dict:
    """
    Analisi critica AI del log accumulato.
    Costo: ~3-5k token Gemini Flash (~$0.0003). Da chiamare manualmente via
    GET /analyze/quality-log?report=true
    """
    entries_with_issues = get_log(only_with_issues=True)
    if not entries_with_issues:
        summary = get_summary()
        if summary.get("total_analyses", 0) == 0:
            return {"error": "Log vuoto — esegui alcune analisi prima di generare il report."}
        return {"message": "Nessun issue rilevato nelle analisi accumulate. Ottimo!", "summary": summary}

    summary = get_summary()
    log_digest = []
    for e in entries_with_issues[:50]:
        log_digest.append({
            "m": e["macchina"],
            "mt": e["machine_type"],
            "ft": e["fonte_tipo"],
            "pm": e["producer_match"],
            "pp": e["producer_pages"],
            "pu": e["producer_url"][-60:] if e.get("producer_url") else "",
            "nr": e["n_rischi"],
            "nc": e["n_checklist"],
            "issues": [{"t": i["type"], "s": i["severity"], "m": i["message"][:100]} for i in e["issues"]],
        })

    prompt = f"""Sei un ingegnere software che analizza i problemi di qualità di ManualFinder, un sistema che:
1. Cerca manuali di sicurezza per macchinari industriali online (Google/Brave/Perplexity)
2. Scarica i PDF trovati e li classifica per pertinenza
3. Usa Gemini AI per estrarre una scheda sicurezza strutturata dal PDF

Hai accesso al log di qualità delle ultime analisi. Ogni entry ha:
- macchina (brand+model), tipo, fonte usata, URL produttore, n. pagine
- issues: problemi rilevati (tipo + severità + messaggio)

STATISTICHE GLOBALI:
{json.dumps(summary, ensure_ascii=False, indent=2)}

LOG DETTAGLIATO (ultime {len(log_digest)} analisi con problemi):
{json.dumps(log_digest, ensure_ascii=False)}

Analizza i pattern e produci un report con:

1. **PROBLEMI RICORRENTI** (ordinati per frequenza): per ogni tipo di issue spiega la causa radice probabile

2. **SUGGERIMENTI RICERCA** (search_service.py): modifiche specifiche alle query, ai filtri URL/titolo, alla logica di selezione candidati, ai domini da includere/escludere — con il codice Python da modificare

3. **SUGGERIMENTI PROMPT** (analysis_service.py / LEGAL_ENRICH_PROMPT): testo specifico da aggiungere/modificare nei prompt AI per risolvere i casi problematici osservati

4. **SUGGERIMENTI SCORING** (pdf_service.py): keyword da aggiungere a NEGATIVE_SIGNALS o BROCHURE_SIGNALS, soglie da cambiare

5. **CASI ANOMALI**: analisi con combinazione insolita di issues che potrebbero indicare un bug nel codice (non solo un prompt sbagliato)

Sii CONCRETO e SPECIFICO: cita i tipi di macchine problematici, i domini problematici, le keyword mancanti. Niente consigli generici.
Rispondi in italiano con markdown."""

    try:
        from app.config import settings
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=4000,
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "n_entries_analyzed": len(log_digest),
            "report": response.text,
        }
    except Exception as e:
        return {"error": f"Generazione report fallita: {e}", "summary": summary}
