#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import os
import urllib.parse
from pathlib import Path

from core.cubejs_api import flatten_results, run_cubejs_query
from core.paths import REPORTS_DIR


DEFAULT_BASE_URL = "https://seller-analytics.mm.ru/cubejs-api/v1/load"
DEFAULT_REPORT_DIR = str(REPORTS_DIR)


def parse_date_range(value):
    raw = (value or "").strip()
    if raw.startswith("[") or raw.startswith("{"):
        return json.loads(raw)
    return value


def build_query(args):
    measures = args.measures
    time_dimension = {
        "dimension": args.time_dimension,
        "dateRange": parse_date_range(args.date_range),
    }
    if args.granularity:
        time_dimension["granularity"] = args.granularity
    query = {
        "measures": measures,
        "timezone": args.timezone,
        "timeDimensions": [time_dimension],
        "filters": [
            {
                "member": args.shop_filter_member,
                "operator": "equals",
                "values": [str(args.shop_id)],
            }
        ],
    }
    if args.dimensions:
        query["dimensions"] = args.dimensions
    return query


def write_csv(rows, path):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a CubeJS analytics query against seller-analytics.mm.ru."
    )
    parser.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    parser.add_argument("--cookie", default=os.getenv("MM_ANALYTICS_COOKIE"))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--report-prefix", default=f"cubejs_query_{dt.date.today().isoformat()}")
    parser.add_argument("--query-json")
    parser.add_argument("--query-file")
    parser.add_argument("--shop-id", type=int, default=int(os.getenv("MM_MY_SHOP_ID", "98")))
    parser.add_argument("--shop-filter-member", default="Sales.shop_id")
    parser.add_argument("--measures", nargs="*", default=["Sales.seller_revenue_without_delivery_measure"])
    parser.add_argument("--dimensions", nargs="*", default=[])
    parser.add_argument("--time-dimension", default="Sales.created_at")
    parser.add_argument("--date-range", default="this day")
    parser.add_argument("--granularity")
    parser.add_argument("--timezone", default="Europe/Moscow")
    return parser.parse_args()


def main():
    args = parse_args()
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    if args.query_json:
        query = json.loads(args.query_json)
    elif args.query_file:
        query = json.loads(Path(args.query_file).read_text(encoding="utf-8"))
    else:
        query = build_query(args)

    params = {"query": json.dumps(query, ensure_ascii=False), "queryType": "multi"}
    payload = run_cubejs_query(query, token=args.token, cookie=args.cookie, base_url=args.base_url)
    rows = flatten_results(payload)

    json_path = report_dir / f"{args.report_prefix}.json"
    csv_path = report_dir / f"{args.report_prefix}.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(rows, csv_path)
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")
    print("Request URL:")
    print(f"{args.base_url}?{urllib.parse.urlencode(params)}")


if __name__ == "__main__":
    main()
