"""
Catalogo canonico dei tipi di macchina con matching fuzzy a 2 livelli.
Sostituisce il testo libero OCR con ID da DB per coerenza nella pipeline.

Matching pipeline:
  L1a: rapidfuzz extractOne (soglia 82) → hit diretto, nessun LLM
  L1b: rapidfuzz extract top-5 (soglia 65) → candidati per LLM
  L2:  LLM arbitro (Gemini Flash / Claude Haiku) sceglie tra candidati

Tabelle create automaticamente all'avvio:
  machine_types, machine_aliases, pending_machine_types
"""
import json
import logging
import re
import time as _time
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ── Cache in-memory ──────────────────────────────────────────────────────────
_cache: Optional[list] = None
_cache_ts: float = 0.0
_alias_map: dict[str, int] = {}   # {normalized_alias: machine_type_id}
_type_flags: dict[int, dict] = {} # {machine_type_id: {requires_patentino, requires_verifiche}}
_CACHE_TTL = 3600  # 1 ora

# ── Soglie di matching ────────────────────────────────────────────────────────
_FUZZY_DIRECT = 82    # L1a: hit diretto, confidenza alta
_FUZZY_CANDIDATES = 65 # L1b: soglia bassa per raccogliere candidati LLM

# ── LLM Level 2 prompt ───────────────────────────────────────────────────────
_LEVEL2_PROMPT = (
    "Sei un classificatore di macchinari da cantiere e industriali.\n"
    "Testo OCR dalla targa: \"{ocr_text}\"\n"
    "Scegli il tipo macchina più appropriato TRA I SEGUENTI CANDIDATI:\n"
    "{candidates_json}\n"
    "Rispondi SOLO con JSON valido: {{\"machine_type_id\": <id intero> oppure null}}\n"
    "Non aggiungere spiegazioni."
)

# ── Seed data ─────────────────────────────────────────────────────────────────
# (name, requires_patentino, requires_verifiche, inail_hint)
_SEED_TYPES: list[tuple] = [
    ("carrello elevatore",          True,  True,  "carrello elevatore frontale"),
    ("carrello portacontainer",     True,  True,  "carrello portacontainer reach stacker"),
    ("piattaforma aerea",           True,  True,  "PLE piattaforma lavoro elevabile"),
    ("piattaforma a forbice",       True,  True,  "piattaforma a forbice PLE"),
    ("piattaforma verticale",       False, True,  "piattaforma verticale PLAV"),
    ("sollevatore telescopico",     True,  True,  "sollevatore telescopico telehandler"),
    ("gru mobile",                  True,  True,  "gru mobile su autocarro"),
    ("gru a torre",                 True,  True,  "gru a torre cantiere"),
    ("gru su autocarro",            True,  True,  "gru su autocarro fassi"),
    ("gru a bandiera",              False, True,  "gru a bandiera articolata"),
    ("paranco elettrico",           False, True,  "paranco elettrico sollevamento"),
    ("argano",                      False, True,  "argano verricello"),
    ("carrello retrattile",         True,  True,  "carrello retrattile reach truck"),
    ("transpallet elettrico",       False, False, "transpallet elettrico"),
    ("elevatore a colonna",         False, True,  "elevatore a colonna montacarichi"),
    ("escavatore",                  True,  False, "escavatore idraulico cingolato"),
    ("pala caricatrice",            True,  False, "pala meccanica caricatrice"),
    ("terna",                       True,  False, "terna escavatore caricatrice"),
    ("minipala",                    True,  False, "minipala skid steer"),
    ("rullo compattatore",          True,  False, "rullo compattatore stradale"),
    ("livellatrice",                True,  False, "livellatrice grader stradale"),
    ("finitrice stradale",          True,  False, "finitrice asfaltice paver"),
    ("dumper",                      True,  False, "dumper articolato cantiere"),
    ("bulldozer",                   False, False, "bulldozer apripista"),
    ("pompa calcestruzzo",          True,  True,  "pompa calcestruzzo autopompa"),
    ("betoniera",                   False, False, "betoniera autobetoniera"),
    ("generatore",                  False, False, "gruppo elettrogeno generatore"),
    ("compressore",                 False, False, "compressore aria"),
    ("saldatrice",                  False, False, "saldatrice elettrica"),
    ("trattore agricolo",           True,  False, "trattore agricolo"),
    ("pressa piegatrice",           False, False, "pressa piegatrice CNC"),
    ("punzonatrice",                False, False, "punzonatrice lamiera"),
    ("macchina taglio laser",       False, False, "taglio laser fibra"),
    ("sega circolare",              False, False, "sega circolare legno"),
    ("centro di lavoro CNC",        False, False, "centro di lavoro CNC"),
    ("tornio",                      False, False, "tornio industriale"),
    ("fresatrice",                  False, False, "fresatrice CNC"),
    ("martello demolitore idraulico", False, False, "martello idraulico escavatore"),
    ("accessorio/attrezzatura",     False, False, None),
]

