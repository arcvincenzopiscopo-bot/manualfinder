"""
Ottimizzatore automatico dei prompt per tipo macchina.
Legge quality_log + manual_feedback, individua pattern di scarsa qualità,
chiede all'AI (Haiku/Gemini-Flash) di migliorare le regole prompt in machine_prompt_rules.

Trigger: chiamato da feedback_analyzer_service.run_analysis() oppure manualmente.
"""
import json
import logging
from collections import Counter
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Soglie per decidere se un tipo macchina ha bisogno di miglioramento
_MIN_ANALYSES = 5          # almeno N analisi negli ultimi 30 giorni
_MIN_ISSUE_RATE = 0.3      # almeno 30% delle analisi con almeno 1 issue
_MIN_AVG_RISCHI = 3.0      # media rischi estratti inferiore a questo valore


async def run_optimizer(provider: str, min_analyses: int = _MIN_ANALYSES) -> dict:
    """
    Analizza quality_log + feedback per ogni tipo macchina e migliora i prompt rule
    per i tipi con qualità sistematicamente bassa.

    Ritorna: {types_analyzed, types_improved, improvements: [{machine_type, changes_summary}]}
    """
    if not settings.database_url:
        return {"types_analyzed": 0, "types_improved": 0, "improvements": []}

    try:
        quality_stats = _load_quality_stats(min_analyses)
        feedback_stats = _load_feedback_stats()
    except Exception as e:
        logger.warning("prompt_optimizer: errore caricamento dati — %s", e)
        return {"types_analyzed": 0, "types_improved": 0, "improvements": []}

    types_analyzed = len(quality_stats)
    types_improved = 0
    improvements = []

    for machine_type, stats in quality_stats.items():
        try:
            needs_improvement = (
                stats["issue_rate"] >= _MIN_ISSUE_RATE
                or stats["avg_rischi"] < _MIN_AVG_RISCHI
                or stats["has_high_issue_rate"] >= 0.2  # 20%+ analisi con issue gravi
            )
            if not needs_improvement:
                continue

            current_rule = _load_current_rule(machine_type)
            fb = feedback_stats.get(machine_type, {})
            improved = await _improve_rule(machine_type, stats, fb, current_rule, provider)
            if improved:
                types_improved += 1
                improvements.append({
                    "machine_type": machine_type,
                    "changes_summary": improved.get("quality_notes", "Regola migliorata"),
                })
        except Exception as e:
            logger.warning("prompt_optimizer: errore per '%s' — %s", machine_type, e)
            continue

    logger.info(
        "prompt_optimizer: analizzati %d tipi, migliorati %d",
        types_analyzed, types_improved,
    )
    return {
        "types_analyzed": types_analyzed,
        "types_improved": types_improved,
        "improvements": improvements,
    }


async def improve_single(machine_type: str, provider: str) -> Optional[dict]:
    """
    Migliora la regola prompt per un singolo tipo macchina.
    Usato dall'endpoint admin POST /manuals/prompt-rules/{machine_type}/improve.
    Ritorna None se non ci sono dati sufficienti.
    """
    if not settings.database_url or not machine_type:
        return None
    try:
        quality_stats = _load_quality_stats(min_analyses=1, machine_type_filter=machine_type)
        if not quality_stats:
            return None
        stats = quality_stats.get(machine_type.lower().strip())
        if not stats:
            return None
        feedback_stats = _load_feedback_stats(machine_type_filter=machine_type)
        fb = feedback_stats.get(machine_type.lower().strip(), {})
        current_rule = _load_current_rule(machine_type)
        return await _improve_rule(machine_type, stats, fb, current_rule, provider)
    except Exception as e:
        logger.warning("prompt_optimizer.improve_single('%s') fallito: %s", machine_type, e)
        return None


