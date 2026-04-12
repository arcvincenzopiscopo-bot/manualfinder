"""
Config service: accesso centralizzato a liste, mappe, domini e brand-hints modificabili
dal pannello admin (rimpiazza costanti hardcoded sparse nel codice).

Tabelle: config_lists, config_maps, domain_classifications, brand_machine_type_hints.

Uso tipico:
    from app.services.config_service import get_list, get_map
    safety_kw = get_list("safety_keywords")
    badge_labels = get_map("badge_labels")

Cache in-process: ogni get_* popola una cache invalidata da invalidate_cache()
(chiamato da endpoint admin dopo scritture).
"""
import json
import logging
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ── Cache in-process ─────────────────────────────────────────────────────────
_lists_cache: dict[str, set[str]] = {}
_maps_cache: dict[str, dict[str, Any]] = {}
_domains_cache: dict[str, set[str]] = {}          # kind → set(domain)
_brand_hints_cache: Optional[list[dict]] = None   # lista ordinata di righe


def invalidate_cache() -> None:
    global _lists_cache, _maps_cache, _domains_cache, _brand_hints_cache
    _lists_cache = {}
    _maps_cache = {}
    _domains_cache = {}
    _brand_hints_cache = None


def _conn():
    if not settings.database_url:
        return None
    try:
        import psycopg2
        return psycopg2.connect(settings.database_url)
    except Exception as e:
        logger.warning("config_service: connessione DB fallita: %s", e)
        return None


# ── config_lists ─────────────────────────────────────────────────────────────

def get_list(list_key: str, fallback: Optional[set[str]] = None) -> set[str]:
    """Ritorna il set degli item attivi per la lista. Fallback in caso di errore DB."""
    if list_key in _lists_cache:
        return _lists_cache[list_key]
    conn = _conn()
    if conn is None:
        return set(fallback or [])
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT item FROM config_lists WHERE list_key = %s AND active = true",
                (list_key,),
            )
            items = {row[0] for row in cur.fetchall()}
        _lists_cache[list_key] = items
        return items if items else set(fallback or [])
    except Exception as e:
        logger.warning("get_list(%s) fallito: %s", list_key, e)
        return set(fallback or [])
    finally:
        conn.close()


def get_list_with_meta(list_key: str) -> list[dict]:
    """Ritorna [{item, meta}] per la lista — utile quando meta contiene pesi/descrizioni."""
    conn = _conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT item, meta FROM config_lists WHERE list_key=%s AND active=true ORDER BY item",
                (list_key,),
            )
            return [{"item": r[0], "meta": r[1]} for r in cur.fetchall()]
    except Exception as e:
        logger.warning("get_list_with_meta(%s) fallito: %s", list_key, e)
        return []
    finally:
        conn.close()


def list_keys() -> list[str]:
    conn = _conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT list_key FROM config_lists ORDER BY list_key")
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def seed_list_if_empty(list_key: str, items: set[str], meta_by_item: Optional[dict] = None) -> int:
    """Se la lista è vuota, la popola. Ritorna numero inseriti."""
    conn = _conn()
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM config_lists WHERE list_key=%s LIMIT 1", (list_key,))
            if cur.fetchone():
                return 0
            inserted = 0
            for it in items:
                meta = (meta_by_item or {}).get(it)
                cur.execute(
                    "INSERT INTO config_lists (list_key, item, meta) VALUES (%s, %s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (list_key, it, json.dumps(meta) if meta is not None else None),
                )
                inserted += cur.rowcount
            conn.commit()
            return inserted
    except Exception as e:
        logger.warning("seed_list_if_empty(%s) fallito: %s", list_key, e)
        return 0
    finally:
        conn.close()


def add_list_item(list_key: str, item: str, meta: Optional[dict] = None) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO config_lists (list_key, item, meta, active) VALUES (%s,%s,%s,true) "
                "ON CONFLICT (list_key, item) DO UPDATE SET active=true, meta=EXCLUDED.meta",
                (list_key, item, json.dumps(meta) if meta is not None else None),
            )
            conn.commit()
        invalidate_cache()
        return True
    finally:
        conn.close()


def delete_list_item(list_key: str, item: str) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM config_lists WHERE list_key=%s AND item=%s", (list_key, item))
            conn.commit()
        invalidate_cache()
        return True
    finally:
        conn.close()


# ── config_maps ──────────────────────────────────────────────────────────────