# {type_name: [alias, alias, ...]}
_SEED_ALIASES: dict[str, list[str]] = {
    "carrello elevatore":        ["forklift", "carrello frontale", "muletto", "fork lift", "carrello elevatore frontale"],
    "piattaforma aerea":         ["ple", "aerial work platform", "awp", "boom lift", "piattaforma aerea a braccio", "piattaforma lavoro elevabile"],
    "piattaforma a forbice":     ["scissor lift", "piattaforma a pantografo", "piattaforma forbice"],
    "sollevatore telescopico":   ["telehandler", "telescopic handler", "manipolatore telescopico", "sollevatore telescopico"],
    "carrello portacontainer":   ["reach stacker", "stacker", "portacontainer"],
    "gru mobile":                ["crane", "gru semovente", "gru mobile", "gru autocarrata"],
    "gru a torre":               ["tower crane", "gru torre"],
    "gru su autocarro":          ["crane truck", "camion gru", "autocarro gru"],
    "escavatore":                ["excavator", "scavatore", "escavatore idraulico", "excavatrice"],
    "pala caricatrice":          ["wheel loader", "pala meccanica", "loader", "pala gommata", "pala cingolata"],
    "terna":                     ["backhoe", "backhoe loader", "retroescavatore"],
    "minipala":                  ["skid steer", "bobcat", "mini pala"],
    "rullo compattatore":        ["compactor", "rullo", "compattatore", "rullo vibrante"],
    "dumper":                    ["autoribaltabile", "dumper articolato"],
    "betoniera":                 ["mixer", "concrete mixer", "autobetoniera", "betoniera a bicchiere"],
    "pompa calcestruzzo":        ["concrete pump", "autopompa", "pompa cls"],
    "bulldozer":                 ["apripista", "buldozer"],
    "generatore":                ["generator", "gruppo elettrogeno", "genset", "generatore elettrico"],
    "compressore":               ["compressor", "compressore aria", "motocompressore"],
    "saldatrice":                ["welder", "saldatrice mig", "saldatrice tig", "saldatrice ad arco"],
    "pressa piegatrice":         ["press brake", "bending machine", "piegatrice"],
    "macchina taglio laser":     ["laser", "taglio laser", "laser cutter", "laser fibra"],
    "accessorio/attrezzatura":   ["attachment", "accessorio", "attrezzo", "benna", "rotatore", "testa idraulica", "polipo", "pinza"],
    "martello demolitore idraulico": ["breaker", "martello idraulico", "martello demolitore"],
}


def _normalize(text: str) -> str:
    """Lowercase + strip + rimuovi punteggiatura multipla."""
    return re.sub(r"\s+", " ", text.lower().strip())


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_conn():
    import psycopg2
    return psycopg2.connect(settings.database_url)


