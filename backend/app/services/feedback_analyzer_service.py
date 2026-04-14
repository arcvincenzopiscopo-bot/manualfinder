"""
Analisi automatica dei feedback degli ispettori (manual_feedback) per estrarre
regole di filtraggio URL (url_filter_rules) e applicarle dinamicamente nella pipeline.

Flusso:
  1. Legge feedback non ancora processati da manual_feedback
  2. Euristica dominio: ≥2 feedback not_a_manual per lo stesso netloc → block_domain (senza AI)
  3. AI per casi ambigui (1 feedback, dominio sconosciuto) → block_domain / block_url_fragment / redirect_category / skip
  4. Persiste regole in url_filter_rules (upsert)
  5. get_dynamic_rules() fornisce cache in-memory TTL 15 min per la pipeline
"""
import json
import re
import time as _time
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

from app.config import settings
from app.services.saved_manuals_service import _get_conn


# ── Cache regole dinamiche ───────────────────────────────────────────────────

_dyn_cache: Optional[tuple] = None  # (blocked_domains, blocked_fragments, redirect_rules)
_dyn_cache_ts: float = 0.0
_DYN_CACHE_TTL = 900  # 15 minuti


def get_dynamic_rules() -> tuple[set[str], set[str], list[dict]]:
    """
    Restituisce (blocked_domains, blocked_fragments, redirect_rules) dalla tabella
    url_filter_rules. Cache in-memory TTL 15 min.
    Fallisce silenziosamente — ritorna tuple di vuoti se DB non disponibile.
    """
    global _dyn_cache, _dyn_cache_ts
    now = _time.monotonic()
    if _dyn_cache is not None and now - _dyn_cache_ts < _DYN_CACHE_TTL:
        return _dyn_cache
    if not settings.database_url:
        return set(), set(), []
    try:
        blocked_domains: set[str] = set()
        blocked_fragments: set[str] = set()
        redirect_rules: list[dict] = []
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT rule_type, rule_value, context_machine_type_id
                    FROM url_filter_rules
                    WHERE is_active = true
                    """
                )
                for row in cur.fetchall():
                    rt = row["rule_type"]
                    rv = row["rule_value"]
                    if rt == "block_domain":
                        blocked_domains.add(rv)
                    elif rt == "block_url_fragment":
                        blocked_fragments.add(rv)
                    elif rt == "redirect_category":
                        redirect_rules.append(dict(row))
        _dyn_cache = (blocked_domains, blocked_fragments, redirect_rules)
        _dyn_cache_ts = now
        return _dyn_cache
    except Exception:
        if _dyn_cache is not None:
            return _dyn_cache
        return set(), set(), []


def invalidate_dynamic_rules_cache() -> None:
    """Invalida la cache in-memory delle regole dinamiche."""
    global _dyn_cache_ts
    _dyn_cache_ts = 0.0


# ── Analisi feedback ─────────────────────────────────────────────────────────

_AI_PROMPT_BATCH = """\
Sei un esperto di classificazione URL per un sistema di ricerca manuali d'uso di macchine industriali italiane.

Analizza i seguenti URL segnalati e per ognuno decidi quale regola di filtraggio applicare.

Regole applicabili:
- block_domain: il dominio pubblica quasi sempre cataloghi/brochure/ricambi, non manuali d'uso. rule_value = netloc (es. "example.com")
- block_url_fragment: il PATH contiene un frammento specifico che indica documenti non-manuali (es. "/depliant/"). rule_value = frammento path
- redirect_category: manuale valido ma per tipo macchina diverso. rule_value = tipo corretto (es. "carrello elevatore")
- skip: caso isolato non generalizzabile

Genera regola SOLO se confidence="high". Se non sei sicuro, usa skip.