def get_map(map_key: str, fallback: Optional[dict] = None) -> dict[str, Any]:
    if map_key in _maps_cache:
        return _maps_cache[map_key]
    conn = _conn()
    if conn is None:
        return dict(fallback or {})
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT k, v FROM config_maps WHERE map_key=%s AND active=true",
                (map_key,),
            )
            rows = cur.fetchall()
        data = {k: v for k, v in rows}
        _maps_cache[map_key] = data
        return data if data else dict(fallback or {})
    except Exception as e:
        logger.warning("get_map(%s) fallito: %s", map_key, e)
        return dict(fallback or {})
    finally:
        conn.close()


def map_keys() -> list[str]:
    conn = _conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT map_key FROM config_maps ORDER BY map_key")
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def seed_map_if_empty(map_key: str, data: dict[str, Any]) -> int:
    conn = _conn()
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM config_maps WHERE map_key=%s LIMIT 1", (map_key,))
            if cur.fetchone():
                return 0
            inserted = 0
            for k, v in data.items():
                cur.execute(
                    "INSERT INTO config_maps (map_key, k, v) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    (map_key, str(k), json.dumps(v)),
                )
                inserted += cur.rowcount
            conn.commit()
            return inserted
    except Exception as e:
        logger.warning("seed_map_if_empty(%s) fallito: %s", map_key, e)
        return 0
    finally:
        conn.close()


def set_map_entry(map_key: str, k: str, v: Any) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO config_maps (map_key, k, v, active) VALUES (%s,%s,%s,true) "
                "ON CONFLICT (map_key, k) DO UPDATE SET v=EXCLUDED.v, active=true",
                (map_key, k, json.dumps(v)),
            )
            conn.commit()
        invalidate_cache()
        return True
    finally:
        conn.close()


def delete_map_entry(map_key: str, k: str) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM config_maps WHERE map_key=%s AND k=%s", (map_key, k))
            conn.commit()
        invalidate_cache()
        return True
    finally:
        conn.close()


def list_map_entries(map_key: str) -> list[dict]:
    conn = _conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT k, v FROM config_maps WHERE map_key=%s AND active=true ORDER BY k",
                (map_key,),
            )
            return [{"k": k, "v": v} for k, v in cur.fetchall()]
    finally:
        conn.close()


# ── domain_classifications ──────────────────────────────────────────────────

def get_domains(kind: str) -> set[str]:
    if kind in _domains_cache:
        return _domains_cache[kind]
    conn = _conn()
    if conn is None:
        return set()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT domain FROM domain_classifications WHERE kind=%s AND active=true",
                (kind,),
            )
            data = {r[0] for r in cur.fetchall()}
        _domains_cache[kind] = data
        return data
    except Exception as e:
        logger.warning("get_domains(%s) fallito: %s", kind, e)
        return set()
    finally:
        conn.close()


def get_domain_map_by_brand(kind: str) -> dict[str, str]:
    """Ritorna {brand: domain} per le righe che hanno brand valorizzato."""
    conn = _conn()
    if conn is None:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT brand, domain FROM domain_classifications "
                "WHERE kind=%s AND active=true AND brand IS NOT NULL",
                (kind,),
            )
            return {b.lower(): d for b, d in cur.fetchall()}
    except Exception as e:
        logger.warning("get_domain_map_by_brand(%s) fallito: %s", kind, e)
        return {}
    finally:
        conn.close()


def seed_domains_if_empty(kind: str, items: list[tuple[str, Optional[str]]]) -> int:
    """items: list of (domain, brand_or_None). Inserisce solo se non già presente per (domain,kind,brand)."""
    conn = _conn()
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM domain_classifications WHERE kind=%s LIMIT 1", (kind,))
            if cur.fetchone():
                return 0
            inserted = 0
            for domain, brand in items:
                cur.execute(
                    "INSERT INTO domain_classifications (domain, kind, brand) VALUES (%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    (domain, kind, brand),
                )
                inserted += cur.rowcount
            conn.commit()
            return inserted
    except Exception as e:
        logger.warning("seed_domains_if_empty(%s) fallito: %s", kind, e)
        return 0
    finally:
        conn.close()


def add_domain(domain: str, kind: str, brand: Optional[str] = None) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO domain_classifications (domain, kind, brand, active) VALUES (%s,%s,%s,true) "
                "ON CONFLICT (domain, kind, brand) DO UPDATE SET active=true",
                (domain, kind, brand),
            )
            conn.commit()
        invalidate_cache()
        return True
    finally:
        conn.close()