def _ensure_tables() -> None:
    """Crea tabelle se non esistono e popola il seed iniziale. Sicuro da chiamare più volte."""
    global _alias_map, _type_flags
    if not settings.database_url:
        logger.warning("machine_type_service: database_url non configurato, uso solo memoria")
        _seed_in_memory()
        return
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS machine_types (
                    id                 SERIAL PRIMARY KEY,
                    name               TEXT NOT NULL UNIQUE,
                    normalized_name    TEXT NOT NULL UNIQUE,
                    inail_search_hint  TEXT,
                    requires_patentino BOOL NOT NULL DEFAULT true,
                    requires_verifiche BOOL NOT NULL DEFAULT true,
                    normative_references TEXT[] DEFAULT '{}',
                    usage_count        INT NOT NULL DEFAULT 0,
                    is_verified        BOOL NOT NULL DEFAULT true,
                    created_at         TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS machine_aliases (
                    id               SERIAL PRIMARY KEY,
                    machine_type_id  INT NOT NULL REFERENCES machine_types(id),
                    alias_text       TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL,
                    source           TEXT NOT NULL DEFAULT 'admin',
                    created_at       TIMESTAMP DEFAULT NOW(),
                    UNIQUE(normalized_alias)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pending_machine_types (
                    id                    SERIAL PRIMARY KEY,
                    proposed_name         TEXT NOT NULL,
                    proposed_by           TEXT,
                    ai_similarity_score   FLOAT,
                    ai_suggested_merge_id INT REFERENCES machine_types(id),
                    resolution            TEXT NOT NULL DEFAULT 'pending',
                    resolved_at           TIMESTAMP,
                    created_at            TIMESTAMP DEFAULT NOW()
                )
            """)
        # Migration: nuove colonne e tabelle
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE machine_types ADD COLUMN IF NOT EXISTS vita_utile_anni INT DEFAULT NULL")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS machine_type_hazard (
                    id                  SERIAL PRIMARY KEY,
                    machine_type_id     INT UNIQUE NOT NULL REFERENCES machine_types(id) ON DELETE CASCADE,
                    categoria_inail     TEXT,
                    focus_testo         TEXT,
                    aggiornato_da       TEXT NOT NULL DEFAULT 'ai',
                    last_updated        TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()
        # Popola seed se tabella vuota
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM machine_types")
            count = cur.fetchone()[0]
        if count == 0:
            _seed_db(conn)
        else:
            _apply_flag_corrections(conn)
        conn.close()
        # Ricarica alias map in memoria
        _rebuild_alias_map()
        logger.info("machine_type_service: tabelle pronte (%d alias in memoria)", len(_alias_map))
    except Exception as e:
        logger.error("machine_type_service: errore setup tabelle: %s", e)
        _seed_in_memory()


def _seed_db(conn) -> None:
    """Inserisce i tipi canonici + alias nel DB. Usato solo al primo avvio."""
    with conn.cursor() as cur:
        for name, req_pat, req_ver, inail_hint in _SEED_TYPES:
            cur.execute(
                """
                INSERT INTO machine_types (name, normalized_name, inail_search_hint,
                    requires_patentino, requires_verifiche, is_verified)
                VALUES (%s, %s, %s, %s, %s, true)
                ON CONFLICT (normalized_name) DO NOTHING
                """,
                (name, _normalize(name), inail_hint, req_pat, req_ver),
            )
        conn.commit()
        # Rileggi gli ID appena inseriti
        cur.execute("SELECT id, normalized_name FROM machine_types")
        name_to_id = {row[1]: row[0] for row in cur.fetchall()}
        # Inserisci alias
        for type_name, aliases in _SEED_ALIASES.items():
            norm_name = _normalize(type_name)
            mt_id = name_to_id.get(norm_name)
            if not mt_id:
                continue
            for alias in aliases:
                norm_alias = _normalize(alias)
                cur.execute(
                    """
                    INSERT INTO machine_aliases (machine_type_id, alias_text, normalized_alias, source)
                    VALUES (%s, %s, %s, 'admin')
                    ON CONFLICT (normalized_alias) DO NOTHING
                    """,
                    (mt_id, alias, norm_alias),
                )
        conn.commit()
    logger.info("machine_type_service: seed DB completato (%d tipi)", len(_SEED_TYPES))


# Correzioni normative v2 — applicate anche su DB esistenti (idempotente)
# Accordo Stato-Regioni 22/02/2012: tutte le macchine movimento terra richiedono patentino.
# D.Lgs. 81/08 Allegato VII: solo apparecchi di sollevamento richiedono verifiche INAIL;
# macchine movimento terra, trattori e bulldozer NON sono nell'Allegato VII.
_FLAG_CORRECTIONS: list[tuple[str, bool, bool]] = [
    # (normalized_name, requires_patentino, requires_verifiche)
    ("escavatore",        True,  False),
    ("pala caricatrice",  True,  False),
    ("terna",             True,  False),
    ("minipala",          True,  False),
    ("rullo compattatore",True,  False),
    ("livellatrice",      True,  False),
    ("finitrice stradale",True,  False),
    ("dumper",            True,  False),
    ("bulldozer",         False, False),
    ("pompa calcestruzzo",True,  True),
    ("trattore agricolo", True,  False),
]


def _apply_flag_corrections(conn) -> None:
    """Corregge i flag normativi su DB esistenti. Sicuro da chiamare ad ogni avvio."""
    try:
        with conn.cursor() as cur:
            for norm_name, req_pat, req_ver in _FLAG_CORRECTIONS:
                cur.execute(
                    "UPDATE machine_types SET requires_patentino = %s, requires_verifiche = %s "
                    "WHERE normalized_name = %s",
                    (req_pat, req_ver, norm_name),
                )
        conn.commit()
        logger.info("machine_type_service: flag corrections applicati")
    except Exception as e:
        logger.warning("machine_type_service: _apply_flag_corrections fallito: %s", e)


def _seed_in_memory() -> None:
    """Fallback: popola _alias_map e _type_flags solo in memoria (nessun DB)."""
    global _alias_map, _type_flags
    fake_id = 1
    for name, req_pat, req_ver, _ in _SEED_TYPES:
        norm = _normalize(name)
        _alias_map[norm] = fake_id
        _type_flags[fake_id] = {"requires_patentino": req_pat, "requires_verifiche": req_ver}
        # Aggiungi alias se presenti
        for alias in _SEED_ALIASES.get(name, []):
            _alias_map[_normalize(alias)] = fake_id
        fake_id += 1
    logger.info("machine_type_service: seed in-memory completato (%d alias)", len(_alias_map))


def _rebuild_alias_map() -> None:
    """Ricostruisce _alias_map e _type_flags da DB (lazy rebuild)."""
    global _alias_map, _type_flags
    if not settings.database_url:
        return
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            # Alias inclusi i nomi canonici stessi
            cur.execute("""
                SELECT a.normalized_alias, a.machine_type_id
                FROM machine_aliases a
                JOIN machine_types t ON t.id = a.machine_type_id
                WHERE t.is_verified = true
            """)
            new_map = {row[0]: row[1] for row in cur.fetchall()}
            # Aggiungi anche i nomi canonici normalizzati
            cur.execute("SELECT id, normalized_name FROM machine_types WHERE is_verified = true")
            for row in cur.fetchall():
                new_map[row[1]] = row[0]
            # Flags
            cur.execute("SELECT id, requires_patentino, requires_verifiche FROM machine_types WHERE is_verified = true")
            new_flags = {row[0]: {"requires_patentino": row[1], "requires_verifiche": row[2]} for row in cur.fetchall()}
        conn.close()
        _alias_map = new_map
        _type_flags = new_flags
    except Exception as e:
        logger.error("machine_type_service: errore rebuild alias map: %s", e)


def invalidate_cache() -> None:
    """Invalida cache + alias map. Chiamare dopo ogni scrittura su machine_types/machine_aliases."""
    global _cache, _cache_ts, _alias_map, _type_flags
    _cache = None
    _cache_ts = 0.0
    _alias_map = {}
    _type_flags = {}
    # Ricostruisce subito la map (non lazy, evita stale state)
    _rebuild_alias_map()


def _ensure_alias_map() -> None:
    """Ricostruisce alias map se vuota (lazy init)."""
    if not _alias_map:
        _rebuild_alias_map()
        if not _alias_map:
            _seed_in_memory()


# ── Lettura ──────────────────────────────────────────────────────────────────

def get_all_types() -> list[dict]:
    """Lista completa dei tipi verificati per il dropdown frontend. Cache 1h."""
    global _cache, _cache_ts
    now = _time.monotonic()
    if _cache is not None and now - _cache_ts < _CACHE_TTL:
        return _cache
    if not settings.database_url:
        # Fallback sintetico da seed
        result = [
            {"id": i + 1, "name": name, "requires_patentino": req_pat, "requires_verifiche": req_ver}
            for i, (name, req_pat, req_ver, _) in enumerate(_SEED_TYPES)
        ]
        _cache = result
        _cache_ts = now
        return result
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, requires_patentino, requires_verifiche, inail_search_hint, usage_count, vita_utile_anni "
                "FROM machine_types WHERE is_verified = true ORDER BY name"
            )
            rows = cur.fetchall()
        conn.close()
        result = [
            {
                "id": r[0], "name": r[1],
                "requires_patentino": r[2], "requires_verifiche": r[3],
                "inail_search_hint": r[4], "usage_count": r[5],
                "vita_utile_anni": r[6],
            }
            for r in rows
        ]
        _cache = result
        _cache_ts = now
        return result
    except Exception as e:
        logger.error("machine_type_service.get_all_types: %s", e)
        return []


def find_by_id(machine_type_id: int) -> Optional[dict]:
    """Lookup singolo tipo per ID."""
    if not settings.database_url:
        return None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, requires_patentino, requires_verifiche, inail_search_hint "
                "FROM machine_types WHERE id = %s AND is_verified = true",
                (machine_type_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "requires_patentino": row[2],
                "requires_verifiche": row[3], "inail_search_hint": row[4]}
    except Exception:
        return None


def get_name_by_id(machine_type_id: int) -> Optional[str]:
    """Ritorna il nome canonico per un ID."""
    row = find_by_id(machine_type_id)
    return row["name"] if row else None


def get_type_flags(machine_type_id: int) -> dict:
    """
    Ritorna {requires_patentino: bool, requires_verifiche: bool}.
    Fail-safe: se ID non trovato o DB non raggiungibile → True/True (conservativo).
    """
    _ensure_alias_map()
    if machine_type_id in _type_flags:
        return _type_flags[machine_type_id]
    # Prova DB direttamente
    if settings.database_url:
        try:
            conn = _get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT requires_patentino, requires_verifiche FROM machine_types WHERE id = %s",
                    (machine_type_id,),
                )
                row = cur.fetchone()
            conn.close()
            if row:
                flags = {"requires_patentino": row[0], "requires_verifiche": row[1]}
                _type_flags[machine_type_id] = flags
                return flags
        except Exception:
            pass
    # Fail-safe conservativo: non rimuovere mai requisiti normativi per errore di lookup
    return {"requires_patentino": True, "requires_verifiche": True}


def increment_usage(machine_type_id: int) -> None:
    """Incrementa usage_count. Chiamato SOLO su feedback confirmed/corrected, non all'OCR."""
    if not settings.database_url:
        return
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE machine_types SET usage_count = usage_count + 1 WHERE id = %s",
                (machine_type_id,),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass


def suggest_new_type(proposed_name: str, session_id: str = "") -> dict:
    """Crea una entry pending_machine_types. Invalida cache."""
    if not settings.database_url:
        return {"status": "no_db", "proposed_name": proposed_name}
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pending_machine_types (proposed_name, proposed_by)
                VALUES (%s, %s) RETURNING id
                """,
                (proposed_name.strip(), session_id or None),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        invalidate_cache()
        return {"status": "pending", "id": new_id, "proposed_name": proposed_name}
    except Exception as e:
        logger.error("machine_type_service.suggest_new_type: %s", e)
        return {"status": "error", "proposed_name": proposed_name}


# ── Matching ──────────────────────────────────────────────────────────────────

def match_ocr_text(ocr_text: str) -> tuple[Optional[int], float, str]:
    """
    Matching a 2 livelli:
      L1a: rapidfuzz extractOne (soglia 82) → hit diretto
      L1b: rapidfuzz extract top-5 (soglia 65) → candidati per LLM
      L2:  LLM sincrono — usato solo se L1a fallisce e ci sono candidati

    Returns (machine_type_id, confidence_0_to_1, method)
    method: "fuzzy_l1" | "llm_l2" | "no_match" | "llm_error"
    """
    _ensure_alias_map()
    if not _alias_map or not ocr_text:
        return (None, 0.0, "no_match")

    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        logger.warning("rapidfuzz non installato — matching disabilitato")
        return (None, 0.0, "no_match")

    norm_query = _normalize(ocr_text)

    # ── Level 1a: hit diretto ────────────────────────────────────────────────
    hit = process.extractOne(
        query=norm_query,
        choices=list(_alias_map.keys()),
        scorer=fuzz.token_sort_ratio,
        score_cutoff=_FUZZY_DIRECT,
    )
    if hit:
        matched_alias, score, _ = hit
        mt_id = _alias_map[matched_alias]
        return (mt_id, score / 100.0, "fuzzy_l1")

    # ── Level 1b: candidati per LLM ─────────────────────────────────────────
    candidates_raw = process.extract(
        query=norm_query,
        choices=list(_alias_map.keys()),
        scorer=fuzz.token_sort_ratio,
        limit=5,
        score_cutoff=_FUZZY_CANDIDATES,
    )
    if not candidates_raw:
        return (None, 0.0, "no_match")

    # Costruisci lista candidati deduplicata per tipo
    seen_ids: set[int] = set()
    candidates: list[dict] = []
    for alias_text, _, _ in candidates_raw:
        mt_id = _alias_map[alias_text]
        if mt_id not in seen_ids:
            seen_ids.add(mt_id)
            name = _get_type_name_from_map(mt_id)
            candidates.append({"id": mt_id, "name": name})

    # ── Level 2: LLM arbitro ─────────────────────────────────────────────────
    result_id = _llm_arbitrate_sync(ocr_text, candidates)
    if result_id is None:
        return (None, 0.0, "llm_error")
    return (result_id, 0.7, "llm_l2")


def _get_type_name_from_map(mt_id: int) -> str:
    """Ritorna il nome del tipo da cache o DB."""
    for item in (_cache or []):
        if item["id"] == mt_id:
            return item["name"]
    row = find_by_id(mt_id)
    return row["name"] if row else str(mt_id)


def _llm_arbitrate_sync(ocr_text: str, candidates: list[dict]) -> Optional[int]:
    """
    Chiama LLM (Gemini Flash → Claude Haiku) con la lista candidati.
    Ritorna machine_type_id o None se LLM non riesce / formato errato.
    Sincrono — usa asyncio.run() solo se fuori da event loop attivo.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Siamo dentro un context asincrono: usa un thread separato
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _llm_arbitrate_async(ocr_text, candidates))
                return future.result(timeout=10)
        else:
            return asyncio.run(_llm_arbitrate_async(ocr_text, candidates))
    except Exception as e:
        logger.error("machine_type_service._llm_arbitrate_sync: %s", e)
        return None


async def _llm_arbitrate_async(ocr_text: str, candidates: list[dict]) -> Optional[int]:
    """
    Versione async del LLM arbitro. Gemini Flash prima, fallback Claude Haiku.
    Prompt immutabile nel codice — modifica solo il contenuto contestuale.
    """
    candidates_json = json.dumps(candidates, ensure_ascii=False)
    prompt = _LEVEL2_PROMPT.format(
        ocr_text=ocr_text,
        candidates_json=candidates_json,
    )
    provider = settings.get_analysis_provider()
    text = None
    try:
        if provider == "gemini" or settings.gemini_api_key:
            from google import genai
            from google.genai import types as gtypes
            client = genai.Client(api_key=settings.gemini_api_key)
            r = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=gtypes.GenerateContentConfig(max_output_tokens=50, temperature=0),
            )
            text = r.text
        elif provider == "anthropic" and settings.anthropic_api_key:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            r = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=50,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = r.content[0].text
        else:
            return None
    except Exception as e:
        logger.error("machine_type_service._llm_arbitrate_async: %s", e)
        return None

    if not text:
        return None
    try:
        m = re.search(r'\{[^}]+\}', text)
        if not m:
            return None
        data = json.loads(m.group())
        val = data.get("machine_type_id")
        if val is None:
            return None
        mt_id = int(val)
        # Verifica che l'ID restituito sia tra i candidati (anti-allucinazione)
        valid_ids = {c["id"] for c in candidates}
        if mt_id not in valid_ids:
            return None
        return mt_id
    except Exception:
        return None


