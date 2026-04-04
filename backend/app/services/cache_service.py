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
    """Cache in-memory con scadenza TTL. Thread-safe per uso async."""

    def __init__(self, ttl: int = _TTL_SECONDS):
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl

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
        return value

    def set(self, *key_parts_and_value) -> None:
        *key_parts, value = key_parts_and_value
        k = self._make_key(*key_parts)
        self._store[k] = (time.time(), value)

    def evict_expired(self) -> int:
        now = time.time()
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]
        return len(expired)

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

    # Alias sincroni per retrocompatibilità (usano il fallback in-memory)
    def get(self, *key_parts) -> Optional[Any]:
        return self._fallback.get(*key_parts)

    def set(self, *key_parts_and_value) -> None:
        self._fallback.set(*key_parts_and_value)


def _build_cache():
    """Costruisce la cache giusta in base alla configurazione."""
    try:
        from app.config import settings
        redis_url = getattr(settings, "redis_url", None)
        if redis_url:
            return _RedisTTLCache(redis_url)
    except Exception:
        pass
    return _InMemoryTTLCache()


# Singleton globale — usato da search_service
search_cache = _build_cache()
