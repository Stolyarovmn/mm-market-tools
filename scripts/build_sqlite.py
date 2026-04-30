#!/usr/bin/env python3
"""Build SQLite database from dashboard JSON data.

Reads data/dashboard/index.json and writes data.db for upload
to GitHub Releases (fetched by GitHub Pages via sql.js).

Usage:
    python scripts/build_sqlite.py
    python scripts/build_sqlite.py --data path/to/index.json --out data.db
"""
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_DATA = ROOT / "data" / "dashboard" / "index.json"
DEFAULT_OUT = ROOT / "data.db"

DDL = """
CREATE TABLE iteration (
    number TEXT, updated_at TEXT, status TEXT, uncertainty REAL
);
CREATE TABLE plan_kpis (
    generated_at TEXT,
    actions_in_plan INTEGER, quick_wins_count INTEGER,
    by_type_count_json TEXT,
    potential_price_shift_rub REAL,
    zero_stock_in_top INTEGER, stockout_risk_in_top INTEGER,
    competitor_aware_in_top INTEGER,
    sources_skipped_json TEXT,
    stock_context_source TEXT, competitor_context_source TEXT,
    stock_annotated INTEGER, competitor_annotated INTEGER,
    rb_generated_at TEXT,
    rb_responses_suggested INTEGER, rb_high_priority_responses INTEGER,
    rb_reason_coverage INTEGER
);
CREATE TABLE plan_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT
);
CREATE TABLE insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT, severity TEXT, message TEXT
);
CREATE TABLE actions (
    rank INTEGER PRIMARY KEY,
    action_type TEXT, title TEXT, group_name TEXT,
    headline TEXT, detail TEXT,
    current_value REAL, suggested_value REAL,
    priority_score REAL, compound_score REAL,
    quick_win INTEGER,
    entity_key TEXT, product_id TEXT,
    meta_json TEXT
);
CREATE TABLE reviews (
    product_id TEXT, sku TEXT, title TEXT,
    return_reason_code TEXT, reason_label TEXT,
    return_count INTEGER, template_response TEXT,
    action_for_seller TEXT, priority TEXT
);
CREATE TABLE applied_actions (
    id TEXT PRIMARY KEY,
    action_id INTEGER, entity_key TEXT, product_id TEXT,
    title TEXT, action_type TEXT,
    applied_at TEXT, measurement_due_at TEXT,
    status TEXT, baseline_json TEXT
);
CREATE TABLE api_status (
    checked_at TEXT, shop_id INTEGER,
    token_status TEXT, token_expires_moscow TEXT,
    cubes INTEGER, existing_documents INTEGER
);
CREATE TABLE api_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT, method TEXT, status TEXT, note TEXT
);
CREATE TABLE api_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, status TEXT, note TEXT
);
CREATE TABLE blockers (
    id TEXT PRIMARY KEY, sev TEXT, title TEXT, body TEXT
);
"""


def build(data_path: Path, out_path: Path) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))

    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(str(out_path))
    conn.executescript(DDL)
    c = conn.cursor()

    plan = data.get("plan", {})
    rb = data.get("review_booster", {})
    aa = data.get("applied_actions", {})
    api = data.get("api_status", {})
    iteration = data.get("iteration", {})

    # iteration
    c.execute("INSERT INTO iteration VALUES (?,?,?,?)",
              (iteration.get("number"), iteration.get("updated_at"),
               iteration.get("status"), iteration.get("uncertainty")))

    # plan_kpis (merged plan + review_booster meta)
    kpis = plan.get("kpis", {})
    meta = plan.get("metadata", {})
    rb_kpis = rb.get("kpis", {})
    c.execute("""INSERT INTO plan_kpis VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        plan.get("generated_at"),
        kpis.get("actions_in_plan"), kpis.get("quick_wins_count"),
        json.dumps(kpis.get("by_type_count", {}), ensure_ascii=False),
        kpis.get("potential_price_shift_rub"),
        kpis.get("zero_stock_in_top"), kpis.get("stockout_risk_in_top"),
        kpis.get("competitor_aware_in_top"),
        json.dumps(meta.get("sources_skipped", []), ensure_ascii=False),
        meta.get("stock_context_source"), meta.get("competitor_context_source"),
        meta.get("stock_annotated"), meta.get("competitor_annotated"),
        rb.get("generated_at"),
        rb_kpis.get("responses_suggested"), rb_kpis.get("high_priority_responses"),
        rb_kpis.get("reason_coverage"),
    ))

    # plan_sources
    for label in meta.get("sources_used", []):
        c.execute("INSERT INTO plan_sources (label) VALUES (?)", (label,))

    # insights
    for ins in plan.get("insights", []):
        c.execute("INSERT INTO insights (source,severity,message) VALUES (?,?,?)",
                  ("plan", ins["severity"], ins["message"]))
    for ins in rb.get("insights", []):
        c.execute("INSERT INTO insights (source,severity,message) VALUES (?,?,?)",
                  ("review_booster", ins["severity"], ins["message"]))

    # actions
    for act in plan.get("actions", []):
        c.execute("""INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            act["rank"], act["action_type"], act["title"], act.get("group"),
            act.get("headline"), act.get("detail"),
            act.get("current_value"), act.get("suggested_value"),
            act.get("priority_score"), act.get("compound_score"),
            1 if act.get("quick_win") else 0,
            act.get("entity_key"), str(act.get("product_id", "")),
            json.dumps(act.get("meta", {}), ensure_ascii=False),
        ))

    # reviews
    for row in rb.get("rows", []):
        c.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)", (
            row.get("product_id"), row.get("sku"), row.get("title"),
            row.get("return_reason_code"), row.get("reason_label"),
            row.get("return_count"), row.get("template_response"),
            row.get("action_for_seller"), row.get("priority"),
        ))

    # applied_actions
    for entry in aa.get("entries", []):
        c.execute("INSERT INTO applied_actions VALUES (?,?,?,?,?,?,?,?,?,?)", (
            entry["id"], entry.get("action_id"), entry.get("entity_key"),
            str(entry.get("product_id", "")), entry.get("title"),
            entry.get("action_type"), entry.get("applied_at"),
            entry.get("measurement_due_at"), entry.get("status"),
            json.dumps(entry.get("baseline", {}), ensure_ascii=False),
        ))

    # api_status
    c.execute("INSERT INTO api_status VALUES (?,?,?,?,?,?)", (
        api.get("checked_at"), api.get("shop_id"),
        api.get("token_status"), api.get("token_expires_moscow"),
        api.get("cubes"), api.get("existing_documents"),
    ))

    for ep in api.get("endpoints", []):
        c.execute("INSERT INTO api_endpoints (url,method,status,note) VALUES (?,?,?,?)",
                  (ep["url"], ep["method"], ep["status"], ep.get("note")))

    for gap in api.get("gaps", []):
        c.execute("INSERT INTO api_gaps (name,status,note) VALUES (?,?,?)",
                  (gap["name"], gap["status"], gap.get("note")))

    # blockers
    for b in data.get("blockers", []):
        c.execute("INSERT INTO blockers VALUES (?,?,?,?)",
                  (b["id"], b["sev"], b["title"], b["body"]))

    conn.commit()
    conn.close()

    size_kb = out_path.stat().st_size // 1024
    tables = [r[0] for r in sqlite3.connect(str(out_path)).execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"data.db built: {size_kb}KB, tables: {', '.join(tables)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    build(Path(args.data), Path(args.out))


if __name__ == "__main__":
    main()
