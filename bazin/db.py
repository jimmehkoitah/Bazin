"""Postgres access: connection pool, migrations and small query helpers."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import DB_DIR, get_settings

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """A pooled connection with an open transaction; commits on success, rolls back on error."""
    with pool().connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def jsonb(value: Any) -> Jsonb:
    """Wrap a Python value for a jsonb parameter."""
    return Jsonb(value)


def fetch_all(conn: psycopg.Connection, sql: str, params: Any = None) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def fetch_one(conn: psycopg.Connection, sql: str, params: Any = None) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(conn: psycopg.Connection, sql: str, params: Any = None) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def execute_many(conn: psycopg.Connection, sql: str, rows: list[Any]) -> None:
    if not rows:
        return
    with conn.cursor() as cur:
        cur.executemany(sql, rows)


def migration_files() -> list[Path]:
    """The canonical schema first, then incremental migrations in name order."""
    files = [DB_DIR / "schema.sql"]
    migrations = DB_DIR / "migrations"
    if migrations.exists():
        files.extend(sorted(p for p in migrations.iterdir() if p.suffix == ".sql"))
    return files


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply schema.sql (idempotent) and any migration not yet recorded. Returns names applied."""
    applied: list[str] = []
    with conn.cursor() as cur:
        # schema.sql is written with IF NOT EXISTS guards, so it is safe to apply every time;
        # it also creates schema_migrations.
        cur.execute((DB_DIR / "schema.sql").read_text())
        cur.execute("select name from schema_migrations")
        done = {r["name"] for r in cur.fetchall()}
        for path in migration_files()[1:]:
            if path.name in done:
                continue
            cur.execute(path.read_text())
            cur.execute("insert into schema_migrations (name) values (%s)", (path.name,))
            applied.append(path.name)
    return applied


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
