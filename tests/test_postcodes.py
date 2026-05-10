from __future__ import annotations

import pytest

from grasmere_routes.postcodes import extract_postcode


@pytest.mark.parametrize(
    "address,expected",
    [
        ("High Road, Weston, Spalding, Lincolnshire PE12 6JU", "PE12 6JU"),
        ("47 Western Avenue, Market Harborough, LE16 9PL", "LE16 9PL"),
        ("Station Road, Abbots Ripton, Huntingdon PE28 2PA", "PE28 2PA"),
        # postcode without space
        ("Some Address NN143DE", "NN14 3DE"),
        # already canonical
        ("Just NG10 4QP somewhere", "NG10 4QP"),
        # no postcode → None
        ("Just a name with no UK postcode", None),
        # empty / None
        ("", None),
        (None, None),
    ],
)
def test_extract_postcode(address, expected):
    assert extract_postcode(address) == expected
