"""
Manual Crawler: ricerca, scarica e mette in cache manuali PDF per brand/modello.

Flusso:
  1. get_cached_manual() — cerca in manual_cache (sincrono, psycopg2)
  2. crawl_for_manual() — ricerca web + download + persist (asincrono)

Riusa search_service.search_manual() per la ricerca — non reimplementa il motore.
"""
import hashlib
import logging
import os
import re
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ── Path storage PDF ──────────────────────────────────────────────────────────

def _manuals_dir() -> str:
    if os.environ.get("RENDER"):
        return "/opt/render/project/data/manuals"
    return os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "manuals")


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_conn():
    import psycopg2
    return psycopg2.connect(settings.database_url)


def _ensure_table() -> None:
    """Crea manual_cache IF NOT EXISTS. Pattern identico a scan_log_service."""
    if not settings.database_url:
        return
    try:
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS manual_cache (
                        id          SERIAL PRIMARY KEY,
                        brand       TEXT NOT NULL,
                        model       TEXT NOT NULL,
                        machine_type TEXT,
                        pdf_url     TEXT NOT NULL UNIQUE,
                        file_path   TEXT,
                        file_hash   TEXT,
                        source_type TEXT DEFAULT 'manufacturer',
                        safety_score INT DEFAULT 0,
                        crawled_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                        expires_at  TIMESTAMP NOT NULL DEFAULT NOW() + INTERVAL '30 days'
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS manual_cache_brand_model_idx
                        ON manual_cache (LOWER(brand), LOWER(model))
                """)
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("manual_cache table init: %s", e)


# ── Cache lookup (sincrono) ───────────────────────────────────────────────────

def get_cached_manual(
    brand: str,
    model: str,
    machine_type: Optional[str] = None,
) -> Optional[dict]:
    """
    Cerca un manuale valido in manual_cache.
    Rispetta expires_at. Restituisce dict con {pdf_url, source_type, file_path} o None.
    """
    if not settings.database_url:
        return None
    try:
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pdf_url, source_type, file_path, safety_score
                    FROM manual_cache
                    WHERE LOWER(brand) = LOWER(%s)
                      AND LOWER(model) = LOWER(%s)
                      AND expires_at > NOW()
                    ORDER BY safety_score DESC
                    LIMIT 1
                    """,
                    (brand, model),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        if row:
            return {
                "pdf_url": row[0],
                "source_type": row[1],
                "file_path": row[2],
                "safety_score": row[3],
            }
    except Exception as e:
        logger.debug("get_cached_manual: %s", e)
    return None


# ── Crawler (asincrono) ───────────────────────────────────────────────────────

async def crawl_for_manual(
    brand: str,
    model: str,
    machine_type: Optional[str] = None,
) -> Optional[dict]:
    """
    Cerca via search_service → scarica il primo PDF valido → persiste in manual_cache.
    Restituisce entry dict (stessa struttura di get_cached_manual) o None se non trovato.
    """
    # 1. Cache hit → ritorna subito
    cached = get_cached_manual(brand, model, machine_type)
    if cached:
        return cached

    # 2. Ricerca web via search_service
    from app.services.search_service import search_manual
    try:
        results = await search_manual(brand, model, machine_type)
    except Exception as e:
        logger.warning("crawl_for_manual search fallita per %s %s: %s", brand, model, e)
        return None

    # 3. Filtra PDF con score ≥ 30 — già ordinati per relevance_score
    pdf_candidates = [r for r in results if r.is_pdf and r.relevance_score >= 30]
    if not pdf_candidates:
        # Fallback: cerca anche i non-pdf segnati come pdf nell'URL
        pdf_candidates = [r for r in results if ".pdf" in r.url.lower()]

    for candidate in pdf_candidates[:3]:  # max 3 tentativi
        result = await _download_and_persist(
            brand=brand,
            model=model,
            machine_type=machine_type,
            url=candidate.url,
            source_type=candidate.source_type,
            safety_score=candidate.relevance_score,
        )
        if result:
            return result

    logger.info("crawl_for_manual: nessun PDF valido trovato per %s %s", brand, model)
    return None


async def _download_and_persist(
    brand: str,
    model: str,
    machine_type: Optional[str],
    url: str,
    source_type: str,
    safety_score: int,
) -> Optional[dict]:
    """
    Scarica il PDF dall'URL, verifica che sia un PDF valido (>= 3 pagine),
    salva su disco e persiste la riga in manual_cache.
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "ManualFinder/1.0"})
            if resp.status_code != 200:
                return None
            content = resp.content

        # Verifica che sia un PDF
        if not content.startswith(b"%PDF"):
            return None

        # Verifica numero pagine minimo tramite PyMuPDF
        try:
            import fitz
            doc = fitz.open(stream=content, filetype="pdf")
            page_count = len(doc)
            doc.close()
            if page_count < 3:
                return None
        except Exception:
            return None  # Non riuscito ad aprire — skip

        # Salva file su disco
        file_path = _save_pdf(brand, model, url, content)

        # Persisti in DB
        file_hash = hashlib.sha256(content).hexdigest()
        _persist_to_cache(
            brand=brand,
            model=model,
            machine_type=machine_type,
            pdf_url=url,
            file_path=file_path,
            file_hash=file_hash,
            source_type=source_type,
            safety_score=safety_score,
        )

        return {
            "pdf_url": url,
            "source_type": source_type,
            "file_path": file_path,
            "safety_score": safety_score,
        }

    except Exception as e:
        logger.debug("_download_and_persist %s: %s", url, e)
        return None


def _save_pdf(brand: str, model: str, url: str, content: bytes) -> Optional[str]:
    """Salva il PDF su disco. Restituisce il path o None se fallisce."""
    try:
        directory = _manuals_dir()
        os.makedirs(directory, exist_ok=True)
        # Nome file deterministico da brand + model + hash URL
        slug = re.sub(r"[^a-z0-9_-]", "_", f"{brand}_{model}".lower())[:50]
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"{slug}_{url_hash}.pdf"
        file_path = os.path.join(directory, filename)
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path
    except Exception as e:
        logger.debug("_save_pdf: %s", e)
        return None


def _persist_to_cache(
    brand: str,
    model: str,
    machine_type: Optional[str],
    pdf_url: str,
    file_path: Optional[str],
    file_hash: str,
    source_type: str,
    safety_score: int,
) -> None:
    """Upsert in manual_cache. Aggiorna expires_at e safety_score se già presente."""
    if not settings.database_url:
        return
    try:
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO manual_cache
                        (brand, model, machine_type, pdf_url, file_path, file_hash,
                         source_type, safety_score, crawled_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW() + INTERVAL '30 days')
                    ON CONFLICT (pdf_url) DO UPDATE SET
                        file_path    = EXCLUDED.file_path,
                        file_hash    = EXCLUDED.file_hash,
                        safety_score = GREATEST(manual_cache.safety_score, EXCLUDED.safety_score),
                        crawled_at   = NOW(),
                        expires_at   = NOW() + INTERVAL '30 days'
                    """,
                    (brand, model, machine_type, pdf_url, file_path, file_hash,
                     source_type, safety_score),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("_persist_to_cache: %s", e)


# ── Init tabella al primo import ──────────────────────────────────────────────
try:
    _ensure_table()
except Exception:
    pass
