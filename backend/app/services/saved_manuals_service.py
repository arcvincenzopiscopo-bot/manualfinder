"""
Servizio per il salvataggio e la ricerca di manuali confermati dagli ispettori.
Usa connessione diretta PostgreSQL a Supabase (transaction pooler).
"""
import logging
from typing import Optional, List
import psycopg2
import psycopg2.extras
from app.config import settings
from app.utils.errors import log_and_swallow

_logger = logging.getLogger(__name__)


def _get_conn():
    from app.services.db_pool import get_conn
    return get_conn()


def _canonical_machine_type(mt: str) -> str:
    """
    Normalizza un machine_type al nome canonico tramite machine_aliases DB.
    Import lazy per evitare cicli. Ritorna la stringa normalizzata se non mappata.
    """
    try:
        from app.services.machine_type_service import resolve_machine_type_id, get_name_by_id
        mt_id = resolve_machine_type_id(mt or "")
        if mt_id:
            name = get_name_by_id(mt_id)
            if name:
                return name
    except Exception as e:
        log_and_swallow(_logger, e, context="canonical machine type")
    return (mt or "").lower().strip()


import time as _time
import threading as _threading

_cache_lock = _threading.RLock()

# ── Cache URL bloccati ────────────────────────────────────────────────────────
# Blocco assoluto: non sono manuali d'uso (brochure, cataloghi, ecc.)
_blocked_urls_cache: set[str] = set()
_blocked_urls_ts: float = 0.0

# Blocco contestuale: sono manuali ma per categoria diversa — (url, machine_type)
_context_blocked_cache: set[tuple[str, str]] = set()
_context_blocked_ts: float = 0.0

# Blocco contestuale per ID FK — (url, machine_type_id)
_context_blocked_id_cache: set[tuple[str, int]] = set()
_context_blocked_id_ts: float = 0.0

_BLOCKED_CACHE_TTL = 900  # 15 minuti
_TRIGRAM_MIN_SIMILARITY = 0.35


def get_blocked_urls() -> set[str]:
    """
    Restituisce il set degli URL segnalati dagli ispettori come NON manuali d'uso
    (feedback_type = 'not_a_manual'). Blocco assoluto: questi URL vengono scartati
    da qualsiasi ricerca indipendentemente dal tipo macchina.
    Cache in-memory TTL 15 min. Fallisce silenziosamente.
    """
    global _blocked_urls_cache, _blocked_urls_ts
    with _cache_lock:
        now = _time.monotonic()
        if now - _blocked_urls_ts < _BLOCKED_CACHE_TTL:
            return _blocked_urls_cache
        if not settings.database_url:
            return set()
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT url FROM manual_feedback WHERE feedback_type = 'not_a_manual'"
                    )
                    urls = {row[0] for row in cur.fetchall()}
            _blocked_urls_cache = urls
            _blocked_urls_ts = now
            return urls
        except Exception as e:
            log_and_swallow(_logger, e, context="load blocked urls")
            return _blocked_urls_cache


def get_context_blocked_urls() -> set[tuple[str, str]]:
    """
    Restituisce il set di (url, machine_type) segnalati come 'wrong_category':
    sono manuali validi ma per una categoria diversa da quella cercata.
    Vanno bloccati solo per quel tipo macchina specifico — possono essere utili altrove.
    Cache in-memory TTL 15 min. Fallisce silenziosamente.
    """
    global _context_blocked_cache, _context_blocked_ts
    with _cache_lock:
        now = _time.monotonic()
        if now - _context_blocked_ts < _BLOCKED_CACHE_TTL:
            return _context_blocked_cache
        if not settings.database_url:
            return set()
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT DISTINCT url, machine_type FROM manual_feedback
                        WHERE feedback_type = 'wrong_category'
                          AND machine_type IS NOT NULL AND machine_type != ''
                        """
                    )
                    pairs = {(row[0], row[1].lower().strip()) for row in cur.fetchall()}
            _context_blocked_cache = pairs
            _context_blocked_ts = now
            return pairs
        except Exception as e:
            log_and_swallow(_logger, e, context="load context blocked urls")
            return _context_blocked_cache


def get_context_blocked_url_ids() -> set[tuple[str, int]]:
    """
    Restituisce il set di (url, machine_type_id) per feedback 'wrong_category'.
    Versione ID-based di get_context_blocked_urls(). Cache TTL 15 min.
    """
    global _context_blocked_id_cache, _context_blocked_id_ts
    with _cache_lock:
        now = _time.monotonic()
        if now - _context_blocked_id_ts < _BLOCKED_CACHE_TTL:
            return _context_blocked_id_cache
        if not settings.database_url:
            return set()
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT DISTINCT url, machine_type_id FROM manual_feedback
                        WHERE feedback_type = 'wrong_category'
                          AND machine_type_id IS NOT NULL
                        """
                    )
                    pairs = {(row[0], row[1]) for row in cur.fetchall()}
            _context_blocked_id_cache = pairs
            _context_blocked_id_ts = now
            return pairs
        except Exception as e:
            log_and_swallow(_logger, e, context="load context blocked url ids")
            return _context_blocked_id_cache


