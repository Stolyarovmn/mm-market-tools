#!/usr/bin/env python3
import argparse
import datetime as dt
from collections import defaultdict
from pathlib import Path

from core.io_utils import load_json, write_json


DEFAULT_INPUT_JSON = "/home/user/mm-market-tools/data/normalized/competitor_market_analysis_2026-04-09g.json"
DEFAULT_REPORT_DIR = "/home/user/mm-market-tools/reports"
DEFAULT_DATE = dt.date.today().isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Build a backlog of market groups/windows where cost coverage must be completed first.")
    parser.add_argument("--input-json", default=DEFAULT_INPUT_JSON)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    return parser.parse_args()


def blind_type(row):
    if row.get("my_avg_price") is None or not row.get("my_sku_count"):
        return "no_assortment_reference"
    return "missing_cogs"


def next_step(row):
    if blind_type(row) == "no_assortment_reference":
        return "собрать benchmark SKU и понять, нужен ли вход в группу вообще"
    return "дозаполнить себестоимость по своим SKU этой группы"


def build_backlog(payload):
    groups = payload.get("groups") or []
    windows = payload.get("entry_windows") or []
    group_lookup = {row.get("group"): row for row in groups}

    backlog_rows = []
    grouped = defaultdict(list)
    for row in windows:
        if row.get("market_margin_fit_pct") is not None:
            continue
        group_row = group_lookup.get(row.get("group")) or {}
        enriched = {
            "group": row.get("group"),
            "price_band": row.get("price_band"),
            "entry_window_score": row.get("entry_window_score"),
            "orders_sum": row.get("orders_sum"),
            "seller_count": row.get("seller_count"),
            "my_sku_count": group_row.get("my_sku_count", 0),
            "my_avg_price": row.get("my_avg_price"),
            "blind_spot_type": blind_type({**row, **group_row}),
            "next_step": next_step({**row, **group_row}),
        }
        priority = float(enriched["entry_window_score"] or 0) * 0.65 + min(float(enriched["orders_sum"] or 0) / 150, 35.0)
        if enriched["blind_spot_type"] == "missing_cogs":
            priority += 10
        enriched["priority_score"] = round(priority, 2)
        backlog_rows.append(enriched)
        grouped[enriched["group"]].append(enriched)

    backlog_rows.sort(key=lambda row: (row["priority_score"], row["orders_sum"]), reverse=True)

    group_backlog = []
    for group, rows in grouped.items():
        rows = sorted(rows, key=lambda row: (row["priority_score"], row["orders_sum"]), reverse=True)
        group_backlog.append(
            {
                "group": group,
                "window_count": len(rows),
                "best_priority_score": rows[0]["priority_score"],
                "best_window_score": rows[0]["entry_window_score"],
                "orders_sum": sum(row["orders_sum"] or 0 for row in rows),
                "my_sku_count": rows[0]["my_sku_count"],
                "blind_spot_type": rows[0]["blind_spot_type"],
                "next_step": rows[0]["next_step"],
                "top_windows": rows[:3],
            }
        )
    group_backlog.sort(key=lambda row: (row["best_priority_score"], row["orders_sum"]), reverse=True)

    return {
        "summary": {
            "blind_window_count": len(backlog_rows),
            "blind_group_count": len(group_backlog),
            "missing_cogs_groups": sum(1 for row in group_backlog if row["blind_spot_type"] == "missing_cogs"),
            "no_assortment_reference_groups": sum(1 for row in group_backlog if row["blind_spot_type"] == "no_assortment_reference"),
        },
        "group_backlog": group_backlog,
        "window_backlog": backlog_rows[:20],
    }


def write_markdown(path, report, date_tag):
    lines = [
        f"# Cost Coverage Backlog {date_tag}",
        "",
        f"- blind_window_count: `{report['summary']['blind_window_count']}`",
        f"- blind_group_count: `{report['summary']['blind_group_count']}`",
        f"- missing_cogs_groups: `{report['summary']['missing_cogs_groups']}`",
        f"- no_assortment_reference_groups: `{report['summary']['no_assortment_reference_groups']}`",
        "",
        "## Приоритетные группы на добор экономики",
        "",
    ]
    for row in report["group_backlog"][:12]:
        lines.append(
            f"- {row['group']} | priority `{row['best_priority_score']}` | windows `{row['window_count']}` | orders `{row['orders_sum']}` | my_sku_count `{row['my_sku_count']}` | type `{row['blind_spot_type']}` | next `{row['next_step']}`"
        )
    if not report["group_backlog"]:
        lines.append("- Слепых групп не осталось.")

    lines.extend(["", "## Приоритетные окна", ""])
    for row in report["window_backlog"][:15]:
        lines.append(
            f"- {row['group']} / {row['price_band']} | priority `{row['priority_score']}` | score `{row['entry_window_score']}` | orders `{row['orders_sum']}` | type `{row['blind_spot_type']}` | next `{row['next_step']}`"
        )
    if not report["window_backlog"]:
        lines.append("- Слепых окон не осталось.")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse_args()
    payload = load_json(args.input_json)
    report = build_backlog(payload)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"cost_coverage_backlog_{args.date_tag}.json"
    md_path = report_dir / f"cost_coverage_backlog_{args.date_tag}.md"
    write_json(json_path, report)
    write_markdown(md_path, report, args.date_tag)
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
