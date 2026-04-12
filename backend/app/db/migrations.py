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


def _m009_inail_manual_assignments(conn) -> None:
    """Tabella inail_manual_assignments: mapping machine_type_id → PDF locale."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inail_manual_assignments (
                id               SERIAL PRIMARY KEY,
                machine_type_id  INTEGER NOT NULL REFERENCES machine_types(id) ON DELETE CASCADE,
                pdf_filename     TEXT NOT NULL,
                display_title    TEXT,
                is_active        BOOLEAN DEFAULT true,
                created_at       TIMESTAMPTZ DEFAULT NOW(),
                updated_at       TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(machine_type_id)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_inail_assignments_active
                ON inail_manual_assignments(machine_type_id)
                WHERE is_active = true
        """)
    conn.commit()


def _m010_saved_manuals_machine_type_id(conn) -> None:
    """Aggiunge machine_type_id e search_machine_type_id a saved_manuals."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE saved_manuals
                ADD COLUMN IF NOT EXISTS machine_type_id
                    INTEGER REFERENCES machine_types(id) ON DELETE SET NULL
        """)
        cur.execute("""
            ALTER TABLE saved_manuals
                ADD COLUMN IF NOT EXISTS search_machine_type_id
                    INTEGER REFERENCES machine_types(id) ON DELETE SET NULL
        """)
    conn.commit()


def _m011_manual_feedback_machine_type_id(conn) -> None:
    """Aggiunge machine_type_id e useful_for_type_id a manual_feedback."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE manual_feedback
                ADD COLUMN IF NOT EXISTS machine_type_id
                    INTEGER REFERENCES machine_types(id) ON DELETE SET NULL
        """)
        cur.execute("""
            ALTER TABLE manual_feedback
                ADD COLUMN IF NOT EXISTS useful_for_type_id
                    INTEGER REFERENCES machine_types(id) ON DELETE SET NULL
        """)
    conn.commit()


def _m012_card_feedback_machine_type_id(conn) -> None:
    """Aggiunge machine_type_id a card_feedback."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE card_feedback
                ADD COLUMN IF NOT EXISTS machine_type_id
                    INTEGER REFERENCES machine_types(id) ON DELETE SET NULL
        """)
    conn.commit()


def _m013_log_machine_type_id(conn) -> None:
    """Aggiunge machine_type_id a quality_log e analysis_log."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE quality_log
                ADD COLUMN IF NOT EXISTS machine_type_id
                    INTEGER REFERENCES machine_types(id) ON DELETE SET NULL
        """)
        cur.execute("""
            ALTER TABLE analysis_log
                ADD COLUMN IF NOT EXISTS machine_type_id
                    INTEGER REFERENCES machine_types(id) ON DELETE SET NULL
        """)
    conn.commit()


def _m014_rules_machine_type_id(conn) -> None:
    """Aggiunge machine_type_id a machine_prompt_rules e url_filter_rules."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE machine_prompt_rules
                ADD COLUMN IF NOT EXISTS machine_type_id
                    INTEGER REFERENCES machine_types(id) ON DELETE SET NULL
        """)
        cur.execute("""
            ALTER TABLE url_filter_rules
                ADD COLUMN IF NOT EXISTS context_machine_type_id
                    INTEGER REFERENCES machine_types(id) ON DELETE SET NULL
        """)
    conn.commit()


def _m015_machine_types_new_flags(conn) -> None:
    """Aggiunge should_have_manual e is_officina a machine_types."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE machine_types
                ADD COLUMN IF NOT EXISTS should_have_manual BOOLEAN DEFAULT false
        """)
        cur.execute("""
            ALTER TABLE machine_types
                ADD COLUMN IF NOT EXISTS is_officina BOOLEAN DEFAULT false
        """)
    conn.commit()


def _m016_machine_type_normative(conn) -> None:
    """Tabella machine_type_normative: norme applicabili per tipo macchina."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS machine_type_normative (
                id               SERIAL PRIMARY KEY,
                machine_type_id  INTEGER REFERENCES machine_types(id) ON DELETE CASCADE,
                norm_text        TEXT NOT NULL,
                display_order    INTEGER DEFAULT 0,
                is_active        BOOLEAN DEFAULT true,
                created_at       TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_mtn_machine_type
                ON machine_type_normative(machine_type_id)
        """)
    conn.commit()


def _m017_riferimenti_normativi(conn) -> None:
    """Tabella riferimenti_normativi: articoli D.Lgs 81/08 per tipo macchina."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS riferimenti_normativi (
                id                SERIAL PRIMARY KEY,
                norma_key         TEXT NOT NULL UNIQUE,
                norma             TEXT NOT NULL,
                titolo            TEXT NOT NULL,
                testo             TEXT NOT NULL,
                keywords          TEXT[],
                machine_type_ids  INTEGER[],
                is_active         BOOLEAN DEFAULT true,
                created_at        TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rn_norma_key
                ON riferimenti_normativi(norma_key)
        """)
    conn.commit()


