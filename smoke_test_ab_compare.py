#!/usr/bin/env python3
import math

from ab_compare import build_comparison_payload


def smoke_test():
    payload = build_comparison_payload(
        variant_a={
            "label": "A",
            "product_id": 101,
            "date_range": ["2026-04-01", "2026-04-07"],
            "metrics": {
                "revenue": 1200.0,
                "orders": 12.0,
                "sold_qty": 15.0,
            },
        },
        variant_b={
            "label": "B",
            "product_id": 202,
            "date_range": ["2026-04-08", "2026-04-14"],
            "metrics": {
                "revenue": 900.0,
                "orders": 9.0,
                "sold_qty": 10.0,
            },
        },
    )

    assert payload["variants"]["A"]["product_id"] == 101
    assert payload["variants"]["B"]["product_id"] == 202
    assert math.isclose(payload["variants"]["A"]["metrics"]["avg_price"], 80.0)
    assert math.isclose(payload["variants"]["B"]["metrics"]["avg_price"], 90.0)

    deltas = payload["comparison"]["delta"]
    assert math.isclose(deltas["revenue"]["absolute"], 300.0)
    assert math.isclose(deltas["orders"]["absolute"], 3.0)
    assert math.isclose(deltas["sold_qty"]["absolute"], 5.0)
    assert math.isclose(deltas["avg_price"]["absolute"], -10.0)

    assert math.isclose(deltas["revenue"]["pct"], 33.33, rel_tol=0, abs_tol=0.01)
    assert math.isclose(deltas["orders"]["pct"], 33.33, rel_tol=0, abs_tol=0.01)
    assert math.isclose(deltas["sold_qty"]["pct"], 50.0, rel_tol=0, abs_tol=0.01)
    assert math.isclose(deltas["avg_price"]["pct"], -11.11, rel_tol=0, abs_tol=0.01)

    print("SMOKE_AB_COMPARE_OK")


if __name__ == "__main__":
    smoke_test()