Rispondi SOLO con un JSON array (un oggetto per ogni URL, stesso ordine dell'input):
[
  {{"url": "...", "rule_type": "...", "rule_value": "...", "reason": "...", "confidence": "high"|"medium"|"low"}},
  ...
]

URL da analizzare:
{items}"""

_AI_PROMPT_ITEM = "{idx}. URL: {url}\n   Feedback: {feedback_type}\n   Note: {notes}\n   Tipo macchina: {machine_type}"

_SKIP_RESULT = {"rule_type": "skip", "rule_value": "", "reason": "quota esaurita o AI non disponibile", "confidence": "low"}


async def _call_ai_rules_batch(
    items: list[dict],  # ogni item: {url, feedback_type, notes, machine_type}
) -> list[dict]:
    """
    Classifica una lista di URL in un'unica chiamata AI (batch).
    Risparmia N-1 chiamate rispetto al loop singolo.
    Ritorna una lista di risultati nello stesso ordine dell'input.
    """
    from app.services.llm_router import llm_router, LLMQuotaExceededError

    items_text = "\n\n".join(
        _AI_PROMPT_ITEM.format(
            idx=i + 1,
            url=item["url"],
            feedback_type=item["feedback_type"],
            notes=item.get("notes") or "(nessuna nota)",
            machine_type=item.get("machine_type") or "non specificato",
        )
        for i, item in enumerate(items)
    )
    prompt = _AI_PROMPT_BATCH.format(items=items_text)

    try:
        raw_text = await llm_router.generate_text(
            "url_rule", prompt, fast=True, max_tokens=min(256 * len(items), 4096)
        )
    except LLMQuotaExceededError:
        return [_SKIP_RESULT.copy() for _ in items]
    except Exception as e:
        logger.warning("_call_ai_rules_batch: errore AI — %s", e)
        return [_SKIP_RESULT.copy() for _ in items]

    # Estrai array JSON dalla risposta
    try:
        start = raw_text.find("[")
        end = raw_text.rfind("]")
        if start != -1 and end != -1:
            results = json.loads(raw_text[start:end + 1])
            if isinstance(results, list):
                # Allinea alla lunghezza attesa (l'AI potrebbe restituirne meno)
                while len(results) < len(items):
                    results.append(_SKIP_RESULT.copy())
                return results[:len(items)]
    except Exception:
        pass
    return [_SKIP_RESULT.copy() for _ in items]


def _upsert_rule(
    conn,
    rule_type: str,
    rule_value: str,
    context_machine_type: Optional[str],
    reason: str,
    source_urls: list[str],
    feedback_count: int = 1,
    context_machine_type_id: Optional[int] = None,
) -> str:
    """
    Inserisce o aggiorna una regola in url_filter_rules.
    Ritorna 'created' o 'updated'.
    """
    # Auto-resolve context_machine_type_id se non fornito
    if context_machine_type_id is None and context_machine_type:
        try:
            from app.services.machine_type_service import resolve_machine_type_id as _resolve
            context_machine_type_id = _resolve(context_machine_type)
        except Exception:
            pass
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO url_filter_rules
                (rule_type, rule_value, context_machine_type_id,
                 reason, source_urls, feedback_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (rule_type, rule_value) DO UPDATE SET
                feedback_count          = url_filter_rules.feedback_count + EXCLUDED.feedback_count,
                source_urls             = (
                    SELECT array_agg(DISTINCT u)
                    FROM unnest(url_filter_rules.source_urls || EXCLUDED.source_urls) AS u
                ),
                reason                  = EXCLUDED.reason,
                context_machine_type_id = COALESCE(EXCLUDED.context_machine_type_id,
                                                   url_filter_rules.context_machine_type_id)
            RETURNING (xmax = 0) AS inserted
            """,
            (rule_type, rule_value, context_machine_type_id,
             reason, source_urls, feedback_count),
        )
        row = cur.fetchone()
        conn.commit()
        return "created" if (row and row[0]) else "updated"


def _already_analyzed_urls() -> set[str]:
    """Ritorna il set di URL già presenti in source_urls di qualche regola."""
    if not settings.database_url:
        return set()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT unnest(source_urls) FROM url_filter_rules")
                return {row[0] for row in cur.fetchall()}
    except Exception:
        return set()


