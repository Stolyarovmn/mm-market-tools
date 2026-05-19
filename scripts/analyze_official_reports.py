#!/usr/bin/env python3
import argparse
from pathlib import Path

from core.dates import infer_window_from_report_source
from core.io_utils import write_csv_rows, write_json
from core.operational_dashboard import build_operational_dashboard, normalize_operational_rows
from core.official_reports import (
    load_left_out_report,
    load_sells_report,
    make_summary,
    merge_reports,
    write_markdown,
)
from core.paths import DASHBOARD_DIR, NORMALIZED_DIR, REPORTS_DIR, ensure_dir, today_tag


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze official MM seller sells/left-out reports over a real period."
    )
    parser.add_argument("--sells-report", required=True)
    parser.add_argument("--left-out-report", required=True)
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--normalized-dir", default=str(NORMALIZED_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--report-prefix", default=f"official_period_analysis_{today_tag()}")
    return parser.parse_args()


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    normalized_dir = ensure_dir(Path(args.normalized_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))
    sells_rows = load_sells_report(args.sells_report)
    left_rows = load_left_out_report(args.left_out_report)
    window = infer_window_from_report_source(args.sells_report)
    merged = merge_reports(sells_rows, left_rows, window_days=window.get("window_days"))
    summary = make_summary(merged)
    normalized_payload = {
        "metadata": {
            "window": window,
            "sources": {
                "sells_report": args.sells_report,
                "left_out_report": args.left_out_report,
            }
        },
        "summary": summary,
        "rows": normalize_operational_rows(merged),
        "family_rows": summary.get("family_rows_payload", []),
    }
    dashboard_payload = build_operational_dashboard(
        merged,
        summary,
        metadata=normalized_payload["metadata"],
    )

    json_path = report_dir / f"{args.report_prefix}.json"
    csv_path = report_dir / f"{args.report_prefix}.csv"
    md_path = report_dir / f"{args.report_prefix}.md"
    normalized_path = normalized_dir / f"{args.report_prefix}.json"
    dashboard_path = dashboard_dir / f"{args.report_prefix}.json"
    write_json(json_path, {"summary": summary, "rows": merged})
    write_csv_rows(csv_path, merged)
    write_markdown(summary, md_path, args.sells_report, args.left_out_report)
    write_json(normalized_path, normalized_payload)
    write_json(dashboard_path, dashboard_payload)
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {normalized_path}")
    print(f"Saved: {dashboard_path}")


if __name__ == "__main__":
    main()
