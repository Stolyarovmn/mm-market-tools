#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path

from core.io_utils import load_json, write_json
from core.market_analysis import classify_group
from core.market_economics import load_cogs_override_rows
from core.paths import COGS_OVERRIDES_PATH


DEFAULT_OFFICIAL_JSON = "/home/user/mm-market-tools/reports/official_period_analysis_2026-04-08.json"
DEFAULT_BACKLOG_JSON = "/home/user/mm-market-tools/reports/cost_coverage_backlog_2026-04-09a.json"
DEFAULT_REPORT_DIR = "/home/user/mm-market-tools/reports"
DEFAULT_DATE = dt.date.today().isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Build a registry of your SKUs with zero or missing COGS in priority blind-spot groups.")
    parser.add_argument("--official-json", default=DEFAULT_OFFICIAL_JSON)
    parser.add_argument("--backlog-json", default=DEFAULT_BACKLOG_JSON)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--cogs-overrides-json", default=str(COGS_OVERRIDES_PATH))
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    return parser.parse_args()


def _identity_key(row):
    return (
        str(row.get("sku") or "").strip(),
        str(row.get("seller_sku_id") or "").strip(),
        str(row.get("product_id") or "").strip(),
        str(row.get("title") or "").strip().lower(),
    )


def build_registry(official_payload, backlog_payload, override_rows):
    target_groups = {row["group"] for row in backlog_payload.get("group_backlog", [])}
    grouped = defaultdict(list)
    overridden_keys = {
        _identity_key(row)
        for row in override_rows
        if float(row.get("cogs") or 0.0) > 0
    }

    seen_keys = set()
    for row in official_payload.get("rows", []):
        group = classify_group(row.get("title") or "")
        if group not in target_groups:
            continue
        key = _identity_key(row)
        if key in overridden_keys:
            continue
        if key in seen_keys:
            continue
        cogs = float(row.get("cogs") or 0.0)
        if cogs > 0:
            continue
        seen_keys.add(key)
        grouped[group].append(
            {
                "group": group,
                "title": row.get("title"),
                "sku": row.get("sku"),
                "seller_sku_id": row.get("seller_sku_id"),
                "product_id": row.get("product_id"),
                "sale_price": row.get("sale_price"),
                "units_sold": row.get("units_sold"),
                "stock_value_sale": row.get("stock_value_sale"),
                "total_stock": row.get("total_stock"),
                "status": row.get("status"),
                "barcode": row.get("barcode") or row.get("sku_barcode") or "",
                "competitor_prices": row.get("competitor_prices") or "",
                "competitor_count": row.get("competitor_count") or 0,
            }
        )

    summary_rows = []
    for backlog_group in backlog_payload.get("group_backlog", []):
        group = backlog_group["group"]
        rows = grouped.get(group, [])
        summary_rows.append(
            {
                "group": group,
                "priority_score": backlog_group.get("best_priority_score"),
                "window_count": backlog_group.get("window_count"),
                "orders_sum": backlog_group.get("orders_sum"),
                "zero_cogs_sku_count": len(rows),
                "sold_zero_cogs_sku_count": sum(1 for row in rows if float(row.get("units_sold") or 0) > 0),
                "stock_zero_cogs_sku_count": sum(1 for row in rows if float(row.get("total_stock") or 0) > 0),
                "top_examples": sorted(rows, key=lambda row: (float(row.get("units_sold") or 0), float(row.get("stock_value_sale") or 0)), reverse=True)[:5],
            }
        )

    summary_rows.sort(key=lambda row: (row["priority_score"] or 0, row["zero_cogs_sku_count"]), reverse=True)
    flat_rows = []
    for row in summary_rows:
        for item in grouped.get(row["group"], []):
            flat_rows.append({**item, "priority_score": row["priority_score"]})
    flat_rows.sort(key=lambda row: (row["priority_score"] or 0, float(row.get("units_sold") or 0), float(row.get("stock_value_sale") or 0)), reverse=True)

    return {
        "summary": {
            "target_group_count": len(target_groups),
            "zero_cogs_group_count": sum(1 for row in summary_rows if row["zero_cogs_sku_count"] > 0),
            "zero_cogs_sku_total": len(flat_rows),
            "sold_zero_cogs_sku_total": sum(1 for row in flat_rows if float(row.get("units_sold") or 0) > 0),
        },
        "groups": summary_rows,
        "items": flat_rows[:200],
    }


