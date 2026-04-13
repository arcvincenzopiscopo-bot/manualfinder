"""
Pool di connessioni PostgreSQL centralizzato.

Tutti i service dovrebbero usare `get_conn()` da qui invece di creare
connessioni ad-hoc con `psycopg2.connect()`. Il pool viene inizializzato
lazy al primo uso e limita le connessioni simultanee (default: 2 min, 20 max).

`get_conn()` è un context manager. Uso:

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(...)
        conn.commit()

Per compatibilità con il codice esistente che fa `conn = _get_conn()` senza
`with`, è disponibile anche `get_conn_raw()` che restituisce un wrapper
che ritorna la connessione al pool quando viene chiusa con `conn.close()`.
"""
import logging
import threading
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.pool

from app.config import settings

_logger = logging.getLogger(__name__)

_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()

_MIN_CONN = 2
_MAX_CONN = 20


def _init_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL non configurata")
        _pool = psycopg2.pool.ThreadedConnectionPool(
            _MIN_CONN, _MAX_CONN, settings.database_url
        )
        _logger.info("Pool PostgreSQL inizializzato (min=%d, max=%d)", _MIN_CONN, _MAX_CONN)
        return _pool


@contextmanager
def get_conn():
    """
    Context manager che prende una connessione dal pool e la restituisce alla fine.
    """
    pool = _init_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


class _PooledConnection:
    """Wrapper che restituisce la connessione al pool su close()."""

    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, *args):
        return self._conn.__exit__(*args)

    def close(self):
        if self._conn is not None:
            self._pool.putconn(self._conn)
            self._conn = None

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)


def get_conn_raw():
    """
    Restituisce una connessione dal pool senza context manager.
    DEVE essere chiusa con conn.close() — che la restituisce al pool.
    Compatibile con il pattern `conn = _get_conn()`.
    """
    pool = _init_pool()
    conn = pool.getconn()
    return _PooledConnection(conn, pool)


def close_pool():
    """Chiude tutte le connessioni. Da chiamare allo shutdown dell'app."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
            _logger.info("Pool PostgreSQL chiuso")
