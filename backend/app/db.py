"""Postgres connection pool (sync, psycopg 3)."""
import logging
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings

logger = logging.getLogger(__name__)
_pool: ConnectionPool | None = None


def init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    s = get_settings()
    pool = ConnectionPool(
        conninfo=s.database_url,
        min_size=1,
        max_size=5,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            # Needed for Supabase's connection pooler (it can't keep prepared statements)
            "prepare_threshold": None,
        },
        check=ConnectionPool.check_connection,  # drop dead connections automatically
        open=False,
        timeout=30,
    )
    pool.open(wait=True, timeout=30)  # fail fast with a clear error if DB is unreachable
    _pool = pool
    logger.info("Database pool ready")


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_pool() -> ConnectionPool:
    if _pool is None:
        init_pool()
    assert _pool is not None
    return _pool


def fetch_all(sql: str, params: Any = None) -> list[dict]:
    with get_pool().connection() as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: Any = None) -> dict | None:
    with get_pool().connection() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: Any = None) -> None:
    with get_pool().connection() as conn:
        conn.execute(sql, params)
