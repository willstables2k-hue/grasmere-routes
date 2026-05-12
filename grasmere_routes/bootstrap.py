"""Page bootstrap helpers — pre-flight checks that show a friendly setup
screen when secrets are missing or migrations haven't been applied yet.

Every page calls require_database() right after require_user(), so the
user always sees a clear next-step instead of a Python traceback."""

from __future__ import annotations

import streamlit as st
from sqlalchemy import text

from .db import engine, is_db_configured


def _setup_screen(title: str, body_md: str) -> None:
    st.title(title)
    st.markdown(body_md)
    st.stop()


def require_database() -> None:
    if not is_db_configured():
        _setup_screen(
            "Grasmere Routes needs a database connection",
            """
            The app couldn't find a `BRAIN_DB_URL` value, so it doesn't know
            where to read or write data.

            **On Streamlit Community Cloud:**

            1. Open https://share.streamlit.io and pick this app.
            2. Click **Settings → Secrets**.
            3. Paste your Supabase connection string from the Brain project:

            ```toml
            BRAIN_DB_URL = "postgresql://USER:PASS@HOST:5432/postgres?sslmode=require"
            ```

            4. Click **Save**. The app reloads automatically.

            **Locally:** put the same line in `.streamlit/secrets.toml`, or set
            `BRAIN_DB_URL` as an environment variable. `LOCAL_DEV=1` bypasses
            the password gate but does NOT bypass this check — you still need
            a database to read.
            """,
        )

    # Quick schema check — if the customers table doesn't exist yet, prompt
    # the user to run migrations rather than crashing on the first SELECT.
    try:
        with engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM customers LIMIT 1"))
    except Exception as e:  # noqa: BLE001
        if "does not exist" in str(e) or "UndefinedTable" in type(e).__name__:
            _setup_screen(
                "The database is reachable but the schema is missing",
                """
                Run the migrations once — they're idempotent (every statement is
                `IF NOT EXISTS` / `OR REPLACE`) so it's safe to re-run any time.

                Locally:

                ```bash
                python -c "from grasmere_routes.db import run_migrations; run_migrations()"
                ```

                On Streamlit Cloud, the easiest path is to run that line locally
                pointed at the same `BRAIN_DB_URL`, then refresh this app.
                """,
            )
        # Any other error: surface it but don't stop the whole page
        st.error(f"Database error: {e}")
        st.stop()
