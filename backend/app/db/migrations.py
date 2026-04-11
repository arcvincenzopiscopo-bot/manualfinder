"""
Sistema di migrazioni DB versionato.

Ogni migrazione è una funzione Python che riceve una psycopg2 connection e
applica modifiche al DB. Le migrazioni vengono eseguite in ordine numerico e
mai rieseguite (tracciamento via tabella schema_version).

Uso:
    from app.db.migrations import run_migrations
    run_migrations()  # idempotente, esegue solo quelle non ancora applicate

Aggiungere nuove migrazioni in fondo a MIGRATIONS con il numero progressivo.
Non modificare mai una migrazione già eseguita — creare una nuova.
"""
import logging
from typing import Callable

logger = logging.getLogger(__name__)


# ─── Definizione migrazioni ───────────────────────────────────────────────────
# Ogni entry: (version: int, description: str, fn: Callable[[conn], None])

def _m001_machine_types(conn) -> None:
    """Tabelle core machine_types, machine_aliases, pending_machine_types."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS machine_types (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL UNIQUE,
                is_verified BOOLEAN DEFAULT true,
                requires_patentino BOOLEAN DEFAULT false,
                requires_verifiche BOOLEAN DEFAULT false,
                inail_search_hint TEXT,
                usage_count INTEGER DEFAULT 0,
                vita_utile_anni INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS machine_aliases (
                id SERIAL PRIMARY KEY,
                machine_type_id INTEGER REFERENCES machine_types(id) ON DELETE CASCADE,
                alias TEXT NOT NULL,
                normalized_alias TEXT NOT NULL,
                UNIQUE(machine_type_id, normalized_alias)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_machine_types (
                id SERIAL PRIMARY KEY,
                proposed_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                resolution TEXT DEFAULT 'pending',
                resolved_at TIMESTAMPTZ,
                inail_hint TEXT,
                db_filename TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    conn.commit()


def _m002_machine_type_hazard(conn) -> None:
    """Tabella hazard INAIL per categoria macchina."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS machine_type_hazard (
                id SERIAL PRIMARY KEY,
                machine_type_id INTEGER REFERENCES machine_types(id) ON DELETE CASCADE,
                categoria_inail TEXT,
                focus_testo TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(machine_type_id)
            )
        """)
    conn.commit()


def _m003_scan_log(conn) -> None:
    """Tabella storico scansioni."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scan_log (
                id SERIAL PRIMARY KEY,
                brand TEXT,
                model TEXT,
                machine_type TEXT,
                machine_type_id INTEGER REFERENCES machine_types(id) ON DELETE SET NULL,
                serial_number TEXT,
                year TEXT,
                norme TEXT[],
                provider TEXT,
                strategy TEXT,
                fonte_tipo TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scan_images (
                id SERIAL PRIMARY KEY,
                scan_log_id INTEGER REFERENCES scan_log(id) ON DELETE CASCADE,
                image_data BYTEA,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    conn.commit()


def _m004_search_cache(conn) -> None:
    """Cache ricerche manuali su DB (fallback a dict in-memory se non disponibile)."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS search_cache_v1 (
                cache_key TEXT PRIMARY KEY,
                results_json TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ
            )
        """)
    conn.commit()


def _m005_manual_cache(conn) -> None:
    """Cache crawler manuali."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS manual_cache (
                id SERIAL PRIMARY KEY,
                cache_key TEXT UNIQUE NOT NULL,
                results_json TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    conn.commit()


def _m006_add_inail_hint_to_pending(conn) -> None:
    """Aggiunge colonna inail_hint a pending_machine_types se mancante."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE pending_machine_types
            ADD COLUMN IF NOT EXISTS inail_hint TEXT
        """)
    conn.commit()


def _m007_add_db_filename_to_pending(conn) -> None:
    """Aggiunge colonna db_filename a pending_machine_types se mancante."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE pending_machine_types
            ADD COLUMN IF NOT EXISTS db_filename TEXT
        """)
    conn.commit()


def _m008_scan_log_columns(conn) -> None:
    """Aggiunge colonne serial_number, year, norme a scan_log se mancanti."""
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE scan_log ADD COLUMN IF NOT EXISTS serial_number TEXT")
        cur.execute("ALTER TABLE scan_log ADD COLUMN IF NOT EXISTS year TEXT")
        cur.execute("ALTER TABLE scan_log ADD COLUMN IF NOT EXISTS norme TEXT[]")
    conn.commit()


MIGRATIONS: list[tuple[int, str, Callable]] = [
    (1,  "machine_types core tables",            _m001_machine_types),
    (2,  "machine_type_hazard table",            _m002_machine_type_hazard),
    (3,  "scan_log tables",                      _m003_scan_log),
    (4,  "search_cache_v1 table",                _m004_search_cache),
    (5,  "manual_cache table",                   _m005_manual_cache),
    (6,  "pending: add inail_hint column",       _m006_add_inail_hint_to_pending),
    (7,  "pending: add db_filename column",      _m007_add_db_filename_to_pending),
    (8,  "scan_log: add serial/year/norme cols", _m008_scan_log_columns),
]


# ─── Runner ───────────────────────────────────────────────────────────────────

def _ensure_schema_version_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                description TEXT,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    conn.commit()


def _applied_versions(conn) -> set[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_version")
        return {row[0] for row in cur.fetchall()}


def _record_version(conn, version: int, description: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO schema_version (version, description) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (version, description),
        )
    conn.commit()


def run_migrations() -> None:
    """
    Esegue tutte le migrazioni non ancora applicate, in ordine.
    Idempotente: migrazioni già eseguite sono saltate.
    Ogni migrazione viene eseguita in una transazione separata con rollback su errore.
    """
    from app.config import settings
    if not settings.database_url:
        logger.info("db.migrations: nessun DATABASE_URL — skip migrazioni")
        return

    try:
        import psycopg2
        conn = psycopg2.connect(settings.database_url)
    except Exception as e:
        logger.error("db.migrations: impossibile connettersi al DB: %s", e)
        return

    try:
        _ensure_schema_version_table(conn)
        applied = _applied_versions(conn)

        for version, description, fn in sorted(MIGRATIONS, key=lambda m: m[0]):
            if version in applied:
                continue
            logger.info("db.migrations: applicando v%d — %s", version, description)
            try:
                fn(conn)
                _record_version(conn, version, description)
                logger.info("db.migrations: v%d OK", version)
            except Exception as e:
                logger.error("db.migrations: v%d FALLITA (%s) — rollback", version, e)
                conn.rollback()
                # Non interrompiamo: le migrazioni successive potrebbero essere indipendenti
    finally:
        conn.close()
