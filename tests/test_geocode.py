from __future__ import annotations

from grasmere_routes.geocode import classify_confidence


def test_rooftop_high_relevance_address() -> None:
    assert classify_confidence({"relevance": 0.95, "place_type": ["address"]}) == "rooftop"


def test_rooftop_exact_match() -> None:
    assert (
        classify_confidence(
            {
                "relevance": 0.92,
                "place_type": ["place"],
                "properties": {"match_code": {"exact_match": True}},
            }
        )
        == "rooftop"
    )


def test_street_mid_relevance() -> None:
    assert classify_confidence({"relevance": 0.8, "place_type": ["address"]}) == "street"


def test_postcode_low_relevance() -> None:
    assert classify_confidence({"relevance": 0.55, "place_type": ["postcode"]}) == "postcode"


def test_failed_low_relevance_unhelpful_type() -> None:
    assert classify_confidence({"relevance": 0.2, "place_type": ["region"]}) == "failed"
