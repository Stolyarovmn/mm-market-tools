#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path

from core.cubejs_api import flatten_results, run_cubejs_query
from core.io_utils import write_json
from core.paths import REPORTS_DIR, ensure_dir


DEFAULT_BASE_URL = "https://seller-analytics.mm.ru/cubejs-api/v1/load"
DEFAULT_MEASURES = [
    "Sales.seller_revenue_without_delivery_measure",
    "Sales.orders_number",
    "Sales.item_sold_number",
]


def parse_date_range(value):
    raw = (value or "").strip()
    if raw.startswith("[") or raw.startswith("{"):
        return json.loads(raw)
    return value


def metric_value(row, key):
    value = row.get(key)
    if value in (None, ""):
        return 0.0
    return float(value)


def avg_price(revenue, sold_qty):
    if not sold_qty:
        return 0.0
    return round(revenue / sold_qty, 2)


def normalize_metrics(metrics):
    revenue = float(metrics.get("revenue") or 0.0)
    orders = float(metrics.get("orders") or 0.0)
    sold_qty = float(metrics.get("sold_qty") or 0.0)
    return {
        "revenue": revenue,
        "orders": orders,
        "sold_qty": sold_qty,
        "avg_price": float(metrics.get("avg_price") or avg_price(revenue, sold_qty)),
    }


def pct_delta(current, reference):
    if not reference:
        return None
    return round((current - reference) / reference * 100.0, 2)


def build_variant_query(args, product_id, date_range):
    return {
        "measures": list(DEFAULT_MEASURES),
        "timezone": args.timezone,
        "timeDimensions": [
            {
                "dimension": args.time_dimension,
                "dateRange": parse_date_range(date_range),
            }
        ],
        "filters": [
            {
                "member": args.shop_filter_member,
                "operator": "equals",
                "values": [str(args.shop_id)],
            },
            {
                "member": args.product_filter_member,
                "operator": "equals",
                "values": [str(product_id)],
            },
        ],
    }


def extract_metrics(payload):
    rows = flatten_results(payload)
    row = rows[0] if rows else {}
    revenue = metric_value(row, "Sales.seller_revenue_without_delivery_measure")
    orders = metric_value(row, "Sales.orders_number")
    sold_qty = metric_value(row, "Sales.item_sold_number")
    return {
        "revenue": revenue,
        "orders": orders,
        "sold_qty": sold_qty,
        "avg_price": avg_price(revenue, sold_qty),
    }


def build_comparison_payload(variant_a, variant_b):
    variant_a = {**variant_a, "metrics": normalize_metrics(variant_a["metrics"])}
    variant_b = {**variant_b, "metrics": normalize_metrics(variant_b["metrics"])}
    delta = {}
    for key in ["revenue", "orders", "sold_qty", "avg_price"]:
        current = float(variant_a["metrics"].get(key) or 0.0)
        reference = float(variant_b["metrics"].get(key) or 0.0)
        delta[key] = {
            "absolute": round(current - reference, 2),
            "pct": pct_delta(current, reference),
        }

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "variants": {
            "A": variant_a,
            "B": variant_b,
        },
        "comparison": {
            "delta": delta,
            "baseline": "B",
            "current": "A",
        },
    }


def build_markdown(payload):
    lines = [
        "# A/B CubeJS Compare",
        "",
        "| Variant | product_id | date_range | revenue | orders | sold_qty | avg_price |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for label in ["A", "B"]:
        variant = payload["variants"][label]
        metrics = variant["metrics"]
        date_range = variant["date_range"]
        lines.append(
            f"| {label} | {variant['product_id']} | {date_range} | "
            f"{metrics['revenue']:.2f} | {metrics['orders']:.2f} | {metrics['sold_qty']:.2f} | {metrics['avg_price']:.2f} |"
        )

    lines.extend(["", "## Delta (A - B)", ""])
    for key, row in payload["comparison"]["delta"].items():
        lines.append(
            f"- {key}: `{row['absolute']:.2f}`"
            + (f" (`{row['pct']:.2f}%`)" if row["pct"] is not None else " (`n/a`)"))
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Compare two CubeJS product/date windows (A vs B).")
    parser.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    parser.add_argument("--cookie", default=os.getenv("MM_ANALYTICS_COOKIE"))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--report-prefix", default=f"ab_compare_{dt.date.today().isoformat()}")
    parser.add_argument("--shop-id", type=int, default=int(os.getenv("MM_MY_SHOP_ID", "98")))
    parser.add_argument("--shop-filter-member", default="Sales.shop_id")
    parser.add_argument("--product-filter-member", default="Sales.product_id")
    parser.add_argument("--time-dimension", default="Sales.created_at")
    parser.add_argument("--timezone", default="Europe/Moscow")
    parser.add_argument("--a-product-id", required=True, type=int)
    parser.add_argument("--a-date-range", required=True)
    parser.add_argument("--a-label", default="A")
    parser.add_argument("--b-product-id", required=True, type=int)
    parser.add_argument("--b-date-range", required=True)
    parser.add_argument("--b-label", default="B")
    return parser.parse_args()


def fetch_variant(args, label, product_id, date_range):
    query = build_variant_query(args, product_id, date_range)
    payload = run_cubejs_query(query, token=args.token, cookie=args.cookie, base_url=args.base_url)
    return {
        "label": label,
        "product_id": product_id,
        "date_range": parse_date_range(date_range),
        "query": query,
        "metrics": extract_metrics(payload),
    }


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))

    variant_a = fetch_variant(args, args.a_label, args.a_product_id, args.a_date_range)
    variant_b = fetch_variant(args, args.b_label, args.b_product_id, args.b_date_range)
    payload = build_comparison_payload(variant_a, variant_b)

    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    write_json(json_path, payload)
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