# ── Admin API ─────────────────────────────────────────────────────────────────

def admin_get_pending() -> list[dict]:
    """Ritorna tutte le proposte pendenti."""
    if not settings.database_url:
        return []
    try:
        import psycopg2.extras
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, p.proposed_name, p.proposed_by, p.resolution,
                       p.ai_similarity_score, p.created_at,
                       t.name AS suggested_merge_name
                FROM pending_machine_types p
                LEFT JOIN machine_types t ON t.id = p.ai_suggested_merge_id
                WHERE p.resolution = 'pending'
                ORDER BY p.created_at DESC
            """)
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error("admin_get_pending: %s", e)
        return []


def admin_resolve_pending(pending_id: int, action: str,
                          merge_into_id: Optional[int] = None,
                          new_type_name: Optional[str] = None,
                          new_requires_patentino: bool = True,
                          new_requires_verifiche: bool = True) -> dict:
    """
    Risolve una proposta pending.
    action: 'alias'    → salva come alias di merge_into_id
            'promote'  → crea nuovo tipo canonico con new_type_name
            'reject'   → scarta
    """
    if not settings.database_url:
        return {"status": "no_db"}
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT proposed_name FROM pending_machine_types WHERE id = %s", (pending_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return {"status": "not_found"}
            proposed_name = row[0]

            if action == "alias" and merge_into_id:
                norm = _normalize(proposed_name)
                cur.execute("""
                    INSERT INTO machine_aliases (machine_type_id, alias_text, normalized_alias, source)
                    VALUES (%s, %s, %s, 'admin')
                    ON CONFLICT (normalized_alias) DO NOTHING
                """, (merge_into_id, proposed_name, norm))
                cur.execute("""
                    UPDATE pending_machine_types
                    SET resolution = 'auto_aliased', resolved_at = NOW()
                    WHERE id = %s
                """, (pending_id,))
                conn.commit()
                conn.close()
                invalidate_cache()
                return {"status": "aliased", "alias_text": proposed_name, "machine_type_id": merge_into_id}

            elif action == "promote":
                name = (new_type_name or proposed_name).strip()
                cur.execute("""
                    INSERT INTO machine_types
                        (name, normalized_name, requires_patentino, requires_verifiche, is_verified)
                    VALUES (%s, %s, %s, %s, true)
                    ON CONFLICT (normalized_name) DO NOTHING
                    RETURNING id
                """, (name, _normalize(name), new_requires_patentino, new_requires_verifiche))
                result = cur.fetchone()
                cur.execute("""
                    UPDATE pending_machine_types
                    SET resolution = 'promoted', resolved_at = NOW()
                    WHERE id = %s
                """, (pending_id,))
                conn.commit()
                conn.close()
                invalidate_cache()
                new_id = result[0] if result else None
                return {"status": "promoted", "name": name, "id": new_id}

            elif action == "reject":
                cur.execute("""
                    UPDATE pending_machine_types
                    SET resolution = 'rejected', resolved_at = NOW()
                    WHERE id = %s
                """, (pending_id,))
                conn.commit()
                conn.close()
                return {"status": "rejected"}

            conn.close()
            return {"status": "unknown_action"}
    except Exception as e:
        logger.error("admin_resolve_pending: %s", e)
        return {"status": "error", "detail": str(e)}


def admin_get_aliases(machine_type_id: int) -> list[dict]:
    """Ritorna tutti gli alias di un tipo macchina."""
    if not settings.database_url:
        return []
    try:
        import psycopg2.extras
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, alias_text, source, created_at
                FROM machine_aliases
                WHERE machine_type_id = %s
                ORDER BY source, alias_text
            """, (machine_type_id,))
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error("admin_get_aliases: %s", e)
        return []


