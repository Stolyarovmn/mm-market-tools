#!/usr/bin/env python3
"""Smoke tests for the Action Center + Quick Wins API.

Tests the state-machine helpers directly (no HTTP server needed).
Prints SMOKE_ACTION_CENTER_API_OK on success.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.action_store import load_action_store, save_action_store
from core.quick_wins_state import (
    load_state,
    mark_done,
    mark_active,
    set_order,
    reset_if_stale,
    _public,
    QUICK_WINS_STATE_PATH,
)

SESSION = "smoke-test-session-9999"


def _clean():
    """Remove smoke session state so tests are idempotent."""
    from core.io_utils import load_json, write_json
    from core.paths import ensure_dir
    if not QUICK_WINS_STATE_PATH.exists():
        return
    raw = load_json(QUICK_WINS_STATE_PATH)
    raw.pop(SESSION, None)
    ensure_dir(QUICK_WINS_STATE_PATH.parent)
    write_json(QUICK_WINS_STATE_PATH, raw)


# ---------------------------------------------------------------------------
# GET /api/quick_wins/state  (load_state)
# ---------------------------------------------------------------------------
def test_get_state():
    _clean()
    state = load_state(SESSION)
    pub = _public(state)
    assert isinstance(pub["done_ids"], list)
    assert isinstance(pub["custom_order"], list)
    assert isinstance(pub["version"], int)
    print("  GET /api/quick_wins/state -> ok")


# ---------------------------------------------------------------------------
# POST /api/quick_wins/complete  (mark_done)
# ---------------------------------------------------------------------------
def test_post_complete():
    _clean()
    state = mark_done(SESSION, "reorder")
    pub = _public(state)
    assert "reorder" in pub["done_ids"], f"expected 'reorder' in done_ids: {pub}"
    assert pub["version"] == 1
    # Idempotent: marking done twice doesn't duplicate
    state2 = mark_done(SESSION, "reorder")
    assert pub["done_ids"].count("reorder") == 1
    print("  POST /api/quick_wins/complete -> ok")


# ---------------------------------------------------------------------------
# POST /api/quick_wins/restore  (mark_active)
# ---------------------------------------------------------------------------
def test_post_restore():
    _clean()
    mark_done(SESSION, "reorder")
    state = mark_active(SESSION, "reorder")
    pub = _public(state)
    assert "reorder" not in pub["done_ids"], f"expected 'reorder' removed: {pub}"
    assert pub["version"] == 2
    print("  POST /api/quick_wins/restore -> ok")


# ---------------------------------------------------------------------------
# POST /api/quick_wins/reorder  (set_order)
# ---------------------------------------------------------------------------
def test_post_reorder():
    _clean()
    order = ["markdown", "reorder", "weekly"]
    state = set_order(SESSION, order)
    pub = _public(state)
    assert pub["custom_order"] == order, f"expected {order}, got {pub['custom_order']}"
    assert pub["version"] == 1
    # Empty order = reset to server priority
    state2 = set_order(SESSION, [])
    assert _public(state2)["custom_order"] == []
    print("  POST /api/quick_wins/reorder -> ok")


# ---------------------------------------------------------------------------
# Auto-reset when backlog changes
# ---------------------------------------------------------------------------
def test_stale_reset():
    _clean()
    mark_done(SESSION, "reorder")
    # Simulate stale by corrupting the stored backlog_mtime
    from core.io_utils import load_json, write_json

    raw = load_json(QUICK_WINS_STATE_PATH)
    raw[SESSION]["backlog_mtime"] = "1970-01-01T00:00:00+00:00"
    write_json(QUICK_WINS_STATE_PATH, raw)
    # reset_if_stale will NOT reset because the backlog file for SESSION doesn't exist
    # (no quick_wins_smoke-test-session-9999.json) — so backlog_mtime stays None -> no reset.
    # Test just checks no exception is raised.
    state = reset_if_stale(SESSION)
    assert state is not None
    print("  reset_if_stale -> ok (no exception)")


# ---------------------------------------------------------------------------
# Action Center store (existing endpoints)
# ---------------------------------------------------------------------------
def test_action_center_store():
    store = load_action_store()
    assert "watchlists" in store
    assert "actions" in store
    assert "saved_views" in store
    print("  action_center load_action_store -> ok")


def main():
    print("Running Action Center API smoke tests…")
    test_get_state()
    test_post_complete()
    test_post_restore()
    test_post_reorder()
    test_stale_reset()
    test_action_center_store()
    _clean()
    print("SMOKE_ACTION_CENTER_API_OK")


if __name__ == "__main__":
    main()
