from __future__ import annotations

import io
from datetime import date

import pandas as pd

from grasmere_routes.orders_import import parse_orders_excel


SAMPLE_ROWS = [
    {
        "Delivery Run Code": "BR0",
        "Delivery Date": pd.Timestamp("2026-04-30"),
        "Customer Name": "Baytree Nurseries Ltd",
        "Customer Code": "BAYTREE",
        "Number of Boxes": None,
        "Order Number": 53046121,
        "Order Value": 335.28,
        "Order Currency": "GBP",
        "Delivery Address": "High Road, Weston, Spalding, Lincolnshire PE12 6JU",
        "Delivery Instructions": None,
        "Additional Notes": None,
    },
    {
        "Delivery Run Code": "GB0",
        "Delivery Date": pd.Timestamp("2026-04-30"),
        "Customer Name": "Titchmarsh Village Shop",
        "Customer Code": "2TITCHMA",
        "Number of Boxes": None,
        "Order Number": 53049423,
        "Order Value": 111.41,
        "Order Currency": "GBP",
        "Delivery Address": "1 The Green, Titchmarsh, Kettering NN14 3DE",
        "Delivery Instructions": None,
        "Additional Notes": None,
    },
    {
        # Row deliberately missing customer_code → parser must emit error
        "Delivery Run Code": "WP0",
        "Delivery Date": pd.Timestamp("2026-04-30"),
        "Customer Name": "Junk Row",
        "Customer Code": None,
        "Number of Boxes": 2,
        "Order Number": 99999,
        "Order Value": 50.00,
        "Order Currency": "GBP",
        "Delivery Address": "Nowhere",
        "Delivery Instructions": None,
        "Additional Notes": None,
    },
]


def _make_xlsx(rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    return buf.getvalue()


def test_parse_orders_excel_happy_path():
    payload = _make_xlsx(SAMPLE_ROWS[:2])
    rows, errors = parse_orders_excel(payload)
    assert errors == []
    assert len(rows) == 2
    a, b = rows
    assert a.customer_code == "BAYTREE"
    assert a.delivery_date == date(2026, 4, 30)
    assert a.order_value_pence == 33528  # £335.28 → pence
    assert a.delivery_run_code == "BR0"
    assert a.order_number == "53046121"
    assert b.customer_code == "2TITCHMA"
    assert b.order_value_pence == 11141


def test_parse_orders_excel_emits_error_for_missing_code():
    payload = _make_xlsx(SAMPLE_ROWS)
    rows, errors = parse_orders_excel(payload)
    assert len(rows) == 2
    assert any("missing customer_code" in e["error"] for e in errors)


def test_parse_orders_excel_zero_rows():
    payload = _make_xlsx([])
    rows, errors = parse_orders_excel(payload)
    assert rows == []
    assert errors == []
