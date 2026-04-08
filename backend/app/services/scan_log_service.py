"""
Servizio di logging delle analisi targa completate.

Ogni analisi completata (step "complete" nel pipeline SSE) viene registrata
nella tabella `scan_log` con tutti i dati utili per batch futuri:
  - identificazione macchina (brand, model, machine_type, serial_number, year)
  - risultato ricerca (inail_url, producer_url, fonte_tipo)
  - flag qualità (is_fallback_ai, is_ante_ce, is_allegato_v)
  - safety alerts trovati

Uso batch tipico:
  SELECT * FROM scan_log WHERE fonte_tipo = 'fallback_ai' ORDER BY ts DESC
  → lista di macchine per cui non è stato trovato nessun manuale → retry search
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ── Schema ────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS scan_log (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Dati macchina (come confermati dall'utente prima del full analysis)
    brand           TEXT,
    model           TEXT,
    machine_type    TEXT,
    machine_type_id INT,
    serial_number   TEXT,
    machine_year    TEXT,

    -- Norme estratte dalla targa (OCR)
    norme           TEXT[] DEFAULT '{}',

    -- QR Code rilevati sulla targa
    qr_urls         TEXT[] DEFAULT '{}',

    -- Risultato ricerca
    inail_url       TEXT,
    producer_url    TEXT,
    producer_pages  INT DEFAULT 0,
    -- "pdf" | "inail" | "inail+produttore" | "fallback_ai" | "datasheet"
    fonte_tipo      TEXT,

    -- Flag qualità
    is_fallback_ai  BOOL NOT NULL DEFAULT false,
    is_ante_ce      BOOL NOT NULL DEFAULT false,
    is_allegato_v   BOOL NOT NULL DEFAULT false,

    -- Safety Gate EU
    safety_alerts_count INT DEFAULT 0,

    -- Metadati sessione (opzionale, dal header X-Session-ID se presente)
    session_id      TEXT
)
"""

_CREATE_IDX = [
    "CREATE INDEX IF NOT EXISTS scan_log_ts_idx ON scan_log (ts DESC)",
    "CREATE INDEX IF NOT EXISTS scan_log_brand_model_idx ON scan_log (brand, model)",
    "CREATE INDEX IF NOT EXISTS scan_log_fonte_idx ON scan_log (fonte_tipo)",
    "CREATE INDEX IF NOT EXISTS scan_log_machine_type_idx ON scan_log (machine_type)",
]

_tables_ensured = False


def _get_conn():
    import psycopg2
    return psycopg2.connect(settings.database_url)


def _ensure_table() -> bool:
    """Crea la tabella e gli indici se non esistono. Ritorna False se DB non disponibile."""
    global _tables_ensured
    if _tables_ensured:
        return True
    if not settings.database_url:
        return False
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(_DDL)
            for idx_sql in _CREATE_IDX:
                cur.execute(idx_sql)
        conn.commit()
        conn.close()
        _tables_ensured = True
        return True
    except Exception as e:
        logger.warning("scan_log: impossibile creare tabella: %s", e)
        return False


# ── Write ─────────────────────────────────────────────────────────────────────

def log_scan(
    brand: str,
    model: str,
    machine_type: Optional[str],
    machine_type_id: Optional[int],
    serial_number: Optional[str],
    machine_year: Optional[str],
    norme: list[str],
    qr_urls: list[str],
    inail_url: Optional[str],
    producer_url: Optional[str],
    producer_pages: int,
    fonte_tipo: Optional[str],
    is_ante_ce: bool,
    is_allegato_v: bool,
    safety_alerts_count: int,
    session_id: Optional[str] = None,
) -> None:
    """
    Registra una scansione completata. Non-blocking: non solleva eccezioni.
    Da chiamare dopo generate_safety_card() nel pipeline SSE.
    """
    if not _ensure_table():
        return
    is_fallback = fonte_tipo == "fallback_ai"
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scan_log (
                    brand, model, machine_type, machine_type_id,
                    serial_number, machine_year,
                    norme, qr_urls,
                    inail_url, producer_url, producer_pages, fonte_tipo,
                    is_fallback_ai, is_ante_ce, is_allegato_v,
                    safety_alerts_count, session_id
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
                """,
                (
                    brand or None, model or None, machine_type, machine_type_id,
                    serial_number or None, machine_year or None,
                    norme or [], qr_urls or [],
                    inail_url or None, producer_url or None, producer_pages, fonte_tipo,
                    is_fallback, is_ante_ce, is_allegato_v,
                    safety_alerts_count, session_id,
                ),
            )
        conn.commit()
        conn.close()
        logger.debug("scan_log: registrata scansione %s %s (fonte: %s)", brand, model, fonte_tipo)
    except Exception as e:
        logger.warning("scan_log: errore insert: %s", e)


# ── Read (per batch e admin) ──────────────────────────────────────────────────

def get_fallback_scans(limit: int = 200) -> list[dict]:
    """
    Ritorna le ultime `limit` scansioni senza manuale trovato (fallback_ai).
    Usato per costruire batch di retry ricerca manuale.
    Deduplica per (brand, model) — tiene solo la scansione più recente.
    """
    if not _ensure_table():
        return []
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (lower(brand), lower(model))
                    id, ts, brand, model, machine_type, machine_type_id,
                    serial_number, machine_year, norme, qr_urls
                FROM scan_log
                WHERE fonte_tipo = 'fallback_ai'
                ORDER BY lower(brand), lower(model), ts DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.warning("scan_log.get_fallback_scans: %s", e)
        return []


def get_stats() -> dict:
    """
    Statistiche aggregate per il pannello admin.
    """
    if not _ensure_table():
        return {}
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scan_log")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM scan_log WHERE fonte_tipo = 'fallback_ai'")
            fallback = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM scan_log WHERE fonte_tipo IN ('pdf','inail+produttore')")
            full_pdf = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM scan_log WHERE is_allegato_v = true")
            allegato_v = cur.fetchone()[0]
            cur.execute(
                """
                SELECT machine_type, COUNT(*) AS n
                FROM scan_log
                WHERE machine_type IS NOT NULL
                GROUP BY machine_type
                ORDER BY n DESC
                LIMIT 10
                """
            )
            top_types = [{"machine_type": r[0], "count": r[1]} for r in cur.fetchall()]
        conn.close()
        return {
            "total_scans": total,
            "fallback_ai_count": fallback,
            "full_pdf_count": full_pdf,
            "allegato_v_count": allegato_v,
            "top_machine_types": top_types,
        }
    except Exception as e:
        logger.warning("scan_log.get_stats: %s", e)
        return {}
