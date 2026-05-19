#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from core.dates import infer_window_from_report_source
from core.io_utils import write_json
from core.official_reports import load_left_out_report, load_sells_report, make_summary, merge_reports
from core.operational_dashboard import build_operational_dashboard, normalize_operational_rows


def parse_args():
    parser = argparse.ArgumentParser(
        description="Refresh an operational dashboard bundle from existing raw CSV and metadata, without re-requesting reports."
    )
    parser.add_argument("--sells-report", required=True)
    parser.add_argument("--left-out-report", required=True)
    parser.add_argument("--metadata-from")
    parser.add_argument("--normalized-output", required=True)
    parser.add_argument("--dashboard-output", required=True)
    return parser.parse_args()


def load_metadata(path):
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload.get("metadata") or {}


def enrich_metadata(metadata, sells_report, left_out_report):
    metadata = dict(metadata or {})
    sources = dict(metadata.get("sources") or {})
    if not sources.get("sells_report") and not sources.get("sells_csv"):
        sources["sells_report"] = sells_report
    if not sources.get("left_out_report") and not sources.get("left_out_csv"):
        sources["left_out_report"] = left_out_report
    metadata["sources"] = sources
    if not (metadata.get("window") or {}).get("date_from"):
        inferred = infer_window_from_report_source(sources.get("sells_report") or sources.get("sells_csv") or sells_report)
        if inferred:
            metadata["window"] = inferred
    return metadata


def main():
    args = parse_args()
    metadata = enrich_metadata(load_metadata(args.metadata_from), args.sells_report, args.left_out_report)
    sells_rows = load_sells_report(args.sells_report)
    left_rows = load_left_out_report(args.left_out_report)
    merged = merge_reports(sells_rows, left_rows, window_days=(metadata.get("window") or {}).get("window_days"))
    summary = make_summary(merged)
    normalized_payload = {
        "metadata": metadata,
        "summary": summary,
        "rows": normalize_operational_rows(merged),
        "family_rows": summary.get("family_rows_payload", []),
    }
    dashboard_payload = build_operational_dashboard(merged, summary, metadata=metadata)
    write_json(Path(args.normalized_output), normalized_payload)
    write_json(Path(args.dashboard_output), dashboard_payload)
    print(f"Saved: {args.normalized_output}")
    print(f"Saved: {args.dashboard_output}")


if __name__ == "__main__":
    main()
