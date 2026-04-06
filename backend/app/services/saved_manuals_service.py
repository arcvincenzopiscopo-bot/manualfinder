"""
Servizio per il salvataggio e la ricerca di manuali confermati dagli ispettori.
Usa connessione diretta PostgreSQL a Supabase (transaction pooler).
"""
from typing import Optional
import psycopg2
import psycopg2.extras
from app.config import settings


def _get_conn():
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL non configurata")
    return psycopg2.connect(settings.database_url)


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
    brand: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 30,
) -> list:
    """
    Cerca manuali salvati per tipo macchina, brand o modello.
    Restituisce max `limit` risultati ordinati dal più recente.
    """
    conditions = []
    params = []

    if machine_type:
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
