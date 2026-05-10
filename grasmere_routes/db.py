"""Postgres engine + cached query helper.

Mirrors the pattern used in `grasmere-sales-dashboard/lib/db.py` so the
two apps feel the same to maintain. Connection comes from
`st.secrets["BRAIN_DB_URL"]` (or env `BRAIN_DB_URL` for non-Streamlit
contexts like the test suite + migration script).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

SQL_DIR = Path(__file__).parent / "sql"


def _to_sqlalchemy_url(raw: str) -> str:
    """Normalise postgres:// → postgresql+psycopg:// (Supabase quirk)."""
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://") and "+psycopg" not in raw:
        raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


def _resolve_url() -> str:
    # Try Streamlit secrets first (only available when running under Streamlit)
    try:
        import streamlit as st  # type: ignore

        if "BRAIN_DB_URL" in st.secrets:
            return _to_sqlalchemy_url(st.secrets["BRAIN_DB_URL"])
    except Exception:
        pass
    raw = os.environ.get("BRAIN_DB_URL") or os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError(
            "BRAIN_DB_URL not set — add it to .streamlit/secrets.toml or env"
        )
    return _to_sqlalchemy_url(raw)


@lru_cache(maxsize=1)
def engine() -> Engine:
    return create_engine(_resolve_url(), pool_pre_ping=True, future=True)


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Synchronous read query → DataFrame. Cache at the page level via
    @st.cache_data on the calling function — this layer stays unmemoised
    so writes are seen immediately."""
    with engine().connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params or {})


def execute(sql: str, params: dict | None = None) -> None:
    with engine().begin() as conn:
        conn.execute(text(sql), params or {})


def execute_many(sql: str, rows: list[dict]) -> None:
    if not rows:
        return
    with engine().begin() as conn:
        conn.execute(text(sql), rows)


def execute_returning(sql: str, params: dict | None = None) -> list[dict]:
    with engine().begin() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(r._mapping) for r in result]


def run_migrations() -> None:
    """Apply every .sql file in grasmere_routes/sql/ in alphabetical order.
    Idempotent — files are written with IF NOT EXISTS / OR REPLACE."""
    files = sorted(SQL_DIR.glob("*.sql"))
    with engine().begin() as conn:
        for f in files:
            sql = f.read_text(encoding="utf-8")
            conn.exec_driver_sql(sql)
