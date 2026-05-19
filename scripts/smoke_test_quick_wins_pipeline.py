#!/usr/bin/env python3
import sys as _s; from pathlib import Path as _P
_r=_P(__file__).resolve().parent.parent
if str(_r) not in _s.path: _s.path.insert(0,str(_r))

"""Smoke test for the Quick Wins pipeline.

Runs build_quick_wins with fixture data and verifies the output shape.
Prints SMOKE_QUICK_WINS_OK on success.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_quick_wins import build_quick_wins, LABELS, ROUTES, ACTIONS

EXPECTED_KINDS = {"reorder", "markdown", "reviews", "questions", "run_job", "title_seo", "price_trap", "watchlist"}
REQUIRED_ITEM_KEYS = {"id", "kind", "count", "label", "action", "route", "priority"}


def test_output_shape():
    payload = build_quick_wins(session_date="2026-01-01")
    assert payload["schema_version"] == "v1", "schema_version must be 'v1'"
    assert payload["session_date"] == "2026-01-01"
    items = payload.get("items")
    assert isinstance(items, list), "items must be a list"
    # All items must have required keys.
    for item in items:
        missing = REQUIRED_ITEM_KEYS - set(item)
        assert not missing, f"item missing keys: {missing}  item={item}"
        assert item["count"] > 0, "items with count==0 must be dropped"
    # Priorities must be unique and sequential from 1.
    priorities = [i["priority"] for i in items]
    assert priorities == list(range(1, len(items) + 1)), f"priorities must be sequential: {priorities}"
    print(f"  output has {len(items)} items: {[i['id'] for i in items]}")


def test_all_kinds_reachable():
    for kind in EXPECTED_KINDS:
        assert kind in LABELS, f"LABELS missing kind: {kind}"
        assert kind in ROUTES, f"ROUTES missing kind: {kind}"
        assert kind in ACTIONS, f"ACTIONS missing kind: {kind}"
    print(f"  all {len(EXPECTED_KINDS)} kinds have labels/routes/actions")


def test_idempotent(tmp_path):
    from core.io_utils import write_json
    from core.paths import DASHBOARD_DIR

from core.logging_config import get_logger
log = get_logger('scripts.smoke_test_quick_wins_pipeline')
    payload = build_quick_wins(session_date="2026-01-01")
    out = DASHBOARD_DIR / "quick_wins_2026-01-01.json"
    write_json(out, payload)
    payload2 = build_quick_wins(session_date="2026-01-01")
    assert payload["schema_version"] == payload2["schema_version"]
    # Items should be the same structure (counts may differ if data changed, but not in smoke).
    print("  re-run is idempotent (same schema)")


def main():
    print("Running Quick Wins pipeline smoke tests…")
    test_output_shape()
    test_all_kinds_reachable()
    test_idempotent(None)
    print("SMOKE_QUICK_WINS_OK")


if __name__ == "__main__":
    main()
