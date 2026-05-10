"""£ / km / min / % formatters used across the Streamlit pages."""

from __future__ import annotations


def fmt_gbp(pence: int | float | None, digits: int = 2) -> str:
    if pence is None:
        return "—"
    return f"£{pence / 100:,.{digits}f}"


def fmt_gbp_rounded(pence: int | float | None) -> str:
    if pence is None:
        return "—"
    return f"£{pence / 100:,.0f}"


def fmt_km(km: float | None) -> str:
    if km is None:
        return "—"
    return f"{km:,.1f} km"


def fmt_min(m: int | float | None) -> str:
    if m is None:
        return "—"
    m = int(m)
    if m < 60:
        return f"{m}m"
    h, mm = divmod(m, 60)
    return f"{h}h" if mm == 0 else f"{h}h {mm}m"


def fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def fmt_relative_days(days: int | None) -> str:
    if days is None:
        return "never"
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    if days < 365:
        return f"{round(days / 30)} months ago"
    return f"{round(days / 365)} years ago"