def _m018_backfill_machine_type_ids(conn) -> None:
    """
    Backfill machine_type_id FK columns da testo esistente.
    Usa machine_types.normalized_name (match esatto) poi machine_aliases.normalized_alias
    come fallback. Idempotente: salta righe già con machine_type_id valorizzato.
    """
    _resolve_sql = """
        COALESCE(
            (SELECT id FROM machine_types
             WHERE normalized_name = LOWER(TRIM({col}))),
            (SELECT ma.machine_type_id FROM machine_aliases ma
             WHERE ma.normalized_alias = LOWER(TRIM({col}))
             LIMIT 1)
        )
    """

    tables_text_cols = [
        # (tabella, colonna_testo, colonna_id_da_popolare)
        ("saved_manuals",      "manual_machine_type", "machine_type_id"),
        ("saved_manuals",      "search_machine_type", "search_machine_type_id"),
        ("manual_feedback",    "machine_type",         "machine_type_id"),
        ("manual_feedback",    "useful_for_type",      "useful_for_type_id"),
        ("card_feedback",      "machine_type",         "machine_type_id"),
        ("quality_log",        "machine_type",         "machine_type_id"),
        ("analysis_log",       "machine_type",         "machine_type_id"),
        ("url_filter_rules",   "context_machine_type", "context_machine_type_id"),
        ("machine_prompt_rules", "machine_type",       "machine_type_id"),
    ]

    with conn.cursor() as cur:
        for table, text_col, id_col in tables_text_cols:
            resolve = _resolve_sql.format(col=f"t.{text_col}")
            cur.execute(f"""
                UPDATE {table} t
                SET {id_col} = {resolve}
                WHERE t.{id_col} IS NULL
                  AND t.{text_col} IS NOT NULL
                  AND t.{text_col} != ''
            """)
    conn.commit()


def _m019_drop_redundant_text_columns(conn) -> None:
    """
    Rimuove le colonne testo ridondanti ormai sostituite da FK machine_type_id.
    Eseguita DOPO il backfill v18. Lascia intatte le colonne ancora in uso
    come chiave testuale (machine_prompt_rules.machine_type, quality_log.machine_type,
    saved_manuals.manual_machine_type/search_machine_type).
    """
    with conn.cursor() as cur:
        # manual_feedback: useful_for_type → useful_for_type_id
        cur.execute("ALTER TABLE manual_feedback DROP COLUMN IF EXISTS useful_for_type")
        # card_feedback: machine_type → machine_type_id
        cur.execute("ALTER TABLE card_feedback DROP COLUMN IF EXISTS machine_type")
        # analysis_log: machine_type → machine_type_id
        cur.execute("ALTER TABLE analysis_log DROP COLUMN IF EXISTS machine_type")
        # url_filter_rules: context_machine_type → context_machine_type_id
        cur.execute("ALTER TABLE url_filter_rules DROP COLUMN IF EXISTS context_machine_type")
    conn.commit()


MIGRATIONS: list[tuple[int, str, Callable]] = [
    (1,  "machine_types core tables",                    _m001_machine_types),
    (2,  "machine_type_hazard table",                    _m002_machine_type_hazard),
    (3,  "scan_log tables",                              _m003_scan_log),
    (4,  "search_cache_v1 table",                        _m004_search_cache),
    (5,  "manual_cache table",                           _m005_manual_cache),
    (6,  "pending: add inail_hint column",               _m006_add_inail_hint_to_pending),
    (7,  "pending: add db_filename column",              _m007_add_db_filename_to_pending),
    (8,  "scan_log: add serial/year/norme cols",         _m008_scan_log_columns),
    (9,  "inail_manual_assignments table",               _m009_inail_manual_assignments),
    (10, "saved_manuals: add machine_type_id FKs",       _m010_saved_manuals_machine_type_id),
    (11, "manual_feedback: add machine_type_id FKs",     _m011_manual_feedback_machine_type_id),
    (12, "card_feedback: add machine_type_id FK",        _m012_card_feedback_machine_type_id),
    (13, "quality/analysis_log: add machine_type_id FK", _m013_log_machine_type_id),
    (14, "rules: add machine_type_id FKs",               _m014_rules_machine_type_id),
    (15, "machine_types: add should_have_manual/is_officina", _m015_machine_types_new_flags),
    (16, "machine_type_normative table",                 _m016_machine_type_normative),
    (17, "riferimenti_normativi table",                  _m017_riferimenti_normativi),
    (18, "backfill machine_type_id from text columns",   _m018_backfill_machine_type_ids),
    (19, "drop redundant text columns",                  _m019_drop_redundant_text_columns),
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
