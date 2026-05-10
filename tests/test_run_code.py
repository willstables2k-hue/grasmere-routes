from __future__ import annotations

from grasmere_routes.run_code import (
    DAY_FRI,
    DAY_THU,
    DAY_TUE,
    decode_run_code,
)


def test_wp0_decodes() -> None:
    d = decode_run_code("'WP0'")
    assert d.unparseable is False
    assert d.is_mail_order is False
    assert d.by_day[DAY_TUE] == "White"
    assert d.by_day[DAY_THU] == "Pink"
    assert d.by_day[DAY_FRI] is None


def test_o_and_zero_both_mean_no_van() -> None:
    assert decode_run_code("'GOG'").by_day[DAY_THU] is None
    assert decode_run_code("'GO0'").by_day[DAY_THU] is None
    assert decode_run_code("'GO0'").by_day[DAY_FRI] is None


def test_nr_is_mail_order() -> None:
    d = decode_run_code("'~NR'")
    assert d.is_mail_order is True
    assert d.unparseable is False


def test_unparseable_letters() -> None:
    assert decode_run_code("'5ME'").unparseable is True
    assert decode_run_code("'MMR'").unparseable is True


def test_wrong_length_unparseable() -> None:
    assert decode_run_code("'W'").unparseable is True
    assert decode_run_code("'WPRR'").unparseable is True
    assert decode_run_code("").unparseable is True
