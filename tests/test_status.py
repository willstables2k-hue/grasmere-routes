"""Mirror of apps/web/lib/status.test.ts (now retired)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from grasmere_routes.status import derive_status

TODAY = date(2026, 5, 9)


def days(n: int) -> date:
    return TODAY - timedelta(days=n)


def test_live_when_delivered_within_threshold() -> None:
    r = derive_status(
        last_delivery_date=days(45),
        manually_confirmed_live_at=None,
        threshold_days=180,
        today=TODAY,
    )
    assert r.status == "live"
    assert r.days_since_last_delivery == 45


def test_dormant_when_181_days_silent() -> None:
    r = derive_status(
        last_delivery_date=days(181),
        manually_confirmed_live_at=None,
        threshold_days=180,
        today=TODAY,
    )
    assert r.status == "dormant"


def test_no_history_when_null_date() -> None:
    r = derive_status(
        last_delivery_date=None,
        manually_confirmed_live_at=None,
        threshold_days=180,
        today=TODAY,
    )
    assert r.status == "no_history"
    assert r.days_since_last_delivery is None


def test_manual_confirm_overrides_dormancy() -> None:
    r = derive_status(
        last_delivery_date=days(400),
        manually_confirmed_live_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
        threshold_days=180,
        today=TODAY,
    )
    assert r.status == "live"


def test_old_manual_confirm_does_not_keep_live() -> None:
    r = derive_status(
        last_delivery_date=days(400),
        manually_confirmed_live_at=datetime(2025, 9, 1, tzinfo=timezone.utc),
        threshold_days=180,
        today=TODAY,
    )
    assert r.status == "dormant"