def admin_add_alias(machine_type_id: int, alias_text: str) -> dict:
    """Aggiunge un alias manuale a un tipo macchina esistente."""
    if not settings.database_url:
        return {"status": "no_db"}
    alias_text = alias_text.strip()
    if not alias_text:
        return {"status": "empty"}
    norm = _normalize(alias_text)
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO machine_aliases (machine_type_id, alias_text, normalized_alias, source)
                VALUES (%s, %s, %s, 'admin')
                ON CONFLICT (normalized_alias) DO NOTHING
                RETURNING id
            """, (machine_type_id, alias_text, norm))
            row = cur.fetchone()
        conn.commit()
        conn.close()
        invalidate_cache()
        if row:
            return {"status": "ok", "id": row[0], "alias_text": alias_text}
        return {"status": "duplicate"}
    except Exception as e:
        logger.error("admin_add_alias: %s", e)
        return {"status": "error", "detail": str(e)}


def admin_delete_alias(alias_id: int) -> dict:
    """Elimina un alias."""
    if not settings.database_url:
        return {"status": "no_db"}
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM machine_aliases WHERE id = %s AND source != 'admin' OR id = %s",
                        (alias_id, alias_id))
            deleted = cur.rowcount
        conn.commit()
        conn.close()
        invalidate_cache()
        return {"status": "ok", "deleted": deleted}
    except Exception as e:
        logger.error("admin_delete_alias: %s", e)
        return {"status": "error", "detail": str(e)}


def admin_update_flags(machine_type_id: int,
                       requires_patentino: bool,
                       requires_verifiche: bool,
                       inail_search_hint: Optional[str] = None,
                       vita_utile_anni: Optional[int] = None) -> dict:
    """Aggiorna i flag normativi, l'hint INAIL e la vita utile di un tipo macchina."""
    if not settings.database_url:
        return {"status": "no_db"}
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE machine_types
                SET requires_patentino = %s,
                    requires_verifiche = %s,
                    inail_search_hint  = %s,
                    vita_utile_anni    = %s
                WHERE id = %s
            """, (
                requires_patentino,
                requires_verifiche,
                inail_search_hint.strip() if inail_search_hint else None,
                vita_utile_anni,
                machine_type_id,
            ))
        conn.commit()
        conn.close()
        invalidate_cache()
        return {"status": "ok"}
    except Exception as e:
        logger.error("admin_update_flags: %s", e)
        return {"status": "error", "detail": str(e)}


def admin_get_stats() -> dict:
    """Statistiche per il pannello admin: usage, pending, tipi più usati."""
    if not settings.database_url:
        return {"error": "no_db"}
    try:
        import psycopg2.extras
        conn = _get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS total FROM machine_types WHERE is_verified = true")
            total_types = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM machine_aliases")
            total_aliases = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM pending_machine_types WHERE resolution = 'pending'")
            pending_count = cur.fetchone()["total"]

            cur.execute("""
                SELECT id, name, usage_count, requires_patentino, requires_verifiche
                FROM machine_types
                WHERE is_verified = true
                ORDER BY usage_count DESC
                LIMIT 10
            """)
            top_types = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT proposed_name, proposed_by, created_at
                FROM pending_machine_types
                WHERE resolution = 'pending'
                  AND created_at < NOW() - INTERVAL '7 days'
                ORDER BY created_at
            """)
            stale_pending = [dict(r) for r in cur.fetchall()]

        conn.close()
        return {
            "total_types": total_types,
            "total_aliases": total_aliases,
            "pending_count": pending_count,
            "top_types": top_types,
            "stale_pending": stale_pending,
        }
    except Exception as e:
        logger.error("admin_get_stats: %s", e)
        return {"error": str(e)}


