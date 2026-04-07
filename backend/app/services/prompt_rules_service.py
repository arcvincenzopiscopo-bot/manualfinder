"""
Cache TTL 15 min delle regole prompt per tipo macchina da Supabase (tabella machine_prompt_rules).
Permette di personalizzare il comportamento AI per categoria di macchina senza deploy.
"""
import time as _time
from typing import Optional
from app.config import settings

_cache: dict[str, dict] = {}
_cache_ts: float = 0.0
_TTL = 900  # 15 minuti


def get_rules_for_machine_type(machine_type: str) -> Optional[dict]:
    """
    Cerca la regola prompt per il tipo macchina specificato (match parziale).
    Ritorna None se non trovata o se il DB non è disponibile.
    Cache in-memory TTL 15 min.
    """
    global _cache, _cache_ts
    now = _time.monotonic()
    if now - _cache_ts > _TTL:
        _refresh_cache()
    if not machine_type:
        return None
    mt = machine_type.lower().strip()
    # Match esatto prima, poi parziale (es. "piattaforma aerea a braccio" → "piattaforma aerea")
    if mt in _cache:
        return _cache[mt]
    for key, rule in _cache.items():
        if key in mt or mt in key:
            return rule
    return None


def _refresh_cache() -> None:
    global _cache, _cache_ts
    if not settings.database_url:
        _cache_ts = _time.monotonic()  # Evita refresh continui se DB non configurato
        return
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(settings.database_url)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM machine_prompt_rules WHERE is_active = true ORDER BY machine_type"
            )
            rows = cur.fetchall()
        conn.close()
        _cache = {r["machine_type"].lower().strip(): dict(r) for r in rows}
        _cache_ts = _time.monotonic()
    except Exception:
        _cache_ts = _time.monotonic()  # Segna come "aggiornato" per evitare retry loop


def invalidate_cache() -> None:
    """Invalida la cache — chiamato dopo ogni modifica alle regole."""
    global _cache_ts
    _cache_ts = 0.0