async def _improve_rule(
    machine_type: str,
    stats: dict,
    feedback: dict,
    current_rule: Optional[dict],
    provider: str,
) -> Optional[dict]:
    """Costruisce il meta-prompt di miglioramento, chiama AI, salva il risultato."""
    # Ricostruisce i top issue come testo leggibile
    issue_counter = Counter()
    for issue_list in stats.get("all_issues", []):
        if isinstance(issue_list, list):
            for iss in issue_list:
                if isinstance(iss, dict) and iss.get("code"):
                    issue_counter[iss["code"]] += 1
        elif isinstance(issue_list, str):
            issue_counter[issue_list] += 1
    top_issues_str = ", ".join(
        f"{code} (×{count})" for code, count in issue_counter.most_common(5)
    ) or "nessuno rilevato"

    # Feedback summary
    fb_lines = []
    for fb_type, count in feedback.items():
        label_map = {
            "not_a_manual": "URL segnalati come non-manuale",
            "wrong_category": "URL con categoria errata",
            "useful_other_category": "URL utile per altra categoria",
        }
        fb_lines.append(f"- {label_map.get(fb_type, fb_type)}: {count}")
    feedback_str = "\n".join(fb_lines) if fb_lines else "Nessun feedback disponibile"

    current_rule_str = json.dumps({
        k: v for k, v in (current_rule or {}).items()
        if k in ("extra_context", "specific_risks", "normative_refs", "inspection_focus")
    }, ensure_ascii=False, indent=2) if current_rule else "Nessuna regola esistente"

    prompt = f"""Sei un esperto di sicurezza sul lavoro italiano (D.Lgs. 81/2008, Direttiva Macchine 2006/42/CE).
Devi migliorare le regole di analisi per il tipo di macchina: "{machine_type}"

REGOLA ATTUALE:
{current_rule_str}

SEGNALI DI QUALITÀ (ultimi 30 giorni, {stats['n_analyses']} analisi):
- Media rischi estratti: {stats['avg_rischi']:.1f} (minimo atteso: 4)
- Media checklist items: {stats['avg_checklist']:.1f} (minimo atteso: 5)
- Tasso analisi con problemi: {stats['issue_rate']:.0%}
- Problemi più frequenti: {top_issues_str}

FEEDBACK ISPETTORI:
{feedback_str}

Basandoti sui segnali di qualità, migliora la regola per ottenere analisi più complete e accurate.
Se avg_rischi < 3: aggiungi rischi specifici mancanti in specific_risks.
Se issue_rate alta su wrong_category_content: raffina extra_context con caratteristiche distintive.
Se missing_verifiche_allegato7 frequente: includi in inspection_focus la verifica periodica.

Rispondi SOLO con JSON valido, nessun altro testo:
{{
  "extra_context": "...",
  "specific_risks": "...",
  "normative_refs": "...",
  "inspection_focus": "...",
  "quality_notes": "Modifiche apportate rispetto alla regola precedente: ..."
}}"""

    from app.services.prompt_rules_service import _call_ai_for_rule
    result = await _call_ai_for_rule(prompt, provider)
    if not result:
        return None

    # Salva la regola migliorata nel DB (ON CONFLICT DO UPDATE)
    _save_improved_rule(machine_type, result)

    # Invalida cache prompt_rules
    from app.services.prompt_rules_service import invalidate_cache
    invalidate_cache()

    return result


# ── DB helpers ────────────────────────────────────────────────────────────────

def _load_quality_stats(
    min_analyses: int,
    machine_type_filter: Optional[str] = None,
) -> dict[str, dict]:
    """
    Legge quality_log degli ultimi 30 giorni, raggruppa per machine_type.
    Ritorna solo i tipi con >= min_analyses analisi.
    """
    import psycopg2, psycopg2.extras
    filter_clause = ""
    params: list = [min_analyses]
    if machine_type_filter:
        filter_clause = "AND LOWER(machine_type) LIKE %s"
        params.insert(0, f"%{machine_type_filter.lower().strip()}%")
        params = [f"%{machine_type_filter.lower().strip()}%", min_analyses]

    sql = f"""
        SELECT
            LOWER(TRIM(machine_type)) AS mt,
            COUNT(*) AS n_analyses,
            AVG(n_rischi) AS avg_rischi,
            AVG(n_checklist) AS avg_checklist,
            AVG(n_issues::float) AS avg_issues,
            SUM(CASE WHEN n_issues > 0 THEN 1 ELSE 0 END)::float / COUNT(*) AS issue_rate,
            SUM(CASE WHEN has_high THEN 1 ELSE 0 END)::float / COUNT(*) AS has_high_issue_rate,
            array_agg(issues) AS all_issues
        FROM quality_log
        WHERE ts > now() - interval '30 days'
          AND machine_type IS NOT NULL AND machine_type != ''
          {filter_clause}
        GROUP BY LOWER(TRIM(machine_type))
        HAVING COUNT(*) >= %s
    """
    conn = psycopg2.connect(settings.database_url)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.close()
    return {
        r["mt"]: {
            "n_analyses": r["n_analyses"],
            "avg_rischi": float(r["avg_rischi"] or 0),
            "avg_checklist": float(r["avg_checklist"] or 0),
            "avg_issues": float(r["avg_issues"] or 0),
            "issue_rate": float(r["issue_rate"] or 0),
            "has_high_issue_rate": float(r["has_high_issue_rate"] or 0),
            "all_issues": r["all_issues"] or [],
        }
        for r in rows
        if r["mt"]
    }


