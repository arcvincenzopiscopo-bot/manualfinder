"""
Servizio per il salvataggio e la ricerca di manuali confermati dagli ispettori.
Usa connessione diretta PostgreSQL a Supabase (transaction pooler).
"""
from typing import Optional, List
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


def find_for_search(
    brand: str,
    model: str,
    machine_type: Optional[str],
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
                cur.execute(
                    """
                    SELECT *, 'specific' AS _match_type
                    FROM saved_manuals
                    WHERE manual_brand ILIKE %s
                      AND manual_model ILIKE %s
                      AND manual_brand NOT ILIKE 'GENERICO'
                    ORDER BY created_at DESC
                    LIMIT 5
                    """,
                    (f"%{brand}%", f"%{model}%"),
                )
                specific_ids = []
                for row in cur.fetchall():
                    r = dict(row)
                    specific_ids.append(str(r["id"]))
                    results.append(r)

                # 2) Generici per categoria o machine_type match (escludi già trovati)
                if machine_type:
                    exclude = tuple(specific_ids) if specific_ids else ("__none__",)
                    cur.execute(
                        """
                        SELECT *, 'generic' AS _match_type
                        FROM saved_manuals
                        WHERE (
                            manual_brand ILIKE 'GENERICO'
                            OR manual_machine_type ILIKE %s
                        )
                        AND id::text NOT IN %s
                        ORDER BY
                            CASE WHEN manual_brand ILIKE 'GENERICO' THEN 0 ELSE 1 END,
                            created_at DESC
                        LIMIT 5
                        """,
                        (f"%{machine_type}%", exclude),
                    )
                    results.extend(dict(r) for r in cur.fetchall())

        return results
    except Exception:
        return []  # Non bloccare la pipeline se il DB non è raggiungibile