def delete_manual_by_url(url: str) -> bool:
    """
    Rimuove un manuale da saved_manuals dato l'URL.
    Chiamato quando un ispettore segnala un URL precedentemente salvato come 'not_a_manual'.
    Ritorna True se almeno una riga è stata eliminata.
    """
    if not settings.database_url or not url:
        return False
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM saved_manuals WHERE url = %s", (url,))
                deleted = cur.rowcount
            conn.commit()
        return deleted > 0
    except Exception as e:
        log_and_swallow(_logger, e, context="delete manual by url")
        return False


def check_url_saved(url: str) -> bool:
    """Ritorna True se l'URL è già presente in saved_manuals."""
    if not settings.database_url:
        return False
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM saved_manuals WHERE url = %s LIMIT 1", (url,))
                return cur.fetchone() is not None
    except Exception as e:
        log_and_swallow(_logger, e, context="check url saved")
        return False


def save_feedback(
    url: str,
    feedback_type: str,  # 'not_a_manual' | 'wrong_category' | 'useful_other_category'
    brand: Optional[str] = None,
    model: Optional[str] = None,
    machine_type: Optional[str] = None,
    machine_type_id: Optional[int] = None,
    useful_for_type: Optional[str] = None,
    useful_for_type_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> None:
    """
    Salva il feedback dell'ispettore su un documento trovato.
    feedback_type:
      'not_a_manual'         — non è un manuale d'uso/manutenzione (es. brochure, catalogo)
      'wrong_category'       — è un manuale d'uso ma per una categoria diversa dalla macchina cercata
      'useful_other_category'— manuale utile ma per un tipo macchina diverso (specificato in useful_for_type)
    Non solleva eccezioni.
    """
    if not settings.database_url:
        return
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO manual_feedback
                        (url, brand, model, machine_type, machine_type_id,
                         feedback_type, useful_for_type_id, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (url, brand, model, machine_type, machine_type_id,
                     feedback_type, useful_for_type_id, notes),
                )
                conn.commit()
    except Exception as e:
        log_and_swallow(_logger, e, context="save feedback")


def count_unanalyzed_feedback() -> int:
    """
    Conta i feedback non ancora convertiti in regole in url_filter_rules.
    Usato per decidere se triggerare l'analisi automatica.
    """
    if not settings.database_url:
        return 0
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM manual_feedback
                    WHERE feedback_type IN ('not_a_manual', 'wrong_category', 'useful_other_category')
                      AND url NOT IN (
                          SELECT unnest(source_urls) FROM url_filter_rules
                      )
                    """
                )
                row = cur.fetchone()
                return row[0] if row else 0
    except Exception as e:
        log_and_swallow(_logger, e, context="count unanalyzed feedback")
        return 0


def save_manual(data: dict) -> dict:
    """Inserisce un manuale salvato. Restituisce la riga inserita."""
    cols = list(data.keys())
    placeholders = ["%s"] * len(cols)
    sql = (
        f"INSERT INTO saved_manuals ({', '.join(cols)}) "
        f"VALUES ({', '.join(placeholders)}) "
        f"RETURNING *"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, list(data.values()))
            conn.commit()
            return dict(cur.fetchone())


def search_saved(
    machine_type: Optional[str] = None,
    machine_type_id: Optional[int] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 30,
) -> list:
    """
    Cerca manuali salvati per tipo macchina, brand o modello.
    machine_type_id ha priorità su machine_type (testo).
    Restituisce max `limit` risultati ordinati dal più recente.
    """
    conditions = []
    params = []

    if machine_type_id is not None:
        conditions.append("(machine_type_id = %s OR manual_machine_type ILIKE %s)")
        params.extend([machine_type_id, f"%{machine_type or ''}%"])
    elif machine_type:
        conditions.append("manual_machine_type ILIKE %s")
        params.append(f"%{machine_type}%")
    if brand:
        conditions.append("manual_brand ILIKE %s")
        params.append(f"%{brand}%")
    if model:
        conditions.append("manual_model ILIKE %s")
        params.append(f"%{model}%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM saved_manuals {where} ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def find_for_search(
    brand: str,
    model: str,
    machine_type: Optional[str],
    machine_type_id: Optional[int] = None,
) -> List[dict]:
    """
    Usato dalla pipeline di ricerca per trovare manuali salvati rilevanti.
    Restituisce due gruppi:
      1. Specifici per brand+model (confermati da un ispettore su quel modello)
      2. Generici per categoria/tipo macchina (riferimento di categoria)
    Fallisce silenziosamente se DATABASE_URL non è configurata o il DB non risponde.
    """
    if not settings.database_url:
        return []
    try:
        results: list[dict] = []
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

                # 1) Specifici: brand+model corrispondenti (escludi GENERICO)
                # Usa ILIKE substring + pg_trgm similarity per tollerare typo OCR
                cur.execute(
                    f"""
                    SELECT *,
                           'specific' AS _match_type,
                           (similarity(manual_brand, %s) + similarity(manual_model, %s)) AS _score
                    FROM saved_manuals
                    WHERE manual_brand NOT ILIKE 'GENERICO'
                      AND (manual_brand ILIKE %s OR similarity(manual_brand, %s) > {_TRIGRAM_MIN_SIMILARITY})
                      AND (manual_model ILIKE %s OR similarity(manual_model, %s) > {_TRIGRAM_MIN_SIMILARITY})
                    ORDER BY _score DESC, created_at DESC
                    LIMIT 5
                    """,
                    (brand, model,
                     f"%{brand}%", brand,
                     f"%{model}%", model),
                )
                specific_ids = []
                for row in cur.fetchall():
                    r = dict(row)
                    specific_ids.append(str(r["id"]))
                    results.append(r)

                # 2) Generici per categoria o machine_type match (escludi già trovati).
                # Preferisce match per ID FK, poi fallback testo ILIKE.
                if machine_type or machine_type_id is not None:
                    exclude = tuple(specific_ids) if specific_ids else ("__none__",)
                    canonical = _canonical_machine_type(machine_type or "")
                    mt_text = machine_type or ""
                    if machine_type_id is not None:
                        cur.execute(
                            f"""
                            SELECT *, 'generic' AS _match_type
                            FROM saved_manuals
                            WHERE (machine_type_id = %s
                                   OR manual_machine_type ILIKE %s
                                   OR manual_machine_type ILIKE %s
                                   OR search_machine_type ILIKE %s
                                   OR search_machine_type ILIKE %s
                                   OR similarity(manual_machine_type, %s) > {_TRIGRAM_MIN_SIMILARITY}
                                   OR similarity(search_machine_type, %s) > {_TRIGRAM_MIN_SIMILARITY})
                              AND id::text NOT IN %s
                            ORDER BY
                                CASE WHEN machine_type_id = %s THEN 0 ELSE 1 END,
                                CASE WHEN manual_brand ILIKE 'GENERICO' THEN 0 ELSE 1 END,
                                created_at DESC
                            LIMIT 5
                            """,
                            (
                                machine_type_id,
                                f"%{mt_text}%", f"%{canonical}%",
                                f"%{mt_text}%", f"%{canonical}%",
                                mt_text, mt_text,
                                exclude,
                                machine_type_id,
                            ),
                        )
                    else:
                        cur.execute(
                            f"""
                            SELECT *, 'generic' AS _match_type
                            FROM saved_manuals
                            WHERE (manual_machine_type ILIKE %s
                                   OR manual_machine_type ILIKE %s
                                   OR search_machine_type ILIKE %s
                                   OR search_machine_type ILIKE %s
                                   OR similarity(manual_machine_type, %s) > {_TRIGRAM_MIN_SIMILARITY}
                                   OR similarity(search_machine_type, %s) > {_TRIGRAM_MIN_SIMILARITY})
                              AND id::text NOT IN %s
                            ORDER BY
                                CASE WHEN manual_brand ILIKE 'GENERICO' THEN 0 ELSE 1 END,
                                created_at DESC
                            LIMIT 5
                            """,
                            (
                                f"%{mt_text}%", f"%{canonical}%",
                                f"%{mt_text}%", f"%{canonical}%",
                                mt_text, mt_text,
                                exclude,
                            ),
                        )
                    results.extend(dict(r) for r in cur.fetchall())

        # Rimuove URL segnalati dagli ispettori come non idonei
        # not_a_manual → blocco assoluto da qualsiasi ricerca
        blocked_abs = get_blocked_urls()
        if blocked_abs:
            results = [r for r in results if r.get("url") not in blocked_abs]

        # wrong_category → blocco contestuale: solo per il machine_type in cui è stato segnalato
        if machine_type_id is not None and results:
            ctx_blocked_ids = get_context_blocked_url_ids()
            if ctx_blocked_ids:
                results = [
                    r for r in results
                    if (r.get("url"), machine_type_id) not in ctx_blocked_ids
                ]
        elif machine_type and results:
            mt_lower = machine_type.lower().strip()
            ctx_blocked = get_context_blocked_urls()
            if ctx_blocked:
                results = [
                    r for r in results
                    if (r.get("url"), mt_lower) not in ctx_blocked
                ]

        return results
    except Exception as e:
        log_and_swallow(_logger, e, context="find for search")
        return []
