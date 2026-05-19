#!/usr/bin/env python3
"""Persistent Quick Wins session state.

Storage: data/local/quick_wins_state.json
State is keyed by session_date and auto-resets when the underlying
quick_wins_<date>.json changes (detected via file mtime).
"""
import datetime as dt
from pathlib import Path

from core.io_utils import load_json, write_json
from core.paths import DASHBOARD_DIR, LOCAL_DATA_DIR, ensure_dir

from core.logging_config import get_logger
log = get_logger('core.quick_wins_state')

QUICK_WINS_STATE_PATH = LOCAL_DATA_DIR / "quick_wins_state.json"


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _backlog_mtime(session_date):
    """Return mtime ISO string of the underlying quick_wins_<date>.json, or None."""
    path = DASHBOARD_DIR / f"quick_wins_{session_date}.json"
    if not path.exists():
        return None
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat()


def _default_state(session_date):
    return {
        "session_date": session_date,
        "done_ids": [],
        "custom_order": [],
        "version": 0,
        "backlog_mtime": _backlog_mtime(session_date),
        "updated_at": _now_iso(),
    }


def _load_raw():
    ensure_dir(QUICK_WINS_STATE_PATH.parent)
    if not QUICK_WINS_STATE_PATH.exists():
        return {}
    try:
        return load_json(QUICK_WINS_STATE_PATH)
    except Exception:
        return {}


def _save_raw(raw):
    ensure_dir(QUICK_WINS_STATE_PATH.parent)
    write_json(QUICK_WINS_STATE_PATH, raw)


def load_state(session_date):
    """Load state for *session_date*, resetting if the backlog file changed."""
    raw = _load_raw()
    state = raw.get(session_date)
    if state is None:
        state = _default_state(session_date)
        raw[session_date] = state
        _save_raw(raw)
        return state
    # Auto-reset if the underlying backlog was rebuilt.
    current_mtime = _backlog_mtime(session_date)
    if current_mtime and state.get("backlog_mtime") != current_mtime:
        state = _default_state(session_date)
        raw[session_date] = state
        _save_raw(raw)
    return state


def _mutate(session_date, fn):
    """Load state, apply fn(state), bump version, save, return state."""
    raw = _load_raw()
    state = raw.get(session_date) or _default_state(session_date)
    fn(state)
    state["version"] = state.get("version", 0) + 1
    state["updated_at"] = _now_iso()
    raw[session_date] = state
    _save_raw(raw)
    return state


def mark_done(session_date, item_id):
    def _apply(state):
        done = state.setdefault("done_ids", [])
        if item_id not in done:
            done.append(item_id)
    return _mutate(session_date, _apply)


def mark_active(session_date, item_id):
    def _apply(state):
        state["done_ids"] = [x for x in state.get("done_ids", []) if x != item_id]
    return _mutate(session_date, _apply)


def set_order(session_date, order):
    def _apply(state):
        state["custom_order"] = list(order)
    return _mutate(session_date, _apply)


def reset_if_stale(session_date):
    """Force reset if backlog has changed; return current state."""
    raw = _load_raw()
    state = raw.get(session_date) or _default_state(session_date)
    current_mtime = _backlog_mtime(session_date)
    if current_mtime and state.get("backlog_mtime") != current_mtime:
        state = _default_state(session_date)
        raw[session_date] = state
        _save_raw(raw)
    return state


def _public(state):
    return {
        "done_ids": state.get("done_ids", []),
        "custom_order": state.get("custom_order", []),
        "version": state.get("version", 0),
    }
