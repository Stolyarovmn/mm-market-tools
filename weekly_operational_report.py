#!/usr/bin/env python3
import argparse
from pathlib import Path

import requests

from core.dates import market_window_bounds, parse_moscow_datetime, to_epoch_ms
from core.documents_api import create_request, download_file, fetch_requests, find_latest_matching_request, wait_for_request
from core.io_utils import write_csv_rows, write_json
from core.operational_dashboard import build_operational_dashboard, normalize_operational_rows
from core.official_reports import load_left_out_report, load_sells_report, make_summary, merge_reports, write_markdown
from core.paths import DASHBOARD_DIR, NORMALIZED_DIR, RAW_REPORTS_DIR, REPORTS_DIR, ensure_dir, today_tag


def build_documents_payload(job_type, shop_id, date_from=None, date_to=None, group=False, returns=False):
    payload = {
        "jobType": job_type,
        "params": {
            "shopId": None,
            "shopIds": [shop_id],
            "contentType": "CSV",
            "language": "ru",
        },
    }
    if job_type == "SELLS_REPORT":
        payload["params"].update(
            {
                "group": group,
                "returns": returns,
                "dateFrom": to_epoch_ms(date_from),
                "dateTo": to_epoch_ms(date_to),
            }
        )
    return payload


def extract_match_params(payload):
    params = dict((payload or {}).get("params") or {})
    params.pop("shopId", None)
    return params


def create_or_reuse_request(session, token, payload, poll_interval=3.0, timeout_seconds=120.0):
    job_type = payload["jobType"]
    match_params = extract_match_params(payload)
    try:
        created = create_request(session, token, payload)
        request_payload = created.get("payload") or {}
        request_id = request_payload.get("requestId")
        if request_id is None:
            raise RuntimeError(f"Missing requestId for {job_type}")
        final_row = wait_for_request(
            session,
            token,
            request_id,
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
        )
        return final_row, "created"
    except requests.HTTPError as exc:
        response = exc.response
        if response is None or response.status_code != 400:
            raise
        requests_payload = fetch_requests(session, token, page=0, size=50)
        existing = find_latest_matching_request(requests_payload, job_type, match_params)
        if existing:
            return existing, "reused"
        detail = response.text.strip()
        raise RuntimeError(f"Unable to create or reuse {job_type}: {detail}") from exc


def resolve_window(args):
    if args.date_from and args.date_to:
        date_from = parse_moscow_datetime(args.date_from)
        date_to = parse_moscow_datetime(args.date_to)
        return date_from, date_to
    return market_window_bounds(args.window_days)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a weekly operational report by requesting official seller CSV reports."
    )
    parser.add_argument("--token", required=True)
    parser.add_argument("--shop-id", type=int, default=98)
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--raw-dir", default=str(RAW_REPORTS_DIR))
    parser.add_argument("--normalized-dir", default=str(NORMALIZED_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--report-prefix", default=f"weekly_operational_report_{today_tag()}")
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    raw_dir = ensure_dir(Path(args.raw_dir))
    normalized_dir = ensure_dir(Path(args.normalized_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))
    date_from, date_to = resolve_window(args)

    with requests.Session() as session:
        sells_final, sells_mode = create_or_reuse_request(
            session,
            args.token,
            build_documents_payload("SELLS_REPORT", args.shop_id, date_from, date_to, group=True, returns=False),
            poll_interval=args.poll_interval,
            timeout_seconds=args.timeout_seconds,
        )
        left_final, left_mode = create_or_reuse_request(
            session,
            args.token,
            build_documents_payload("LEFT_OUT_REPORT", args.shop_id),
            poll_interval=args.poll_interval,
            timeout_seconds=args.timeout_seconds,
        )

        sells_link = ((sells_final.get("result") or {}).get("link"))
        left_link = ((left_final.get("result") or {}).get("link"))
        if not sells_link or not left_link:
            raise SystemExit("One of the report links is missing")

        sells_name = (sells_final.get("result") or {}).get("fileName") or f"sells-report-{today_tag()}.csv"
        left_name = (left_final.get("result") or {}).get("fileName") or f"left-out-report-{today_tag()}.csv"
        sells_path = download_file(session, sells_link, raw_dir / sells_name)
        left_path = download_file(session, left_link, raw_dir / left_name)

    sells_rows = load_sells_report(str(sells_path))
    left_rows = load_left_out_report(str(left_path))
    window_days = round((date_to - date_from).total_seconds() / 86400, 2)
    merged = merge_reports(sells_rows, left_rows, window_days=window_days)
    summary = make_summary(merged)
    normalized_payload = {
        "metadata": {
            "window": {
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "window_days": window_days,
            },
            "sources": {
                "sells_csv": str(sells_path),
                "left_out_csv": str(left_path),
            },
            "documents": {
                "sells_request_id": sells_final.get("requestId"),
                "left_out_request_id": left_final.get("requestId"),
                "sells_mode": sells_mode,
                "left_out_mode": left_mode,
            },
        },
        "summary": summary,
        "rows": normalize_operational_rows(merged),
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
    write_json(
        json_path,
        {
            **normalized_payload["metadata"],
            "summary": summary,
            "rows": merged,
        },
    )
    write_csv_rows(csv_path, merged)
    write_markdown(summary, md_path, str(sells_path), str(left_path))
    write_json(normalized_path, normalized_payload)
    write_json(dashboard_path, dashboard_payload)
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {normalized_path}")
    print(f"Saved: {dashboard_path}")


if __name__ == "__main__":
    main()
