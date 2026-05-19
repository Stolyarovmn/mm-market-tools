#!/usr/bin/env python3
"""Build state.db from local user state files.

Reads:
  data/local/applied_index.json  -> table: applied_actions
  data/local/quick_wins_state.json -> table: quick_wins_state

Writes: state.db (same dir as data.db, i.e. repo root)
"""
import json
import sqlite3
from pathlib import Path

from core.logging_config import get_logger
log = get_logger('scripts.build_state_db')

ROOT = Path(__file__).resolve().parent.parent

DDL_APPLIED = """
CREATE TABLE IF NOT EXISTS applied_actions (
    id TEXT PRIMARY KEY,
    entity_key TEXT,
    product_id TEXT,
    title TEXT,
    action_type TEXT,
    applied_at TEXT,
    measurement_due_at TEXT,
    status TEXT DEFAULT 'pending'
);
"""

DDL_QUICKWINS = """
CREATE TABLE IF NOT EXISTS quick_wins_state (
    session_date TEXT PRIMARY KEY,
    done_ids_json TEXT,
    custom_order_json TEXT,
    version INTEGER,
    updated_at TEXT
);
"""


def make_applied_id(rec):
    if rec.get("id"):
        return str(rec["id"])
    entity_key = str(rec.get("entity_key") or rec.get("product_id") or "")
    applied_at = str(rec.get("applied_at") or rec.get("timestamp") or "")
    return f"{entity_key}_{applied_at[:10]}"


def load_applied(conn):
    applied_path = ROOT / "data/local/applied_index.json"
    if not applied_path.exists():
        print("  applied_index.json not found, creating empty table")
        return 0
    try:
        records = json.loads(applied_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  WARN: cannot parse applied_index.json: {e}")
        return 0
    if not isinstance(records, list):
        records = [records]
    count = 0
    for rec in records:
        row_id = make_applied_id(rec)
        conn.execute(
            """INSERT OR REPLACE INTO applied_actions
               (id, entity_key, product_id, title, action_type, applied_at, measurement_due_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row_id,
                rec.get("entity_key") or rec.get("product_id") or "",
                str(rec.get("product_id") or ""),
                str(rec.get("title") or ""),
                str(rec.get("action_type") or ""),
                str(rec.get("applied_at") or rec.get("timestamp") or ""),
                str(rec.get("measurement_due_at") or ""),
                str(rec.get("status") or "pending"),
            ),
        )
        count += 1
    return count


def load_quick_wins(conn):
    qw_path = ROOT / "data/local/quick_wins_state.json"
    if not qw_path.exists():
        print("  quick_wins_state.json not found, creating empty table")
        return 0
    try:
        data = json.loads(qw_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  WARN: cannot parse quick_wins_state.json: {e}")
        return 0

    # Normalize: can be dict (single) or list of dicts
    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = data
    else:
        records = []

    count = 0
    for rec in records:
        session_date = str(rec.get("session_date") or "")
        if not session_date:
            continue
        conn.execute(
            """INSERT OR REPLACE INTO quick_wins_state
               (session_date, done_ids_json, custom_order_json, version, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                session_date,
                json.dumps(rec.get("done_ids") or []),
                json.dumps(rec.get("custom_order") or []),
                int(rec.get("version") or 0),
                str(rec.get("updated_at") or ""),
            ),
        )
        count += 1
    return count


def main():
    db_path = ROOT / "state.db"
    # Ensure data/local exists
    (ROOT / "data/local").mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(DDL_APPLIED)
        conn.execute(DDL_QUICKWINS)
        n_applied = load_applied(conn)
        n_qw = load_quick_wins(conn)
        conn.commit()
    finally:
        conn.close()

    print(f"state.db built: applied_actions={n_applied}, quick_wins_state={n_qw}")


if __name__ == "__main__":
    main()