def _load_feedback_stats(
    machine_type_filter: Optional[str] = None,
) -> dict[str, dict[str, int]]:
    """Legge manual_feedback degli ultimi 30 giorni, raggruppa per machine_type + feedback_type."""
    import psycopg2, psycopg2.extras
    params: list = []
    filter_clause = ""
    if machine_type_filter:
        filter_clause = "AND LOWER(machine_type) LIKE %s"
        params = [f"%{machine_type_filter.lower().strip()}%"]

    sql = f"""
        SELECT LOWER(TRIM(machine_type)) AS mt, feedback_type, COUNT(*) AS cnt
        FROM manual_feedback
        WHERE ts > now() - interval '30 days'
          AND machine_type IS NOT NULL AND machine_type != ''
          {filter_clause}
        GROUP BY LOWER(TRIM(machine_type)), feedback_type
    """
    conn = psycopg2.connect(settings.database_url)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.close()
    result: dict[str, dict[str, int]] = {}
    for r in rows:
        mt = r["mt"]
        if mt not in result:
            result[mt] = {}
        result[mt][r["feedback_type"]] = int(r["cnt"])
    return result


def _load_current_rule(machine_type: str) -> Optional[dict]:
    """Legge la regola corrente dal DB (bypass cache per avere dati freschi)."""
    import psycopg2, psycopg2.extras
    try:
        conn = psycopg2.connect(settings.database_url)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM machine_prompt_rules WHERE LOWER(machine_type) = %s LIMIT 1",
                (machine_type.lower().strip(),),
            )
            row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def _save_improved_rule(machine_type: str, rule: dict) -> None:
    """Salva la regola migliorata. Usa ON CONFLICT DO UPDATE per aggiornare l'esistente."""
    import psycopg2
    try:
        conn = psycopg2.connect(settings.database_url)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO machine_prompt_rules
                    (machine_type, extra_context, specific_risks, normative_refs,
                     inspection_focus, quality_notes, is_active, source,
                     improvement_count, last_improved_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, true, 'ai_improved', 1, now(), now())
                ON CONFLICT (machine_type) DO UPDATE SET
                    extra_context     = EXCLUDED.extra_context,
                    specific_risks    = EXCLUDED.specific_risks,
                    normative_refs    = EXCLUDED.normative_refs,
                    inspection_focus  = EXCLUDED.inspection_focus,
                    quality_notes     = EXCLUDED.quality_notes,
                    source            = CASE
                                          WHEN machine_prompt_rules.source = 'manual'
                                          THEN 'manual'  -- non toccare le regole manuali
                                          ELSE 'ai_improved'
                                        END,
                    improvement_count = COALESCE(machine_prompt_rules.improvement_count, 0) + 1,
                    last_improved_at  = now(),
                    updated_at        = now()
                """,
                (
                    machine_type.lower().strip(),
                    rule.get("extra_context"),
                    rule.get("specific_risks"),
                    rule.get("normative_refs"),
                    rule.get("inspection_focus"),
                    rule.get("quality_notes"),
                ),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("prompt_optimizer._save_improved_rule('%s') fallito: %s", machine_type, e)
