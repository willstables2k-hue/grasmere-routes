from __future__ import annotations

from datetime import date

import pytest

from grasmere_routes.csv_import import (
    extract_soft_window,
    parse_customer_csv,
    parse_day_group,
    parse_uk_date,
)

HEADER = (
    "customer_name (do not edit),legal_entity_name (do not edit),"
    "business_tax_number (do not edit),delivery_address (do not edit),"
    "billing_address (do not edit),latest_delivery_date (do not edit),"
    "customer_code,outbound_integration_customer_code,active (Yes or No),"
    "pricing_level,negotiated_prices_group,show_only_negotiated_pricing (Yes or No),"
    "auto_assign_last_price_as_negotiated_price (Yes or No),show_rrp (Yes or No),"
    "require_external_reference (Yes or No),minimum_order_amounts_enabled (Yes or No),"
    "preserve_original_line_item_sequence_in_invoice_documents (Yes or No),"
    "discount,rebate,invoice_notes,standing_picking_instructions,"
    "delivery_date_message,standing_delivery_instructions,delivery_run_code,"
    "delivery_run_position,freight_rule,delivery_fee_percentage,"
    "minimum_order_amount_for_freight,delivery_days_and_cut_off_times_group,"
    "payment_term_days,payment_term_option,sales_rep,internal_notes,"
    "internal_customer_contact_notes,automatically_charge_fuel_levy (Yes or No),"
    "charge_card (Yes or No),charge_customer_card_fee (Yes or No),"
    "visibility_groups (separated by '|'),tags (separated by '|'),"
    "agreement_id (do not edit)"
)


def _row(values: dict[str, str]) -> str:
    cols = HEADER.split(",")
    out = []
    for c in cols:
        v = values.get(c, "")
        if "," in v:
            v = '"' + v + '"'
        out.append(v)
    return ",".join(out)


def test_parse_uk_date_iso() -> None:
    assert parse_uk_date("21/08/2025") == date(2025, 8, 21)
    assert parse_uk_date("1/5/2026") == date(2026, 5, 1)


def test_parse_uk_date_blank_or_junk() -> None:
    assert parse_uk_date("") is None
    assert parse_uk_date("   ") is None
    assert parse_uk_date("21-08-2025") is None


@pytest.mark.parametrize(
    "input_,expected",
    [
        ("TUES THURS", [1, 3]),
        ("TUES FRI", [1, 4]),
        ("THURS", [3]),
        ("Default", [1, 3]),
        ("MON FRI", [0, 4]),
        ("MON TUES THURS FRI", [0, 1, 3, 4]),
        ("SAT", [5]),
        ("Cromer", None),
        ("", None),
        ("Vine house farm grasmere", None),
    ],
)
def test_parse_day_group(input_: str, expected: list[int] | None) -> None:
    assert parse_day_group(input_) == expected


def test_extract_soft_window_between() -> None:
    assert extract_soft_window("delivery BETWEEN 7AM AND 9AM please") == ("07:00", "09:00")


def test_extract_soft_window_before() -> None:
    assert extract_soft_window("delivery before 1pm") == (None, "13:00")


def test_extract_soft_window_loose_between() -> None:
    assert extract_soft_window("Delivery between 9 and 10 if poss") == ("09:00", "10:00")


def test_extract_soft_window_opening_times() -> None:
    assert extract_soft_window("Opening times: 06:45 - 17:30") == ("06:45", "17:30")


def test_extract_soft_window_no_match() -> None:
    assert extract_soft_window("just leave it round the back") == (None, None)


def test_round_trip_full_row() -> None:
    csv_text = "\n".join([
        HEADER,
        _row({
            "customer_name (do not edit)": "Abbots Ripton Village Stores",
            "legal_entity_name (do not edit)": "Abbots Ripton Village Stores",
            "delivery_address (do not edit)": "Station Road, Abbots Ripton, Huntingdon PE28 2PA",
            "billing_address (do not edit)": "Station Road, Abbots Ripton, Huntingdon PE28 2PA",
            "latest_delivery_date (do not edit)": "01/05/2026",
            "customer_code": "'ABOTTRIP'",
            "active (Yes or No)": "Yes",
            "pricing_level": "Level 1",
            "invoice_notes": "Cheque/COD. Opening times: 06:45 - 17:30",
            "standing_picking_instructions": "TUE: GREEN FRI: GREEN",
            "standing_delivery_instructions": "Cheque/COD. Opening times: 06:45 - 17:30",
            "delivery_run_code": "'GOG'",
            "delivery_run_position": "28",
            "delivery_days_and_cut_off_times_group": "TUES THURS",
            "payment_term_days": "0",
            "sales_rep": "James (Grasmere Farm)",
        }),
    ])
    out = parse_customer_csv(csv_text)
    assert out.errors == []
    assert len(out.rows) == 1
    r = out.rows[0]
    assert r.customer_code == "ABOTTRIP"
    assert r.legacy_run_code == "GOG"
    assert r.legacy_run_position == 28
    assert r.preferred_days == [1, 3]
    assert r.is_cod is True
    assert r.last_delivery_date == date(2026, 5, 1)
    assert r.soft_window_start == "06:45"
    assert r.soft_window_end == "17:30"
    assert r.active is True
    assert r.raw_csv_row["customer_code"] == "'ABOTTRIP'"


def test_freeform_day_group_flagged() -> None:
    csv_text = "\n".join([
        HEADER,
        _row({
            "customer_name (do not edit)": "Cromer Crab Co",
            "customer_code": "'CROMER1'",
            "active (Yes or No)": "Yes",
            "delivery_run_code": "'~NR'",
            "delivery_days_and_cut_off_times_group": "Cromer",
        }),
    ])
    out = parse_customer_csv(csv_text)
    assert out.rows[0].flagged_for_review is True
    assert out.rows[0].preferred_days is None


def test_missing_code_emits_error() -> None:
    csv_text = "\n".join([
        HEADER,
        _row({"customer_name (do not edit)": "X"}),
    ])
    out = parse_customer_csv(csv_text)
    assert out.rows == []
    assert "customer_code" in out.errors[0][1]