# ── Vita utile ────────────────────────────────────────────────────────────────

async def admin_populate_vita_utile(provider: str) -> dict:
    """
    Usa l'AI per popolare vita_utile_anni per tutti i machine_types con valore NULL.
    Ritorna {populated: N, skipped: M, errors: K}.
    """
    if not settings.database_url:
        return {"error": "no_db"}
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM machine_types WHERE is_verified = true AND vita_utile_anni IS NULL ORDER BY name")
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        return {"error": str(e)}

    populated = 0
    skipped = 0
    errors = 0

    from app.services.analysis_service import _call_ai_with_text

    for (mt_id, name) in rows:
        prompt = (
            f"Quanti anni è la vita utile tipica di una '{name}' secondo normativa italiana e best practice industriale?\n"
            f"Considera standard come ISO, EN, D.Lgs 81/08 e prassi manutentiva del settore.\n"
            f"Rispondi SOLO con un numero intero (es. 10). Nessun testo aggiuntivo."
        )
        try:
            result_text = await _call_ai_with_text("", prompt, provider, is_fallback=True)
            # La funzione ritorna un dict; se l'AI ha risposto con testo puro, prova a parsare
            anni = None
            if isinstance(result_text, dict):
                # In caso l'AI risponda in JSON per errore
                for v in result_text.values():
                    try:
                        anni = int(str(v).strip())
                        break
                    except Exception:
                        pass
            elif isinstance(result_text, (int, float)):
                anni = int(result_text)
            else:
                # Stringa: estrai il primo numero
                import re as _re
                m = _re.search(r'\d+', str(result_text))
                if m:
                    anni = int(m.group())
            if anni and 1 <= anni <= 100:
                conn = _get_conn()
                with conn.cursor() as cur:
                    cur.execute("UPDATE machine_types SET vita_utile_anni = %s WHERE id = %s", (anni, mt_id))
                conn.commit()
                conn.close()
                populated += 1
            else:
                skipped += 1
        except Exception as ex:
            logger.warning("populate_vita_utile: errore per '%s': %s", name, ex)
            errors += 1

    invalidate_cache()
    return {"populated": populated, "skipped": skipped, "errors": errors}