def write_markdown(path, report, date_tag):
    lines = [
        f"# Zero COGS Registry {date_tag}",
        "",
        f"- target_group_count: `{report['summary']['target_group_count']}`",
        f"- zero_cogs_group_count: `{report['summary']['zero_cogs_group_count']}`",
        f"- zero_cogs_sku_total: `{report['summary']['zero_cogs_sku_total']}`",
        f"- sold_zero_cogs_sku_total: `{report['summary']['sold_zero_cogs_sku_total']}`",
        "",
        "## Группы, где сначала надо заполнить себестоимость",
        "",
    ]
    for row in report["groups"][:12]:
        lines.append(
            f"- {row['group']} | priority `{row['priority_score']}` | zero_cogs_sku_count `{row['zero_cogs_sku_count']}` | sold_zero_cogs_sku_count `{row['sold_zero_cogs_sku_count']}` | stock_zero_cogs_sku_count `{row['stock_zero_cogs_sku_count']}`"
        )
        for item in row["top_examples"][:3]:
            lines.append(
                f"  example: {item['title']} | sku `{item['sku']}` | sold `{item['units_sold']}` | stock `{item['total_stock']}` | sale `{item['sale_price']}`"
            )
    if not report["groups"]:
        lines.append("- Групп с нулевой себестоимостью не найдено.")

    lines.extend(["", "## Приоритетные SKU с нулевой себестоимостью", ""])
    for item in report["items"][:20]:
        lines.append(
            f"- {item['group']} | {item['title']} | sku `{item['sku']}` | sold `{item['units_sold']}` | stock `{item['total_stock']}` | sale `{item['sale_price']}`"
        )
    if not report["items"]:
        lines.append("- SKU с нулевой себестоимостью не найдено.")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(path, report):
    """Write CSV export with TASK-004 columns first, then ingest contract columns."""
    items = report.get("items", [])
    
    # CSV columns: TASK-004 required columns first, then ingest contract columns
    fieldnames = [
        # TASK-004 required columns
        "group",
        "product_id",
        "sku",
        "barcode",
        "current_price",
        "competitor_prices",
        "market_count",
        "orders_sum",
        "notes",
        # Ingest contract columns (for roundtrip)
        "title",
        "seller_sku_id",
        "sale_price",
        "total_stock",
        "units_sold_window",
        "priority_score",
        "fill_cogs",
        "fill_source",
        "fill_comment",
    ]
    
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in items:
            # Calculate orders_sum as units_sold * sale_price, or fallback to 0
            units_sold = float(item.get("units_sold") or 0)
            sale_price = float(item.get("sale_price") or 0)
            orders_sum = units_sold * sale_price if units_sold > 0 else 0
            
            # Get market_count from competitor_count field
            market_count = int(item.get("competitor_count") or 0)
            
            row = {
                # TASK-004 required columns
                "group": item.get("group") or "",
                "product_id": item.get("product_id") or "",
                "sku": item.get("sku") or "",
                "barcode": item.get("barcode") or "",
                "current_price": sale_price or "",
                "competitor_prices": item.get("competitor_prices") or "",
                "market_count": market_count,
                "orders_sum": orders_sum,
                "notes": "",
                # Ingest contract columns (leave fill_* empty for manual input)
                "title": item.get("title") or "",
                "seller_sku_id": item.get("seller_sku_id") or "",
                "sale_price": sale_price or "",
                "total_stock": item.get("total_stock") or "",
                "units_sold_window": units_sold,
                "priority_score": item.get("priority_score") or "",
                "fill_cogs": "",
                "fill_source": "",
                "fill_comment": "",
            }
            writer.writerow(row)


def main():
    args = parse_args()
    official_payload = load_json(args.official_json)
    backlog_payload = load_json(args.backlog_json)
    report = build_registry(official_payload, backlog_payload, load_cogs_override_rows(args.cogs_overrides_json))
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"zero_cogs_registry_{args.date_tag}.json"
    md_path = report_dir / f"zero_cogs_registry_{args.date_tag}.md"
    csv_path = report_dir / f"zero_cogs_registry_{args.date_tag}.csv"
    write_json(json_path, report)
    write_markdown(md_path, report, args.date_tag)
    write_csv(csv_path, report)
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
