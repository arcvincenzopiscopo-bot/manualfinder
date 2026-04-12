"""
Feedback ispettori sulle schede sicurezza generate.
Distinto dall'esistente /manuals/feedback (che riguarda URL manuali).
Questo router raccoglie rating qualitativi sulle schede generate (strategia A–F).
"""
import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Feedback"])

# ── Opzioni problemi — ora in DB (config_lists:"problemi_options") ──────────
_FB_PROBLEMI_OPTIONS = [
    "norme_errate", "checklist_incompleta", "dati_macchina_sbagliati",
    "prescrizioni_inutilizzabili", "fonte_non_affidabile",
]


def _problemi_options() -> list:
    from app.services.config_service import get_list
    items = get_list("problemi_options", set(_FB_PROBLEMI_OPTIONS))
    return sorted(items) if items else _FB_PROBLEMI_OPTIONS


# Alias di compatibilità
PROBLEMI_OPTIONS = _FB_PROBLEMI_OPTIONS


# ── Modelli request / response ────────────────────────────────────────────────

class CardFeedbackRequest(BaseModel):
    brand: str
    model: str
    machine_type: Optional[str] = None
    machine_type_id: Optional[int] = None
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    problemi: List[str] = []
    note: Optional[str] = None
    strategy: Optional[str] = None    # 'A'..'F'
    fonte_tipo: Optional[str] = None  # 'pdf' | 'fallback_ai' | 'inail' | 'inail+produttore'


# ── Tabella DB ────────────────────────────────────────────────────────────────

def _ensure_feedback_table() -> None:
    if not settings.database_url:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(settings.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS card_feedback (
                        id          SERIAL PRIMARY KEY,
                        ts          TIMESTAMP NOT NULL DEFAULT NOW(),
                        brand       TEXT NOT NULL,
                        model       TEXT NOT NULL,
                        machine_type TEXT,
                        rating      INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
                        problemi    TEXT[],
                        note        TEXT,
                        strategy    TEXT,
                        fonte_tipo  TEXT
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS card_feedback_brand_model_idx
                        ON card_feedback (LOWER(brand), LOWER(model))
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS card_feedback_rating_idx
                        ON card_feedback (rating)
                """)
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("card_feedback table init: %s", e)


try:
    _ensure_feedback_table()
except Exception:
    pass


# ── Endpoint: submit feedback ─────────────────────────────────────────────────

@router.post("/card")
async def submit_card_feedback(body: CardFeedbackRequest):
    """
    Raccoglie il rating dell'ispettore su una scheda sicurezza generata.
    Se rating <= 2 e fonte_tipo = 'fallback_ai', avvia un crawl in background
    per cercare il manuale specifico.
    """
    if settings.database_url:
        try:
            import psycopg2
            # Auto-resolve machine_type_id se non fornito
            mt_id = body.machine_type_id
            if mt_id is None and body.machine_type:
                try:
                    from app.services.machine_type_service import resolve_machine_type_id
                    mt_id = resolve_machine_type_id(body.machine_type)
                except Exception:
                    pass
            conn = psycopg2.connect(settings.database_url)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO card_feedback
                            (brand, model, machine_type_id,
                             rating, problemi, note, strategy, fonte_tipo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            body.brand, body.model, mt_id,
                            body.rating, body.problemi or [], body.note,
                            body.strategy, body.fonte_tipo,
                        ),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.warning("submit_card_feedback DB error: %s", e)

    # Feedback negativo su AI inference → avvia crawl in background
    if body.rating <= 2 and body.fonte_tipo == "fallback_ai":
        try:
            from app.services.manual_crawler import crawl_for_manual
            asyncio.create_task(
                crawl_for_manual(body.brand, body.model, body.machine_type)
            )
        except Exception as e:
            logger.debug("submit_card_feedback crawl task: %s", e)

    return {"ok": True}


# ── Endpoint: statistiche feedback ───────────────────────────────────────────

@router.get("/stats")
async def get_feedback_stats():
    """
    Statistiche aggregate: rating medio per strategia, problemi frequenti.
    """
    if not settings.database_url:
        return {"error": "DB non configurato"}
    try:
        import psycopg2
        conn = psycopg2.connect(settings.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        strategy,
                        fonte_tipo,
                        COUNT(*) AS totale,
                        ROUND(AVG(rating)::numeric, 2) AS rating_medio,
                        SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) AS negativi
                    FROM card_feedback
                    WHERE ts > NOW() - INTERVAL '30 days'
                    GROUP BY strategy, fonte_tipo
                    ORDER BY totale DESC
                """)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
        finally:
            conn.close()
        return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        logger.warning("get_feedback_stats: %s", e)
        return {"error": str(e)}
