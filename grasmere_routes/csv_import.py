"""Importer for the Fresho-style customer CSV (449 rows in the supplied export).

Key headers carry a literal ' (do not edit)' suffix — the column constants
must match exactly.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

# ---------- types ----------


@dataclass
class ImportRow:
    customer_code: str
    name: str
    legal_entity_name: str | None
    delivery_address: str | None
    billing_address: str | None
    pricing_level: str | None
    is_cod: bool
    payment_term_days: int | None
    sales_rep: str | None
    delivery_days_group: str | None
    preferred_days: list[int] | None
    legacy_run_code: str | None
    legacy_run_position: int | None
    standing_picking_instructions: str | None
    standing_delivery_instructions: str | None
    soft_window_start: str | None
    soft_window_end: str | None
    last_delivery_date: date | None
    active: bool
    raw_csv_row: dict[str, str]
    flagged_for_review: bool = False
    flag_reasons: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    rows: list[ImportRow]
    errors: list[tuple[int, str]]


# ---------- helpers ----------


def _strip_quotes(v: str | None) -> str:
    return (v or "").strip().strip("'").strip()


def _non_empty(v: str | None) -> str | None:
    s = (v or "").strip()
    return s if s else None


def parse_uk_date(s: str | None) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if not m:
        return None
    d, mo, y = m.groups()
    try:
        return date(int(y), int(mo), int(d))
    except ValueError:
        return None


_DAY_TOKENS = {
    "MON": 0, "MONDAY": 0,
    "TUE": 1, "TUES": 1, "TUESDAY": 1,
    "WED": 2, "WEDS": 2, "WEDNESDAY": 2,
    "THU": 3, "THUR": 3, "THURS": 3, "THURSDAY": 3,
    "FRI": 4, "FRIDAY": 4,
    "SAT": 5, "SATURDAY": 5,
    "SUN": 6, "SUNDAY": 6,
}


def parse_day_group(group: str | None) -> list[int] | None:
    raw = (group or "").strip()
    if not raw:
        return None
    if raw.lower() == "default":
        return [1, 3]  # Tue + Thu

    tokens = re.split(r"[\s/,]+", raw.upper())
    matched: set[int] = set()
    unknown = 0
    for t in tokens:
        if not t:
            continue
        if t in _DAY_TOKENS:
            matched.add(_DAY_TOKENS[t])
        else:
            unknown += 1
    if not matched:
        return None
    if unknown > len(matched) * 2:
        return None
    return sorted(matched)


def _to_24h(h: str, m: str | None, ampm: str | None) -> str | None:
    try:
        hh = int(h)
        mm = int(m) if m else 0
    except ValueError:
        return None
    if hh > 23 or mm > 59:
        return None
    if ampm == "PM" and hh < 12:
        hh += 12
    if ampm == "AM" and hh == 12:
        hh = 0
    return f"{hh:02d}:{mm:02d}"


def extract_soft_window(text: str | None) -> tuple[str | None, str | None]:
    t = (text or "").upper()
    if not t:
        return None, None

    m = re.search(
        r"BETWEEN\s+(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?\s+AND\s+(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?",
        t,
    )
    if m:
        start = _to_24h(m.group(1), m.group(2), m.group(3))
        end_ampm = m.group(6) or m.group(3)
        end = _to_24h(m.group(4), m.group(5), end_ampm)
        if start and end:
            return start, end

    m = re.search(r"(?:BEFORE|BY)\s+(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?", t)
    if m:
        end = _to_24h(m.group(1), m.group(2), m.group(3))
        if end:
            return None, end

    m = re.search(r"(?:AFTER|FROM)\s+(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?", t)
    if m:
        start = _to_24h(m.group(1), m.group(2), m.group(3))
        if start:
            return start, None

    m = re.search(
        r"OPENING\s+TIMES?[:\s]+(\d{1,2})[:.](\d{2})\s*(AM|PM)?\s*[-–TO\s]+\s*(\d{1,2})[:.](\d{2})\s*(AM|PM)?",
        t,
    )
    if m:
        start = _to_24h(m.group(1), m.group(2), m.group(3))
        end = _to_24h(m.group(4), m.group(5), m.group(6))
        if start and end:
            return start, end

    return None, None


def _detect_cod(invoice_notes: str | None) -> bool:
    s = (invoice_notes or "").upper()
    return bool(s) and (re.search(r"\bCOD\b", s) is not None or "CHEQUE/COD" in s)


# ---------- column mapping (exact CSV headers, including " (do not edit)" suffix) ----------

COL = {
    "name": "customer_name (do not edit)",
    "legal": "legal_entity_name (do not edit)",
    "delivery": "delivery_address (do not edit)",
    "billing": "billing_address (do not edit)",
    "last_date": "latest_delivery_date (do not edit)",
    "code": "customer_code",
    "active": "active (Yes or No)",
    "pricing": "pricing_level",
    "invoice_notes": "invoice_notes",
    "picking": "standing_picking_instructions",
    "deliv_instr": "standing_delivery_instructions",
    "run_code": "delivery_run_code",
    "run_pos": "delivery_run_position",
    "days_group": "delivery_days_and_cut_off_times_group",
    "payment_days": "payment_term_days",
    "sales_rep": "sales_rep",
}


def parse_customer_csv(csv_text: str) -> ParseResult:
    rows: list[ImportRow] = []
    errors: list[tuple[int, str]] = []

    reader = csv.DictReader(io.StringIO(csv_text))
    for i, rec in enumerate(reader, start=2):  # line 1 = header
        name = _non_empty(rec.get(COL["name"]))
        code = _strip_quotes(rec.get(COL["code"]))
        if not code:
            errors.append((i, "missing customer_code"))
            continue
        if not name:
            errors.append((i, f"customer_code {code} missing name"))
            continue

        reasons: list[str] = []
        days_raw = rec.get(COL["days_group"])
        preferred_days = parse_day_group(days_raw)
        if preferred_days is None and _non_empty(days_raw):
            reasons.append(f"unparseable delivery_days_group: {days_raw}")

        win_start, win_end = extract_soft_window(rec.get(COL["deliv_instr"]))

        try:
            run_pos = int(_strip_quotes(rec.get(COL["run_pos"])) or "")
        except ValueError:
            run_pos = None
        try:
            payment_days = int((rec.get(COL["payment_days"]) or "").strip() or "")
        except ValueError:
            payment_days = None

        rows.append(
            ImportRow(
                customer_code=code,
                name=name,
                legal_entity_name=_non_empty(rec.get(COL["legal"])),
                delivery_address=_non_empty(rec.get(COL["delivery"])),
                billing_address=_non_empty(rec.get(COL["billing"])),
                pricing_level=_non_empty(rec.get(COL["pricing"])),
                is_cod=_detect_cod(rec.get(COL["invoice_notes"])),
                payment_term_days=payment_days,
                sales_rep=_non_empty(rec.get(COL["sales_rep"])),
                delivery_days_group=_non_empty(rec.get(COL["days_group"])),
                preferred_days=preferred_days,
                legacy_run_code=_strip_quotes(rec.get(COL["run_code"])) or None,
                legacy_run_position=run_pos,
                standing_picking_instructions=_non_empty(rec.get(COL["picking"])),
                standing_delivery_instructions=_non_empty(rec.get(COL["deliv_instr"])),
                soft_window_start=win_start,
                soft_window_end=win_end,
                last_delivery_date=parse_uk_date(rec.get(COL["last_date"])),
                active=(rec.get(COL["active"]) or "").strip().lower() == "yes",
                raw_csv_row={k: v for k, v in rec.items() if v is not None},
                flagged_for_review=bool(reasons),
                flag_reasons=reasons,
            )
        )

    return ParseResult(rows=rows, errors=errors)
