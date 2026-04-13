"""
Cache TTL in-memory per i risultati di ricerca manuale.
Evita di ripetere le stesse query API per brand+model già cercati.
TTL default: 7 giorni (i manuali non cambiano settimanalmente).
Redis opzionale: se disponibile, usa Redis per persistenza tra riavvii.
"""
import time
import hashlib
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_TTL_SECONDS = 7 * 24 * 3600  # 7 giorni


class _InMemoryTTLCache:
    """Cache in-memory con scadenza TTL e limite LRU."""

    _MAX_ITEMS = 500

    def __init__(self, ttl: int = _TTL_SECONDS, max_items: int = _MAX_ITEMS):
        from collections import OrderedDict
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._ttl = ttl
        self._max_items = max_items

    def _make_key(self, *parts) -> str:
        raw = "|".join(str(p).lower().strip() for p in parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, *key_parts) -> Optional[Any]:
        k = self._make_key(*key_parts)
        entry = self._store.get(k)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self._ttl:
            del self._store[k]
            return None
        self._store.move_to_end(k)
        return value

    def set(self, *key_parts_and_value) -> None:
        *key_parts, value = key_parts_and_value
        k = self._make_key(*key_parts)
        self._store[k] = (time.time(), value)
        self._store.move_to_end(k)
        while len(self._store) > self._max_items:
            self._store.popitem(last=False)

    def evict_expired(self) -> int:
        now = time.time()
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]
        return len(expired)

    def evict_containing_url(self, url: str) -> int:
        """Rimuove tutte le entry cache che contengono l'URL specificato tra i risultati."""
        url_lower = url.lower().strip()
        to_remove = []
        for k, (ts, value) in self._store.items():
            if isinstance(value, list):
                if any(
                    isinstance(r, dict) and r.get("url", "").lower().strip() == url_lower
                    for r in value
                ):
                    to_remove.append(k)
        for k in to_remove:
            del self._store[k]
        return len(to_remove)

    def size(self) -> int:
        return len(self._store)


class _RedisTTLCache:
    """Cache Redis con fallback in-memory se Redis non disponibile."""

    def __init__(self, redis_url: str, ttl: int = _TTL_SECONDS):
        self._ttl = ttl
        self._fallback = _InMemoryTTLCache(ttl)
        self._redis = None
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            logger.info("SearchCache: Redis connesso a %s", redis_url)
        except Exception as e:
            logger.warning("SearchCache: Redis non disponibile (%s), uso in-memory", e)

    def _make_key(self, *parts) -> str:
        raw = "|".join(str(p).lower().strip() for p in parts)
        return "mf:search:" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def get_async(self, *key_parts) -> Optional[Any]:
        if self._redis is None:
            return self._fallback.get(*key_parts)
        try:
            k = self._make_key(*key_parts)
            raw = await self._redis.get(k)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return self._fallback.get(*key_parts)

    async def set_async(self, *key_parts_and_value) -> None:
        *key_parts, value = key_parts_and_value
        if self._redis is None:
            self._fallback.set(*key_parts, value)
            return
        try:
            k = self._make_key(*key_parts)
            await self._redis.setex(k, self._ttl, json.dumps(value, ensure_ascii=False))
        except Exception:
            self._fallback.set(*key_parts, value)

    def evict_containing_url(self, url: str) -> int:
        """Delega al fallback in-memory (Redis non supporta scan per valore)."""
        return self._fallback.evict_containing_url(url)

    # Alias sincroni per retrocompatibilità (usano il fallback in-memory)
    def get(self, *key_parts) -> Optional[Any]:
        return self._fallback.get(*key_parts)

    def set(self, *key_parts_and_value) -> None:
        self._fallback.set(*key_parts_and_value)


class _PostgresTTLCache:
    """
    Cache persistente su Postgres (Supabase).
    Sopravvive ai riavvii del server — essenziale su container (Railway, Render).
    Tabella: search_cache_v1 (cache_key TEXT PK, data TEXT, ts FLOAT).
    Crea la tabella automaticamente se non esiste.
    Fallback in-memory se Postgres non disponibile.
    """

    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS search_cache_v1 (
            cache_key TEXT PRIMARY KEY,
            data      TEXT NOT NULL,
            ts        DOUBLE PRECISION NOT NULL
        )
    """

    def __init__(self, database_url: str, ttl: int = _TTL_SECONDS):
        self._db_url = database_url
        self._ttl = ttl
        self._fallback = _InMemoryTTLCache(ttl)
        self._ready = False
        try:
            import psycopg2
            conn = psycopg2.connect(database_url)
            with conn.cursor() as cur:
                cur.execute(self._CREATE_TABLE)
            conn.commit()
            conn.close()
            self._ready = True
            logger.info("SearchCache: Postgres cache attiva")
        except Exception as e:
            logger.warning("SearchCache: Postgres non disponibile (%s), uso in-memory", e)

    def _make_key(self, *parts) -> str:
        raw = "|".join(str(p).lower().strip() for p in parts)
        return "mf:" + hashlib.sha256(raw.encode()).hexdigest()[:20]

    def get(self, *key_parts) -> Optional[Any]:
        if not self._ready:
            return self._fallback.get(*key_parts)
        try:
            import psycopg2
            k = self._make_key(*key_parts)
            conn = psycopg2.connect(self._db_url)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data, ts FROM search_cache_v1 WHERE cache_key = %s", (k,)
                )
                row = cur.fetchone()
            conn.close()
            if row is None:
                return None
            data_str, ts = row
            if time.time() - ts > self._ttl:
                self._delete(k)
                return None
            return json.loads(data_str)
        except Exception:
            return self._fallback.get(*key_parts)

    def set(self, *key_parts_and_value) -> None:
        *key_parts, value = key_parts_and_value
        self._fallback.set(*key_parts, value)  # sempre aggiorna in-memory
        if not self._ready:
            return
        try:
            import psycopg2
            k = self._make_key(*key_parts)
            data_str = json.dumps(value, ensure_ascii=False)
            conn = psycopg2.connect(self._db_url)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO search_cache_v1 (cache_key, data, ts)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cache_key) DO UPDATE
                        SET data = EXCLUDED.data, ts = EXCLUDED.ts
                    """,
                    (k, data_str, time.time()),
                )
            conn.commit()
            conn.close()
        except Exception:
            pass  # fallback in-memory già aggiornato sopra

    def _delete(self, k: str) -> None:
        try:
            import psycopg2
            conn = psycopg2.connect(self._db_url)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM search_cache_v1 WHERE cache_key = %s", (k,))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def evict_containing_url(self, url: str) -> int:
        return self._fallback.evict_containing_url(url)

    def size(self) -> int:
        return self._fallback.size()


def _build_cache():
    """Costruisce la cache giusta in base alla configurazione."""
    try:
        from app.config import settings
        redis_url = getattr(settings, "redis_url", None)
        if redis_url:
            return _RedisTTLCache(redis_url)
        database_url = getattr(settings, "database_url", None)
        if database_url:
            return _PostgresTTLCache(database_url)
    except Exception:
        pass
    return _InMemoryTTLCache()


# Singleton globale — usato da search_service
search_cache = _build_cache()