def delete_domain(row_id: int) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM domain_classifications WHERE id=%s", (row_id,))
            conn.commit()
        invalidate_cache()
        return True
    finally:
        conn.close()


def list_domains(kind: Optional[str] = None) -> list[dict]:
    conn = _conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            if kind:
                cur.execute(
                    "SELECT id, domain, kind, brand, active FROM domain_classifications "
                    "WHERE kind=%s ORDER BY domain",
                    (kind,),
                )
            else:
                cur.execute(
                    "SELECT id, domain, kind, brand, active FROM domain_classifications "
                    "ORDER BY kind, domain"
                )
            return [
                {"id": r[0], "domain": r[1], "kind": r[2], "brand": r[3], "active": r[4]}
                for r in cur.fetchall()
            ]
    finally:
        conn.close()


def domain_kinds() -> list[str]:
    conn = _conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT kind FROM domain_classifications ORDER BY kind")
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


# ── brand_machine_type_hints ────────────────────────────────────────────────

def get_brand_hints() -> list[dict]:
    """Lista di {brand, model_prefix, machine_type_text, machine_type_id}."""
    global _brand_hints_cache
    if _brand_hints_cache is not None:
        return _brand_hints_cache
    conn = _conn()
    if conn is None:
        _brand_hints_cache = []
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT brand, model_prefix, machine_type_text, machine_type_id "
                "FROM brand_machine_type_hints WHERE active=true"
            )
            _brand_hints_cache = [
                {"brand": r[0], "model_prefix": r[1], "machine_type_text": r[2], "machine_type_id": r[3]}
                for r in cur.fetchall()
            ]
        return _brand_hints_cache
    except Exception as e:
        logger.warning("get_brand_hints fallito: %s", e)
        _brand_hints_cache = []
        return []
    finally:
        conn.close()


def seed_brand_hints_if_empty(
    brand_map: dict[str, str],
    prefix_overrides: list[tuple[str, str, str]],
) -> int:
    """Seed iniziale da _BRAND_TYPE_MAP e _MODEL_PREFIX_OVERRIDES."""
    conn = _conn()
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM brand_machine_type_hints LIMIT 1")
            if cur.fetchone():
                return 0
            inserted = 0
            for brand, tipo in brand_map.items():
                cur.execute(
                    "INSERT INTO brand_machine_type_hints (brand, model_prefix, machine_type_text) "
                    "VALUES (%s, NULL, %s) ON CONFLICT DO NOTHING",
                    (brand, tipo),
                )
                inserted += cur.rowcount
            for brand, prefix, tipo in prefix_overrides:
                cur.execute(
                    "INSERT INTO brand_machine_type_hints (brand, model_prefix, machine_type_text) "
                    "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (brand, prefix, tipo),
                )
                inserted += cur.rowcount
            conn.commit()
            return inserted
    except Exception as e:
        logger.warning("seed_brand_hints_if_empty fallito: %s", e)
        return 0
    finally:
        conn.close()


def add_brand_hint(brand: str, machine_type_text: str, model_prefix: Optional[str] = None,
                   machine_type_id: Optional[int] = None) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO brand_machine_type_hints (brand, model_prefix, machine_type_text, machine_type_id, active) "
                "VALUES (%s,%s,%s,%s,true) "
                "ON CONFLICT (brand, model_prefix) DO UPDATE SET machine_type_text=EXCLUDED.machine_type_text, "
                "machine_type_id=EXCLUDED.machine_type_id, active=true",
                (brand.lower().strip(), model_prefix, machine_type_text, machine_type_id),
            )
            conn.commit()
        invalidate_cache()
        return True
    finally:
        conn.close()


def delete_brand_hint(row_id: int) -> bool:
    conn = _conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM brand_machine_type_hints WHERE id=%s", (row_id,))
            conn.commit()
        invalidate_cache()
        return True
    finally:
        conn.close()


def list_brand_hints() -> list[dict]:
    conn = _conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, brand, model_prefix, machine_type_text, machine_type_id, active "
                "FROM brand_machine_type_hints ORDER BY brand, COALESCE(model_prefix, '')"
            )
            return [
                {"id": r[0], "brand": r[1], "model_prefix": r[2],
                 "machine_type_text": r[3], "machine_type_id": r[4], "active": r[5]}
                for r in cur.fetchall()
            ]
    finally:
        conn.close()