# ── Hazard Intelligence ───────────────────────────────────────────────────────

def get_hazard(machine_type_id: int) -> Optional[dict]:
    """Restituisce i dati hazard per un tipo macchina, o None se non presenti."""
    if not settings.database_url:
        return None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, categoria_inail, focus_testo, aggiornato_da, last_updated "
                "FROM machine_type_hazard WHERE machine_type_id = %s",
                (machine_type_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0],
            "categoria_inail": row[1],
            "focus_testo": row[2],
            "aggiornato_da": row[3],
            "last_updated": row[4].isoformat() if row[4] else None,
        }
    except Exception as e:
        logger.warning("get_hazard: %s", e)
        return None


def admin_upsert_hazard(machine_type_id: int, categoria_inail: str, focus_testo: str, by: str = "admin") -> None:
    """Inserisce o aggiorna i dati hazard per un tipo macchina."""
    if not settings.database_url:
        return
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO machine_type_hazard (machine_type_id, categoria_inail, focus_testo, aggiornato_da, last_updated)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (machine_type_id) DO UPDATE
                    SET categoria_inail = EXCLUDED.categoria_inail,
                        focus_testo     = EXCLUDED.focus_testo,
                        aggiornato_da   = EXCLUDED.aggiornato_da,
                        last_updated    = NOW()
            """, (machine_type_id, categoria_inail, focus_testo, by))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("admin_upsert_hazard: %s", e)


async def admin_populate_hazard(provider: str) -> dict:
    """
    Usa l'AI per generare i dati hazard per tutti i machine_types
    senza hazard o con hazard più vecchio di 90 giorni.
    """
    if not settings.database_url:
        return {"error": "no_db"}
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT mt.id, mt.name
                FROM machine_types mt
                LEFT JOIN machine_type_hazard h ON h.machine_type_id = mt.id
                WHERE mt.is_verified = true
                  AND (h.id IS NULL OR h.last_updated < NOW() - INTERVAL '90 days')
                ORDER BY mt.name
            """)
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        return {"error": str(e)}

    populated = 0
    skipped = 0
    errors = 0

    from app.services.analysis_service import _call_ai_with_text

    for (mt_id, name) in rows:
        prompt = (
            f"Sei un esperto di sicurezza sul lavoro italiano con conoscenza delle statistiche INAIL.\n\n"
            f"Per la categoria macchina: '{name}'\n\n"
            f"Fornisci un JSON con:\n"
            f'{{\n'
            f'  "categoria_inail": "nome della categoria agente materiale INAIL più corrispondente (es. \'Macchine per la lavorazione del legno\', \'Apparecchi di sollevamento\', \'Macchine agricole\')",\n'
            f'  "focus_testo": "2-3 frasi per l\'ispettore sui rischi statisticamente più frequenti in questa categoria secondo i dati INAIL. Cita percentuali o dati se noti. Es: \'Il contatto con organi in movimento rappresenta il 60% degli infortuni gravi in questa categoria. Verificare con priorità assoluta la protezione della lama e i ripari fissi degli organi di trasmissione.\' Usa un tono tecnico-operativo."\n'
            f'}}\n\n'
            f"Basati sulla tua conoscenza delle statistiche INAIL e delle norme italiane.\n"
            f"Rispondi SOLO con il JSON valido."
        )
        try:
            result = await _call_ai_with_text("", prompt, provider, is_fallback=True)
            categoria = result.get("categoria_inail", "").strip() if isinstance(result, dict) else ""
            focus = result.get("focus_testo", "").strip() if isinstance(result, dict) else ""
            if categoria and focus:
                admin_upsert_hazard(mt_id, categoria, focus, "ai")
                populated += 1
            else:
                skipped += 1
        except Exception as ex:
            logger.warning("populate_hazard: errore per '%s': %s", name, ex)
            errors += 1

    return {"populated": populated, "skipped": skipped, "errors": errors}


