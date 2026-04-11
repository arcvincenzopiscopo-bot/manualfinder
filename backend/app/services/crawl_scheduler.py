"""
Crawl Scheduler: job notturno che cerca automaticamente manuali per le macchine
più analizzate con fonte_tipo='fallback_ai'.

Viene avviato all'avvio dell'app (main.py on_startup) e gira alle 02:00 ogni notte.
Usa APScheduler AsyncIOScheduler per condividere l'event loop con FastAPI.
"""
import asyncio
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_scheduler = None  # Lazy init — evita import APScheduler se non installato


# ── Nightly job ───────────────────────────────────────────────────────────────

async def _nightly_crawl_job() -> None:
    """
    Prende le 20 macchine più analizzate con fonte_tipo='fallback_ai' negli ultimi 7 giorni.
    Per ognuna, tenta il crawl se non già in cache.
    Rate limit: 2 secondi tra un download e il successivo.
    """
    logger.info("Crawl scheduler: avvio job notturno")
    rows = _get_priority_queue()
    if not rows:
        logger.info("Crawl scheduler: nessuna macchina in coda")
        return

    from app.services.manual_crawler import crawl_for_manual, get_cached_manual

    found = 0
    skipped = 0
    errors = 0

    for brand, model, machine_type in rows:
        if not brand or not model:
            continue

        # Skip se già in cache
        if get_cached_manual(brand, model, machine_type):
            skipped += 1
            continue

        try:
            result = await crawl_for_manual(brand, model, machine_type)
            if result:
                found += 1
                logger.info("Crawl OK: %s %s → %s", brand, model, result.get("pdf_url", ""))
            else:
                logger.debug("Crawl no result: %s %s", brand, model)
        except Exception as e:
            errors += 1
            logger.warning("Crawl error: %s %s — %s", brand, model, e)

        await asyncio.sleep(2)  # rate limiting tra download

    logger.info(
        "Crawl scheduler: completato — trovati=%d, skippati=%d, errori=%d",
        found, skipped, errors,
    )


def _get_priority_queue() -> list[tuple[str, str, Optional[str]]]:
    """
    Recupera le macchine da crawlare da scan_log (psycopg2 sincrono).
    Priorità: più analizzate con fallback_ai negli ultimi 7 giorni.
    """
    if not settings.database_url:
        return []
    try:
        import psycopg2
        conn = psycopg2.connect(settings.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT brand, model, machine_type, COUNT(*) as cnt
                    FROM scan_log
                    WHERE fonte_tipo = 'fallback_ai'
                      AND ts > NOW() - INTERVAL '7 days'
                      AND brand IS NOT NULL
                      AND model IS NOT NULL
                    GROUP BY brand, model, machine_type
                    ORDER BY cnt DESC
                    LIMIT 20
                """)
                rows = cur.fetchall()
        finally:
            conn.close()
        return [(r[0], r[1], r[2]) for r in rows]
    except Exception as e:
        logger.debug("_get_priority_queue: %s", e)
        return []


# ── Avvio / stop scheduler ────────────────────────────────────────────────────

def start_scheduler() -> None:
    """
    Avvia l'AsyncIOScheduler. Chiamare da on_startup di FastAPI.
    Fallisce silenziosamente se APScheduler non è installato.
    """
    global _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        _scheduler = AsyncIOScheduler(timezone="Europe/Rome")
        _scheduler.add_job(
            _nightly_crawl_job,
            trigger="cron",
            hour=2,
            minute=0,
            id="nightly_crawl",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("Crawl scheduler avviato — job notturno alle 02:00")
    except ImportError:
        logger.warning("APScheduler non installato — crawl scheduler disabilitato")
    except Exception as e:
        logger.warning("Crawl scheduler non avviato: %s", e)


def stop_scheduler() -> None:
    """Ferma lo scheduler. Chiamare da on_shutdown di FastAPI."""
    global _scheduler
    if _scheduler and _scheduler.running:
        try:
            _scheduler.shutdown(wait=False)
            logger.info("Crawl scheduler fermato")
        except Exception:
            pass
