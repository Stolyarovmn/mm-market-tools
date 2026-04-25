#!/usr/bin/env python3
import argparse

from core.dates import infer_window_from_report_source
from core.operational_dashboard import build_operational_dashboard, normalize_operational_rows
from core.official_reports import load_left_out_report, load_sells_report, make_summary, merge_reports
from core.paths import RAW_REPORTS_DIR


def parse_args():
    parser = argparse.ArgumentParser(description="Smoke test for official reports operational pipeline.")
    parser.add_argument("--sells-report", default=str(RAW_REPORTS_DIR / "sells-report.csv"))
    parser.add_argument("--left-out-report", default=str(RAW_REPORTS_DIR / "left-out-report.csv"))
    return parser.parse_args()


def main():
    args = parse_args()
    sells_rows = load_sells_report(args.sells_report)
    left_rows = load_left_out_report(args.left_out_report)
    merged = merge_reports(sells_rows, left_rows, window_days=(infer_window_from_report_source(args.sells_report) or {}).get("window_days"))
    summary = make_summary(merged)
    normalized = normalize_operational_rows(merged)
    dashboard = build_operational_dashboard(merged, summary)

    assert sells_rows, "sells report is empty"
    assert left_rows, "left-out report is empty"
    assert merged, "merged dataset is empty"
    assert summary["rows"] == len(merged), "summary rows mismatch"
    assert summary["sold_skus"] > 0, "expected at least one sold sku in current sample"
    assert len(normalized) == len(merged), "normalized rows mismatch"
    assert dashboard["kpis"]["total_skus"] == len(merged), "dashboard total_skus mismatch"
    assert "current_winners" in dashboard["tables"], "missing current_winners table"
    assert "reorder_now" in dashboard["actions"], "missing reorder action list"
    assert "family_current_winners" in dashboard["family_tables"], "missing family winners table"
    assert "family_rows_payload" in summary, "missing family payload in summary"
    print("SMOKE_OK")
    print(f"rows={summary['rows']}")
    print(f"sold_skus={summary['sold_skus']}")
    print(f"revenue_total={summary['revenue_total']}")
    print(f"gross_profit_total={summary['gross_profit_total']}")


if __name__ == "__main__":
    main()