# ── Quaderno INAIL locale ─────────────────────────────────────────────────────

async def admin_populate_inail_hint(provider: str) -> dict:
    """
    Usa l'AI per associare automaticamente il quaderno INAIL locale (inail_search_hint)
    ai machine_types che hanno il campo NULL.
    Ritorna {populated: N, skipped: M, errors: K}.
    """
    if not settings.database_url:
        return {"error": "no_db"}

    # Carica i file disponibili su disco
    from app.services.local_manuals_service import PDF_MANUALS_DIR, LOCAL_MANUALS_MAP
    available_files: list[dict] = []
    seen_files: set = set()
    for filename in LOCAL_MANUALS_MAP.values():
        if filename not in seen_files:
            seen_files.add(filename)
            available_files.append({"filename": filename, "title": filename.replace(".pdf", "").strip()})
    if PDF_MANUALS_DIR.exists():
        for f in sorted(PDF_MANUALS_DIR.glob("*.pdf")):
            if f.name not in seen_files:
                seen_files.add(f.name)
                available_files.append({"filename": f.name, "title": f.name.replace(".pdf", "").strip()})

    if not available_files:
        return {"error": "no_files", "message": "Nessun quaderno INAIL trovato nella cartella 'pdf manuali'."}

    # Recupera machine_types senza inail_search_hint
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM machine_types WHERE is_verified = true AND inail_search_hint IS NULL ORDER BY name"
            )
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        return {"error": str(e)}

    populated = 0
    skipped = 0
    errors = 0

    from app.services.analysis_service import _call_ai_with_text
    valid_filenames = {f["filename"] for f in available_files}
    files_list = "\n".join(f'  - "{f["filename"]}"' for f in available_files)

    for (mt_id, name) in rows:
        prompt = (
            f"Sei un esperto di sicurezza sul lavoro italiano con conoscenza delle schede INAIL.\n\n"
            f"Categoria macchina: '{name}'\n\n"
            f"Quaderni INAIL disponibili:\n{files_list}\n\n"
            f"Indica il quaderno più pertinente per questa categoria. Se nessuno è adatto, rispondi null.\n\n"
            f"Rispondi SOLO con questo JSON (senza testo aggiuntivo):\n"
            f'{{"filename": "nome-file-esatto.pdf"}}\n'
            f"oppure: {{\"filename\": null}}\n\n"
            f"Il valore di 'filename' deve essere identico a uno dei nomi elencati sopra."
        )
        try:
            result = await _call_ai_with_text("", prompt, provider, is_fallback=True)
            filename = result.get("filename") if isinstance(result, dict) else None
            if filename and filename in valid_filenames:
                conn = _get_conn()
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE machine_types SET inail_search_hint = %s WHERE id = %s",
                        (filename, mt_id),
                    )
                conn.commit()
                conn.close()
                populated += 1
            else:
                skipped += 1
        except Exception as ex:
            logger.warning("populate_inail_hint: errore per '%s': %s", name, ex)
            errors += 1

    return {"populated": populated, "skipped": skipped, "errors": errors}
