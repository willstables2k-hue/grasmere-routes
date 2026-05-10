"""Decoder for legacy delivery_run_code values.

3 characters = [Tuesday, Thursday, Friday] colour assignments.
W=White, P=Pink, B=Blue, G=Green, R=Red, Y=Yellow.
0 or O = van not running that day.
~NR = mail order — exclude from baseline.

Codes that don't decode cleanly (e.g. '5ME', 'MMR') return unparseable=True.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DAY_TUE = 1
DAY_THU = 3
DAY_FRI = 4
RUN_DAYS: tuple[int, ...] = (DAY_TUE, DAY_THU, DAY_FRI)

VanColour = Literal["White", "Pink", "Blue", "Green", "Red", "Yellow"]

_COLOUR_MAP: dict[str, VanColour] = {
    "W": "White", "P": "Pink", "B": "Blue",
    "G": "Green", "R": "Red", "Y": "Yellow",
}


@dataclass(frozen=True)
class DecodedRunCode:
    raw: str
    is_mail_order: bool
    unparseable: bool
    by_day: dict[int, VanColour | None]


def decode_run_code(input_: str | None) -> DecodedRunCode:
    raw = (input_ or "").strip()
    cleaned = raw.strip("'").strip().upper()

    empty_by_day: dict[int, VanColour | None] = {DAY_TUE: None, DAY_THU: None, DAY_FRI: None}

    if not cleaned:
        return DecodedRunCode(raw, False, True, dict(empty_by_day))
    if cleaned in ("~NR", "NR"):
        return DecodedRunCode(raw, True, False, dict(empty_by_day))
    if len(cleaned) != 3:
        return DecodedRunCode(raw, False, True, dict(empty_by_day))

    by_day = dict(empty_by_day)
    days = [DAY_TUE, DAY_THU, DAY_FRI]
    for i, ch in enumerate(cleaned):
        if ch in ("0", "O"):
            by_day[days[i]] = None
            continue
        colour = _COLOUR_MAP.get(ch)
        if colour is None:
            return DecodedRunCode(raw, False, True, dict(empty_by_day))
        by_day[days[i]] = colour

    return DecodedRunCode(raw, False, False, by_day)


def active_days(decoded: DecodedRunCode) -> list[int]:
    return [d for d in RUN_DAYS if decoded.by_day.get(d) is not None]
