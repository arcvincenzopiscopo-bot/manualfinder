"""
Servizio di logging delle analisi targa completate.

Ogni analisi completata (step "complete" nel pipeline SSE) viene registrata
nella tabella `scan_log` con tutti i dati utili per batch futuri:
  - identificazione macchina (brand, model, machine_type, serial_number, year)
  - risultato ricerca (inail_url, producer_url, fonte_tipo)
  - flag qualità (is_fallback_ai, is_ante_ce, is_allegato_v)
  - safety alerts trovati

Le foto delle etichette vengono conservate nella tabella `scan_images` (FK → scan_log.id):
  - compresse a max 800px JPEG q=65 (~60-100 KB per immagine)
  - cancellate automaticamente dopo 30 giorni (le righe scan_log rimangono)
  - servite via GET /admin/scan-log/{id}/image

Uso batch tipico:
  SELECT * FROM scan_log WHERE fonte_tipo = 'fallback_ai' ORDER BY ts DESC
  → lista di macchine per cui non è stato trovato nessun manuale → retry search
"""

import base64
import io
import logging
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
    session_id      TEXT,

    -- Flag admin: nascosta dal pannello (non cancellata dal DB)
    dismissed       BOOL NOT NULL DEFAULT false
)
"""

_CREATE_IDX = [
    "CREATE INDEX IF NOT EXISTS scan_log_ts_idx ON scan_log (ts DESC)",
    "CREATE INDEX IF NOT EXISTS scan_log_brand_model_idx ON scan_log (brand, model)",
    "CREATE INDEX IF NOT EXISTS scan_log_fonte_idx ON scan_log (fonte_tipo)",
    "CREATE INDEX IF NOT EXISTS scan_log_machine_type_idx ON scan_log (machine_type)",
]

_DDL_IMAGES = """
CREATE TABLE IF NOT EXISTS scan_images (
    scan_log_id  INT PRIMARY KEY REFERENCES scan_log(id) ON DELETE CASCADE,
    image_data   BYTEA NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
)
"""

_tables_ensured = False


def _get_conn():
    import psycopg2
    return psycopg2.connect(settings.database_url)


def _ensure_table() -> bool:
    """Crea le tabelle e gli indici se non esistono. Ritorna False se DB non disponibile."""
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
            # Migration per tabelle esistenti
            cur.execute(
                "ALTER TABLE scan_log ADD COLUMN IF NOT EXISTS dismissed BOOL NOT NULL DEFAULT false"
            )
            cur.execute(_DDL_IMAGES)
            # Cleanup automatico: rimuovi immagini più vecchie di 30 giorni
            cur.execute(
                """
                DELETE FROM scan_images
                WHERE created_at < NOW() - INTERVAL '30 days'
                """
            )
        conn.commit()
        conn.close()
        _tables_ensured = True
        return True
    except Exception as e:
        logger.warning("scan_log: impossibile creare tabella: %s", e)
        return False


def _compress_image(image_base64: str, max_size: int = 800, quality: int = 65) -> Optional[bytes]:
    """
    Comprime un'immagine base64 in JPEG ridotto (max 800px, q=65).
    Tipicamente riduce da ~3 MB a ~60-100 KB.
    Ritorna None se fallisce (non blocca il flusso principale).
    """
    try:
        from PIL import Image
        data = image_base64
        if ',' in data:
            data = data.split(',', 1)[1]
        img_bytes = base64.b64decode(data)
        img = Image.open(io.BytesIO(img_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format='JPEG', quality=quality, optimize=True)
        return out.getvalue()
    except Exception as e:
        logger.warning("scan_log: compress_image fallito: %s", e)
        return None


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
) -> Optional[int]:
    """
    Registra una scansione completata. Non-blocking: non solleva eccezioni.
    Ritorna l'ID della riga inserita (per collegare l'immagine), o None se fallisce.
    """
    if not _ensure_table():
        return None
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
                RETURNING id
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
            scan_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        logger.debug("scan_log: registrata scansione %s %s (fonte: %s, id: %s)", brand, model, fonte_tipo, scan_id)
        return scan_id
    except Exception as e:
        logger.warning("scan_log: errore insert: %s", e)
        return None


def store_scan_image(scan_log_id: int, image_base64: str) -> bool:
    """
    Salva la foto dell'etichetta compressa (JPEG 800px q=65) collegata a una riga scan_log.
    Non-blocking. Ritorna True se salvata con successo.
    """
    if not _ensure_table():
        return False
    compressed = _compress_image(image_base64)
    if not compressed:
        return False
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scan_images (scan_log_id, image_data)
                VALUES (%s, %s)
                ON CONFLICT (scan_log_id) DO UPDATE SET image_data = EXCLUDED.image_data, created_at = NOW()
                """,
                (scan_log_id, compressed),
            )
        conn.commit()
        conn.close()
        logger.debug("scan_log: immagine salvata per scan_id=%s (%d KB)", scan_log_id, len(compressed) // 1024)
        return True
    except Exception as e:
        logger.warning("scan_log: errore salvataggio immagine per id=%s: %s", scan_log_id, e)
        return False


def get_scan_image(scan_log_id: int) -> Optional[bytes]:
    """Ritorna i bytes JPEG dell'immagine per una scansione, o None se non disponibile."""
    if not _ensure_table():
        return None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT image_data FROM scan_images WHERE scan_log_id = %s",
                (scan_log_id,),
            )
            row = cur.fetchone()
        conn.close()
        return bytes(row[0]) if row else None
    except Exception as e:
        logger.warning("scan_log: errore lettura immagine id=%s: %s", scan_log_id, e)
        return None


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


def dismiss_scan(scan_id: int) -> bool:
    """
    Nasconde una scansione dal pannello admin (imposta dismissed=true).
    Non cancella la riga dal DB — rimane disponibile per batch e analytics.
    """
    if not _ensure_table():
        return False
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("UPDATE scan_log SET dismissed = true WHERE id = %s", (scan_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("scan_log.dismiss_scan(%s): %s", scan_id, e)
        return False


def get_admin_scans(
    limit: int = 100,
    fonte_filter: Optional[str] = None,
    include_dismissed: bool = False,
) -> list[dict]:
    """
    Lista scansioni per il pannello admin.
    fonte_filter=None → tutte; "fallback_ai" → solo senza manuale trovato.
    include_dismissed=False → nasconde le righe già ignorate dall'admin.
    """
    if not _ensure_table():
        return []
    try:
        conn = _get_conn()
        conditions = []
        params: list = []
        if fonte_filter:
            conditions.append("fonte_tipo = %s")
            params.append(fonte_filter)
        if not include_dismissed:
            conditions.append("dismissed = false")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sl.id, sl.ts, sl.brand, sl.model, sl.machine_type, sl.serial_number, sl.machine_year,
                       sl.fonte_tipo, sl.inail_url, sl.producer_url,
                       sl.is_fallback_ai, sl.is_ante_ce, sl.is_allegato_v, sl.dismissed,
                       EXISTS(SELECT 1 FROM scan_images si WHERE si.scan_log_id = sl.id) AS has_image
                FROM scan_log sl
                {where}
                ORDER BY sl.ts DESC
                LIMIT %s
                """,
                params,
            )
            cols = [d[0] for d in cur.description]
            rows = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                # Serializza timestamp come stringa ISO
                if d.get("ts"):
                    d["ts"] = d["ts"].isoformat()
                rows.append(d)
        conn.close()
        return rows
    except Exception as e:
        logger.warning("scan_log.get_admin_scans: %s", e)
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
