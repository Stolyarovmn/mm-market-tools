#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
from pathlib import Path

from core.io_utils import load_json


DEFAULT_REGISTRY_JSON = "/home/user/mm-market-tools/reports/zero_cogs_registry_2026-04-09a.json"
DEFAULT_REPORT_DIR = "/home/user/mm-market-tools/reports"
DEFAULT_DATE = dt.date.today().isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Export a fill template CSV for zero-COGS SKUs.")
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    return parser.parse_args()


def main():
    args = parse_args()
    payload = load_json(args.registry_json)
    rows = []
    for item in payload.get("items", []):
        rows.append(
            {
                "group": item.get("group"),
                "title": item.get("title"),
                "sku": item.get("sku"),
                "seller_sku_id": item.get("seller_sku_id"),
                "product_id": item.get("product_id"),
                "sale_price": item.get("sale_price"),
                "total_stock": item.get("total_stock"),
                "units_sold_window": item.get("units_sold"),
                "priority_score": item.get("priority_score"),
                "fill_cogs": "",
                "fill_source": "",
                "fill_comment": "",
            }
        )

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_path = report_dir / f"cogs_fill_template_{args.date_tag}.csv"
    fieldnames = [
        "group",
        "title",
        "sku",
        "seller_sku_id",
        "product_id",
        "sale_price",
        "total_stock",
        "units_sold_window",
        "priority_score",
        "fill_cogs",
        "fill_source",
        "fill_comment",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
