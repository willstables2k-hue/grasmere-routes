"""Customer status derivation. Mirrors the customer_status_v Postgres view
so we can apply the same rules in-memory during CSV import or tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

CustomerStatus = Literal["live", "dormant", "no_history"]


@dataclass(frozen=True)
class StatusResult:
    status: CustomerStatus
    days_since_last_delivery: int | None


def derive_status(
    *,
    last_delivery_date: date | None,
    manually_confirmed_live_at: datetime | None,
    threshold_days: int = 180,
    today: date | None = None,
) -> StatusResult:
    today = today or date.today()
    cutoff = today.toordinal() - threshold_days

    if manually_confirmed_live_at is not None:
        # Strip tz for comparison; treat naive as UTC
        confirm_date = (
            manually_confirmed_live_at.date()
            if manually_confirmed_live_at.tzinfo is None
            else manually_confirmed_live_at.astimezone(timezone.utc).date()
        )
        if confirm_date.toordinal() >= cutoff:
            days_since = (
                (today - last_delivery_date).days if last_delivery_date else None
            )
            return StatusResult("live", days_since)

    if last_delivery_date is None:
        return StatusResult("no_history", None)

    days = (today - last_delivery_date).days
    return StatusResult("live" if days <= threshold_days else "dormant", days)