async def _analyze_quality_log_patterns() -> tuple[int, int]:
    """
    Estrae pattern da quality_log (unrelated_producer_pdf / suspicious_producer_url)
    e crea regole block_domain per domini che compaiono >= 2 volte con tali issue.
    Chiamata automaticamente all'inizio di run_analysis().
    """
    if not settings.database_url:
        return 0, 0
    try:
        import psycopg2.extras
        from collections import defaultdict
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT producer_url, machine_type
                    FROM quality_log
                    WHERE producer_url IS NOT NULL AND producer_url != ''
                      AND (
                          issues @> '[{"type": "unrelated_producer_pdf"}]'::jsonb
                          OR issues @> '[{"type": "suspicious_producer_url"}]'::jsonb
                      )
                    ORDER BY ts DESC
                    LIMIT 300
                    """
                )
                rows = cur.fetchall()
    except Exception:
        return 0, 0

    domain_hits: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        try:
            netloc = urlparse(row["producer_url"]).netloc.lower()
            if netloc:
                domain_hits[netloc].append(row["producer_url"])
        except Exception:
            pass

    created = 0
    updated = 0
    try:
        with _get_conn() as conn:
            for netloc, urls in domain_hits.items():
                if len(urls) >= 2:
                    reason = (
                        f"Dominio con {len(urls)} URL problematici in quality_log "
                        "(unrelated_producer_pdf / suspicious_producer_url)"
                    )
                    action = _upsert_rule(
                        conn,
                        rule_type="block_domain",
                        rule_value=netloc,
                        context_machine_type=None,
                        reason=reason,
                        source_urls=list({u for u in urls}),
                        feedback_count=len(urls),
                    )
                    if action == "created":
                        created += 1
                    else:
                        updated += 1
    except Exception:
        pass

    if created + updated > 0:
        invalidate_dynamic_rules_cache()

    return created, updated


async def run_analysis(provider: str) -> dict:
    """
    Analizza i feedback non processati e crea/aggiorna regole in url_filter_rules.
    Ritorna statistiche: {rules_created, rules_updated, skipped, feedback_processed, new_rules}.
    """
    if not settings.database_url:
        return {"rules_created": 0, "rules_updated": 0, "skipped": 0, "feedback_processed": 0, "new_rules": []}

    # ── Step 0: pattern da quality_log ──────────────────────────────────────
    ql_created, ql_updated = await _analyze_quality_log_patterns()

    # ── Step 1: carica feedback non ancora processati ────────────────────────
    already_done = _already_analyzed_urls()

    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT url, feedback_type, brand, model, machine_type, machine_type_id,
                           useful_for_type_id, notes
                    FROM manual_feedback
                    WHERE feedback_type IN ('not_a_manual', 'wrong_category', 'useful_other_category')
                    ORDER BY ts DESC
                    LIMIT 500
                    """
                )
                all_feedback = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        return {"error": str(e), "rules_created": 0, "rules_updated": 0, "skipped": 0, "feedback_processed": 0, "new_rules": []}

    # Escludi URL già processati
    feedback = [f for f in all_feedback if f["url"] not in already_done]
    if not feedback:
        return {"rules_created": 0, "rules_updated": 0, "skipped": 0, "feedback_processed": 0, "new_rules": []}

    # Carica i frammenti già presenti in _PDF_EXCLUDE_TERMS
    try:
        from app.services.search_service import _PDF_EXCLUDE_TERMS as _existing_terms
    except Exception:
        _existing_terms = frozenset()

    # ── Step 2: euristica dominio (zero AI) ──────────────────────────────────
    domain_groups: dict[str, list[dict]] = defaultdict(list)
    for fb in feedback:
        try:
            netloc = urlparse(fb["url"]).netloc.lower()
            domain_groups[netloc].append(fb)
        except Exception:
            pass

    rules_created = 0
    rules_updated = 0
    skipped = 0
    processed_urls: set[str] = set()
    new_rules: list[dict] = []

    with _get_conn() as conn:
        for netloc, entries in domain_groups.items():
            not_a_manual_entries = [e for e in entries if e["feedback_type"] == "not_a_manual"]

            # Dominio con ≥2 feedback not_a_manual → block_domain senza AI
            if len(not_a_manual_entries) >= 2:
                source_urls = list({e["url"] for e in not_a_manual_entries})
                reason = f"Dominio segnalato {len(not_a_manual_entries)}x come non-manuale da ispettori"
                action = _upsert_rule(
                    conn,
                    rule_type="block_domain",
                    rule_value=netloc,
                    context_machine_type=None,
                    reason=reason,
                    source_urls=source_urls,
                    feedback_count=len(not_a_manual_entries),
                )
                if action == "created":
                    rules_created += 1
                    new_rules.append({"rule_type": "block_domain", "rule_value": netloc, "reason": reason})
                else:
                    rules_updated += 1
                processed_urls.update(source_urls)

        # ── Step 3: AI per casi ambigui (batch) ──────────────────────────────
        remaining = [f for f in feedback if f["url"] not in processed_urls]

        # Prima passata: gestisci i casi senza AI
        ai_needed: list[dict] = []
        for fb in remaining:
            url = fb["url"]
            parsed = urlparse(url)
            path = parsed.path.lower()

            # Frammento già in _PDF_EXCLUDE_TERMS → salta (già gestito)
            if any(term in path for term in _existing_terms):
                skipped += 1
                processed_urls.add(url)
                continue

            # useful_other_category → redirect_category direttamente (nessuna AI necessaria)
            useful_for_type_id = fb.get("useful_for_type_id")
            useful_for_name = None
            if useful_for_type_id:
                try:
                    from app.services.machine_type_service import get_name_by_id as _get_name
                    useful_for_name = _get_name(useful_for_type_id)
                except Exception:
                    pass
            if fb["feedback_type"] == "useful_other_category" and useful_for_name:
                source_urls = [url]
                mt_orig = fb.get("machine_type") or ""
                reason = f"Manuale utile per '{useful_for_name}', non per '{mt_orig}'"
                action = _upsert_rule(
                    conn,
                    rule_type="redirect_category",
                    rule_value=useful_for_name,
                    context_machine_type=mt_orig or None,
                    context_machine_type_id=fb.get("machine_type_id"),
                    reason=reason,
                    source_urls=source_urls,
                    feedback_count=1,
                )
                if action == "created":
                    rules_created += 1
                    new_rules.append({"rule_type": "redirect_category", "rule_value": useful_for_name, "reason": reason})
                else:
                    rules_updated += 1
                processed_urls.add(url)
                continue

            # Accodato per batch AI
            ai_needed.append(fb)

        # Seconda passata: una singola chiamata AI per tutti i casi ambigui (R3)
        if ai_needed:
            batch_input = [
                {
                    "url": fb["url"],
                    "feedback_type": fb["feedback_type"],
                    "notes": fb.get("notes") or "",
                    "machine_type": fb.get("machine_type") or "",
                }
                for fb in ai_needed
            ]
            ai_results = await _call_ai_rules_batch(batch_input)

            for fb, result in zip(ai_needed, ai_results):
                url = fb["url"]
                if result.get("confidence") != "high" or result.get("rule_type") == "skip":
                    skipped += 1
                    processed_urls.add(url)
                    continue

                rule_type = result.get("rule_type", "skip")
                rule_value = result.get("rule_value", "").strip()
                if not rule_value or rule_type == "skip":
                    skipped += 1
                    processed_urls.add(url)
                    continue

                ctx_mt = None
                if rule_type == "redirect_category":
                    ctx_mt = fb.get("machine_type") or None

                action = _upsert_rule(
                    conn,
                    rule_type=rule_type,
                    rule_value=rule_value,
                    context_machine_type=ctx_mt,
                    reason=result.get("reason", ""),
                    source_urls=[url],
                    feedback_count=1,
                )
                if action == "created":
                    rules_created += 1
                    new_rules.append({"rule_type": rule_type, "rule_value": rule_value, "reason": result.get("reason", "")})
                else:
                    rules_updated += 1
                processed_urls.add(url)

    # Invalida cache dopo aggiornamenti
    total_created = rules_created + ql_created
    total_updated = rules_updated + ql_updated
    if total_created + total_updated > 0:
        invalidate_dynamic_rules_cache()

    # Auto-ottimizzazione prompt: migliora i rule per i tipi macchina con qualità bassa
    prompts_improved = 0
    try:
        from app.services import prompt_optimizer_service
        opt_result = await prompt_optimizer_service.run_optimizer(min_analyses=5)
        prompts_improved = opt_result.get("types_improved", 0)
        if prompts_improved > 0:
            logger.info("prompt_optimizer: migliorati %d prompt rule", prompts_improved)
    except Exception as e:
        logger.warning("prompt_optimizer non eseguito (non critico): %s", e)

    return {
        "rules_created": total_created,
        "rules_updated": total_updated,
        "skipped": skipped,
        "feedback_processed": len(processed_urls),
        "quality_log_rules_created": ql_created,
        "quality_log_rules_updated": ql_updated,
        "prompts_improved": prompts_improved,
        "new_rules": new_rules,
    }
