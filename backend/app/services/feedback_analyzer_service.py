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
                    SELECT rule_type, rule_value, context_machine_type
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

_AI_PROMPT = """\
Sei un esperto di classificazione URL per un sistema di ricerca manuali d'uso di macchine industriali italiane.

URL segnalato: {url}
Tipo feedback: {feedback_type}
Note ispettore: {notes}
Tipo macchina cercata: {machine_type}

Analizza l'URL e decidi quale regola applicare per evitare di proporre ancora questo tipo di documento.

Rispondi SOLO con JSON (nessun testo aggiuntivo):
{{
  "rule_type": "block_domain" | "block_url_fragment" | "redirect_category" | "skip",
  "rule_value": "<valore della regola>",
  "reason": "<spiegazione in 1 riga>",
  "confidence": "high" | "medium" | "low"
}}

Regole:
- block_domain: il dominio pubblica quasi sempre cataloghi/brochure/ricambi, non manuali d'uso. rule_value = netloc (es. "example.com")
- block_url_fragment: il PATH contiene un frammento specifico che indica documenti non-manuali (es. "/depliant/", "/product-line/"). rule_value = frammento path (es. "/depliant/")
- redirect_category: è un manuale d'uso valido ma per un tipo di macchina diverso. rule_value = tipo corretto (es. "carrello elevatore")
- skip: caso isolato non generalizzabile come regola

Genera regola SOLO se confidence="high". Se non sei sicuro, usa skip."""


async def _call_ai_rule(
    url: str,
    feedback_type: str,
    notes: str,
    machine_type: str,
    provider: str,
) -> dict:
    """Chiama l'AI per classificare un URL in una regola di filtraggio."""
    prompt = _AI_PROMPT.format(
        url=url,
        feedback_type=feedback_type,
        notes=notes or "(nessuna nota)",
        machine_type=machine_type or "non specificato",
    )

    raw_text = ""
    if provider == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",  # modello economico per task semplice
            max_tokens=256,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text

    elif provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=256,
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw_text = response.text

    else:
        return {"rule_type": "skip", "rule_value": "", "reason": "nessun AI configurato", "confidence": "low"}

    # Estrai JSON dalla risposta
    try:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {"rule_type": "skip", "rule_value": "", "reason": "risposta AI non parsabile", "confidence": "low"}


def _upsert_rule(
    conn,
    rule_type: str,
    rule_value: str,
    context_machine_type: Optional[str],
    reason: str,
    source_urls: list[str],
    feedback_count: int = 1,
) -> str:
    """
    Inserisce o aggiorna una regola in url_filter_rules.
    Ritorna 'created' o 'updated'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO url_filter_rules
                (rule_type, rule_value, context_machine_type, reason, source_urls, feedback_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (rule_type, rule_value) DO UPDATE SET
                feedback_count = url_filter_rules.feedback_count + EXCLUDED.feedback_count,
                source_urls    = (
                    SELECT array_agg(DISTINCT u)
                    FROM unnest(url_filter_rules.source_urls || EXCLUDED.source_urls) AS u
                ),
                reason = EXCLUDED.reason
            RETURNING (xmax = 0) AS inserted
            """,
            (rule_type, rule_value, context_machine_type, reason, source_urls, feedback_count),
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


async def run_analysis(provider: str) -> dict:
    """
    Analizza i feedback non processati e crea/aggiorna regole in url_filter_rules.
    Ritorna statistiche: {rules_created, rules_updated, skipped, feedback_processed, new_rules}.
    """
    if not settings.database_url:
        return {"rules_created": 0, "rules_updated": 0, "skipped": 0, "feedback_processed": 0, "new_rules": []}

    # ── Step 1: carica feedback non ancora processati ────────────────────────
    already_done = _already_analyzed_urls()

    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT url, feedback_type, brand, model, machine_type, useful_for_type, notes
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

        # ── Step 3: AI per casi ambigui ──────────────────────────────────────
        remaining = [f for f in feedback if f["url"] not in processed_urls]

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
            if fb["feedback_type"] == "useful_other_category" and fb.get("useful_for_type"):
                source_urls = [url]
                mt_orig = fb.get("machine_type") or ""
                reason = f"Manuale utile per '{fb['useful_for_type']}', non per '{mt_orig}'"
                action = _upsert_rule(
                    conn,
                    rule_type="redirect_category",
                    rule_value=fb["useful_for_type"],
                    context_machine_type=mt_orig or None,
                    reason=reason,
                    source_urls=source_urls,
                    feedback_count=1,
                )
                if action == "created":
                    rules_created += 1
                    new_rules.append({"rule_type": "redirect_category", "rule_value": fb["useful_for_type"], "reason": reason})
                else:
                    rules_updated += 1
                processed_urls.add(url)
                continue

            # Chiama AI per casi rimanenti (provider disponibile)
            if provider not in ("anthropic", "gemini"):
                skipped += 1
                continue

            try:
                result = await _call_ai_rule(
                    url=url,
                    feedback_type=fb["feedback_type"],
                    notes=fb.get("notes") or "",
                    machine_type=fb.get("machine_type") or "",
                    provider=provider,
                )
            except Exception:
                skipped += 1
                continue

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
    if rules_created + rules_updated > 0:
        invalidate_dynamic_rules_cache()

    return {
        "rules_created": rules_created,
        "rules_updated": rules_updated,
        "skipped": skipped,
        "feedback_processed": len(processed_urls),
        "new_rules": new_rules,
    }
