#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path


DEFAULT_SNAPSHOT_DIR = "/home/user/mm-market-tools/data/snapshots"
DEFAULT_REPORT_DIR = "/home/user/mm-market-tools/reports"


def load_snapshot(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def product_map(snapshot):
    return {int(row["product_id"]): row for row in snapshot.get("products", [])}


def days_between(start_ts, end_ts):
    start = dt.datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
    end = dt.datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
    delta = end - start
    return max(delta.total_seconds() / 86400, 1 / 24)


def compute_metrics(start_row, end_row, window_days):
    sold_start = int(start_row.get("sold_total") or 0)
    sold_end = int(end_row.get("sold_total") or 0)
    sold_window = max(0, sold_end - sold_start)
    active_end = int(end_row.get("active_qty") or 0)
    avg_daily_sales = sold_window / window_days if window_days > 0 else 0
    stock_cover_days = (active_end / avg_daily_sales) if avg_daily_sales > 0 else math.inf
    stockout_risk = avg_daily_sales > 0 and stock_cover_days <= 14
    stale_stock = sold_window == 0 and active_end > 0
    sell_through_proxy = sold_window / (sold_window + active_end) if (sold_window + active_end) > 0 else 0
    return {
        "product_id": int(end_row["product_id"]),
        "title": end_row["title"],
        "price": float(end_row.get("price") or 0),
        "rating": float(end_row.get("rating") or 0),
        "reviews": int(end_row.get("reviews") or 0),
        "sold_window": sold_window,
        "avg_daily_sales": round(avg_daily_sales, 2),
        "active_end": active_end,
        "stock_cover_days": None if math.isinf(stock_cover_days) else round(stock_cover_days, 1),
        "stockout_risk": stockout_risk,
        "stale_stock": stale_stock,
        "sell_through_proxy": round(sell_through_proxy, 3),
    }


def analyze_window(start_snapshot, end_snapshot):
    window_days = days_between(start_snapshot["captured_at"], end_snapshot["captured_at"])
    start_map = product_map(start_snapshot)
    end_map = product_map(end_snapshot)
    rows = []
    for product_id, end_row in end_map.items():
        start_row = start_map.get(product_id)
        if not start_row:
            start_row = {
                "product_id": product_id,
                "title": end_row.get("title", ""),
                "price": end_row.get("price", 0),
                "sold_total": 0,
                "active_qty": 0,
                "rating": end_row.get("rating", 0),
                "reviews": end_row.get("reviews", 0),
            }
        rows.append(compute_metrics(start_row, end_row, window_days))
    rows.sort(key=lambda row: (row["sold_window"], row["avg_daily_sales"]), reverse=True)
    return window_days, rows


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "product_id",
                "title",
                "price",
                "sold_window",
                "avg_daily_sales",
                "active_end",
                "stock_cover_days",
                "stockout_risk",
                "stale_stock",
                "sell_through_proxy",
                "rating",
                "reviews",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["product_id"],
                    row["title"],
                    row["price"],
                    row["sold_window"],
                    row["avg_daily_sales"],
                    row["active_end"],
                    row["stock_cover_days"],
                    row["stockout_risk"],
                    row["stale_stock"],
                    row["sell_through_proxy"],
                    row["rating"],
                    row["reviews"],
                ]
            )


def write_markdown(rows, path, window_days, start_path, end_path):
    top_sellers = [row for row in rows if row["sold_window"] > 0][:20]
    stockout_risk = [row for row in rows if row["stockout_risk"]][:20]
    stale = [row for row in rows if row["stale_stock"]][:20]
    lines = [
        "# Оконный анализ продаж",
        "",
        f"- окно: `{round(window_days, 1)}` дней",
        f"- начальный снапшот: `{start_path}`",
        f"- конечный снапшот: `{end_path}`",
        "",
        "## Что продаётся сейчас",
        "",
    ]
    for row in top_sellers:
        lines.append(
            f"- {row['title']} | sold_window `{row['sold_window']}` | avg_daily `{row['avg_daily_sales']}` | active `{row['active_end']}`"
        )
    lines.extend(["", "## Что рискует закончиться", ""])
    for row in stockout_risk:
        lines.append(
            f"- {row['title']} | sold_window `{row['sold_window']}` | cover `{row['stock_cover_days']}` days | active `{row['active_end']}`"
        )
    lines.extend(["", "## Что стоит без движения", ""])
    for row in stale:
        lines.append(
            f"- {row['title']} | active `{row['active_end']}` | price `{row['price']} ₽`"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze sales and stock over a real time window using two dated shop snapshots."
    )
    parser.add_argument("--start-snapshot", required=True)
    parser.add_argument("--end-snapshot", required=True)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--date-tag", default=dt.date.today().isoformat())
    parser.add_argument("--report-prefix", default="time_window_analysis")
    return parser.parse_args()


def main():
    args = parse_args()
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    start_snapshot = load_snapshot(args.start_snapshot)
    end_snapshot = load_snapshot(args.end_snapshot)
    window_days, rows = analyze_window(start_snapshot, end_snapshot)
    json_path = report_dir / f"{args.report_prefix}_{args.date_tag}.json"
    csv_path = report_dir / f"{args.report_prefix}_{args.date_tag}.csv"
    md_path = report_dir / f"{args.report_prefix}_{args.date_tag}.md"
    json_path.write_text(
        json.dumps({"window_days": round(window_days, 2), "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(rows, csv_path)
    write_markdown(rows, md_path, window_days, args.start_snapshot, args.end_snapshot)
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
