"""Streamlit-native auth + role assignment.

Same pattern as grasmere-sales-dashboard:
  - st.login("google") + email allowlist in secrets
  - LOCAL_DEV bypass for development
  - role derived from secrets.app.roles dict {email: role}

Roles: admin / dispatcher / driver. Pages decide what they show based on role.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

import streamlit as st

Role = Literal["admin", "dispatcher", "driver"]


@dataclass(frozen=True)
class SessionUser:
    email: str
    name: str
    role: Role


def _local_dev() -> bool:
    return os.environ.get("LOCAL_DEV", "").lower() in ("1", "true", "yes")


def _allowed_emails() -> set[str]:
    raw = st.secrets.get("app", {}).get("allowed_emails", []) if hasattr(st, "secrets") else []
    return {e.strip().lower() for e in raw}


def _roles_map() -> dict[str, Role]:
    raw = st.secrets.get("app", {}).get("roles", {}) if hasattr(st, "secrets") else {}
    return {k.lower(): v for k, v in raw.items()}


def require_user() -> SessionUser:
    """Block the page until a logged-in, allow-listed user is present.
    Returns the SessionUser. In LOCAL_DEV always returns a fake admin."""
    if _local_dev():
        return SessionUser("dev@local", "Dev (local)", "admin")

    user = getattr(st, "user", None)
    if not user or not getattr(user, "is_logged_in", False):
        st.title("Grasmere Routes")
        st.write("Sign in with Google to continue.")
        st.button("Sign in with Google", on_click=st.login, args=("google",), type="primary")
        st.stop()

    email = (user.email or "").lower()
    allowed = _allowed_emails()
    if allowed and email not in allowed:
        st.error(f"{email} is not on the allowlist.")
        st.button("Sign out", on_click=st.logout)
        st.stop()

    role: Role = _roles_map().get(email, "dispatcher")
    return SessionUser(email=email, name=user.name or email, role=role)


def require_role(*allowed: Role) -> SessionUser:
    u = require_user()
    if u.role not in allowed:
        st.error(f"This page requires one of {allowed}; you are {u.role}.")
        st.stop()
    return u
