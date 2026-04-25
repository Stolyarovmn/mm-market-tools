#!/usr/bin/env python3
import argparse
from pathlib import Path

from core.dates import infer_window_from_report_source
from core.io_utils import write_csv_rows, write_json
from core.official_reports import load_left_out_report, load_sells_report, make_summary, merge_reports
from core.paths import REPORTS_DIR, ensure_dir, today_tag


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze MM seller reports on product-family level using product_id, barcode and SKU signals."
    )
    parser.add_argument("--sells-report", required=True)
    parser.add_argument("--left-out-report", required=True)
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--report-prefix", default=f"variant_family_analysis_{today_tag()}")
    return parser.parse_args()


def build_markdown(summary, path, sells_source, left_source):
    lines = [
        "# Анализ семейств товаров",
        "",
        f"- sells source: `{sells_source}`",
        f"- left-out source: `{left_source}`",
        f"- всего семейств: `{summary.get('family_rows', 0)}`",
        f"- семейств с продажами: `{summary.get('sold_families', 0)}`",
        f"- семейств-победителей: `{summary.get('winner_families', 0)}`",
        f"- многовариантных семейств: `{summary.get('multi_variant_families', 0)}`",
        "",
        "## Сильные семейства",
        "",
    ]
    for row in summary.get("family_current_winners", [])[:15]:
        lines.append(
            f"- {row['title']} | variants `{row['variant_count']}` | sold `{row['sold_units_sum']}` | net `{row['net_revenue_sum']} ₽` | avg_daily `{row['avg_daily_sales_sum']}`"
        )
    lines.extend(["", "## Слабые, но живые сигналы", ""])
    for row in summary.get("family_soft_signal_products", [])[:15]:
        lines.append(
            f"- {row['title']} | variants `{row['variant_count']}` | sold `{row['sold_units_sum']}` | net `{row['net_revenue_sum']} ₽`"
        )
    lines.extend(["", "## Семейства на дозакупку", ""])
    for row in summary.get("family_reorder_now", [])[:15]:
        lines.append(
            f"- {row['title']} | sold `{row['sold_units_sum']}` | stock `{row['stock_units_sum']}` | cover `{row['stock_cover_days']}`"
        )
    lines.extend(["", "## Крупные карточки с вариантами", ""])
    for row in summary.get("largest_multi_variant_families", [])[:15]:
        lines.append(
            f"- {row['title']} | variants `{row['variant_count']}` | barcodes `{row['barcode_count']}` | stock `{row['stock_units_sum']}` | sold `{row['sold_units_sum']}`"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    sells_rows = load_sells_report(args.sells_report)
    left_rows = load_left_out_report(args.left_out_report)
    merged = merge_reports(sells_rows, left_rows, window_days=(infer_window_from_report_source(args.sells_report) or {}).get("window_days"))
    summary = make_summary(merged)
    family_rows = summary.get("family_rows_payload", [])

    json_path = report_dir / f"{args.report_prefix}.json"
    csv_path = report_dir / f"{args.report_prefix}.csv"
    md_path = report_dir / f"{args.report_prefix}.md"

    write_json(
        json_path,
        {
            "metadata": {
                "sources": {
                    "sells_report": args.sells_report,
                    "left_out_report": args.left_out_report,
                }
            },
            "summary": {
                "family_rows": summary.get("family_rows", 0),
                "sold_families": summary.get("sold_families", 0),
                "winner_families": summary.get("winner_families", 0),
                "multi_variant_families": summary.get("multi_variant_families", 0),
            },
            "families": family_rows,
        },
    )
    write_csv_rows(csv_path, family_rows)
    build_markdown(summary, md_path, args.sells_report, args.left_out_report)
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
