#!/usr/bin/env python3
import argparse
from pathlib import Path

from core.io_utils import load_json, write_json
from core.paths import NORMALIZED_DIR, REPORTS_DIR, ensure_dir, today_tag


DEFAULT_THRESHOLDS = [99, 149, 199, 299, 399, 499, 799, 999, 1499, 1999]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Detect SKU prices slightly above psychological filter thresholds."
    )
    parser.add_argument(
        "--input-json",
        default=str(NORMALIZED_DIR / "weekly_operational_report_2026-04-08.json"),
    )
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--report-prefix", default=f"price_trap_report_{today_tag()}")
    parser.add_argument(
        "--thresholds",
        nargs="*",
        type=int,
        default=DEFAULT_THRESHOLDS,
        help="Psychological price caps to audit against.",
    )
    parser.add_argument(
        "--max-overshoot",
        type=float,
        default=15.0,
        help="Max rubles above threshold to still count as a trap.",
    )
    parser.add_argument(
        "--max-relative-overshoot-pct",
        type=float,
        default=5.0,
        help="Max percent above threshold to still count as a trap.",
    )
    parser.add_argument(
        "--min-stock",
        type=int,
        default=1,
        help="Only include SKU with at least this stock.",
    )
    return parser.parse_args()


def find_nearest_threshold(price, thresholds):
    below = [t for t in thresholds if t < price]
    if not below:
        return None
    return max(below)


def classify_trap(row, thresholds, max_overshoot, max_relative_overshoot_pct):
    price = float(row.get("sale_price") or 0.0)
    if price <= 0:
        return None
    threshold = find_nearest_threshold(price, thresholds)
    if threshold is None:
        return None
    overshoot = round(price - threshold, 2)
    relative = round((overshoot / threshold) * 100.0, 2) if threshold else None
    if overshoot <= 0:
        return None
    if overshoot > max_overshoot:
        return None
    if relative is not None and relative > max_relative_overshoot_pct:
        return None
    suggested_price = threshold
    severity_score = round(
        (row.get("stock_value_sale") or 0)
        + (row.get("units_sold") or 0) * 100
        + max(0, 20 - overshoot) * 10,
        2,
    )
    return {
        "key": row.get("key"),
        "product_id": row.get("product_id"),
        "barcode": row.get("barcode"),
        "title": row.get("title"),
        "sale_price": price,
        "threshold": threshold,
        "overshoot_rub": overshoot,
        "overshoot_pct": relative,
        "suggested_price": suggested_price,
        "units_sold": row.get("units_sold", 0),
        "total_stock": row.get("total_stock", 0),
        "stock_value_sale": row.get("stock_value_sale", 0.0),
        "current_winner": bool(row.get("current_winner")),
        "historical_only_hit": bool(row.get("historical_only_hit")),
        "stale_stock": bool(row.get("stale_stock")),
        "severity_score": severity_score,
        "recommendation": (
            "Проверить перевод под психологический порог"
            if row.get("total_stock", 0) > 0
            else "Сначала проверить наличие"
        ),
    }


def build_markdown(rows, args, source_path):
    lines = [
        "# Price Trap Report",
        "",
        f"- source: `{source_path}`",
        f"- thresholds: `{', '.join(str(v) for v in args.thresholds)}`",
        f"- max overshoot: `{args.max_overshoot} ₽`",
        f"- max relative overshoot: `{args.max_relative_overshoot_pct}%`",
        f"- matched sku: `{len(rows)}`",
        "",
        "## Top candidates",
        "",
    ]
    if not rows:
        lines.append("- Ловушек рядом с психологическими порогами не найдено.")
        return "\n".join(lines)
    for row in rows[:25]:
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- current price: `{row['sale_price']} ₽`",
                f"- nearby cap: `{row['threshold']} ₽`",
                f"- overshoot: `{row['overshoot_rub']} ₽` (`{row['overshoot_pct']}%`)",
                f"- suggested test price: `{row['suggested_price']} ₽`",
                f"- sold in window: `{row['units_sold']}`",
                f"- stock: `{row['total_stock']}`",
                f"- stale stock: `{row['stale_stock']}`",
                "",
            ]
        )
    return "\n".join(lines)


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    payload = load_json(Path(args.input_json))
    rows = []
    for row in payload.get("rows") or []:
        if int(row.get("total_stock") or 0) < args.min_stock:
            continue
        trap = classify_trap(row, args.thresholds, args.max_overshoot, args.max_relative_overshoot_pct)
        if trap:
            rows.append(trap)
    rows.sort(
        key=lambda row: (
            row["severity_score"],
            row["units_sold"],
            row["stock_value_sale"],
        ),
        reverse=True,
    )
    result = {
        "generated_from": args.input_json,
        "thresholds": args.thresholds,
        "max_overshoot": args.max_overshoot,
        "max_relative_overshoot_pct": args.max_relative_overshoot_pct,
        "rows": rows,
        "summary": {
            "matched_skus": len(rows),
            "top_thresholds": {
                str(threshold): sum(1 for row in rows if row["threshold"] == threshold)
                for threshold in args.thresholds
            },
        },
    }
    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    write_json(json_path, result)
    md_path.write_text(build_markdown(rows, args, args.input_json), encoding="utf-8")
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
