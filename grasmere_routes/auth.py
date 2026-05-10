"""Shared-password gate for the v1 launch.

A single team password lets anyone in. We dropped per-user OIDC for now to
get the team using the platform without a Google-OAuth setup; the role
plumbing (`require_role`) is preserved so re-introducing per-user identity
later is just an auth.py swap.

  - Default password: "grasmere2026"  (override via secrets.app.password)
  - LOCAL_DEV=1 env var bypasses the gate entirely for development
  - Successful login is remembered in st.session_state for the browser session
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

import streamlit as st

Role = Literal["admin", "dispatcher", "driver"]
DEFAULT_PASSWORD = "grasmere2026"


@dataclass(frozen=True)
class SessionUser:
    email: str
    name: str
    role: Role


def _local_dev() -> bool:
    return os.environ.get("LOCAL_DEV", "").lower() in ("1", "true", "yes")


def _expected_password() -> str:
    """Read from st.secrets.app.password if set, else the built-in default."""
    try:
        if hasattr(st, "secrets"):
            app_secrets = st.secrets.get("app", {})
            pw = app_secrets.get("password")
            if pw:
                return str(pw)
    except Exception:
        pass
    return DEFAULT_PASSWORD


def _team_user() -> SessionUser:
    return SessionUser(email="team@grasmerefarm.co.uk", name="Grasmere team", role="admin")


def require_user() -> SessionUser:
    """Block the page until the shared password has been entered."""
    if _local_dev():
        return SessionUser("dev@local", "Dev (local)", "admin")

    if st.session_state.get("authenticated"):
        return _team_user()

    st.title("Grasmere Routes")
    st.caption("Enter the shared team password to continue.")
    pw = st.text_input("Password", type="password", key="_login_pw")
    sign_in = st.button("Sign in", type="primary")
    if sign_in:
        if pw == _expected_password():
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


def require_role(*_allowed: Role) -> SessionUser:
    """Role gates are no-ops under the shared-password model — every
    authenticated user is `admin`. Kept as a function so pages don't have
    to change when per-user identity returns."""
    return require_user()
