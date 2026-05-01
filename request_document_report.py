#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import time
from pathlib import Path

from core.auth import require_access_token
from core.dates import parse_moscow_datetime, to_epoch_ms
from core.documents_api import create_request, fetch_requests
from core.http_client import create_session, download_bytes
from core.paths import REPORTS_DIR


DEFAULT_BASE_URL = "https://api.business.kazanexpress.ru/api/seller/documents"
DEFAULT_REPORT_DIR = str(REPORTS_DIR)


def find_request(requests_payload, request_id):
    requests_list = ((requests_payload.get("payload") or {}).get("requests") or [])
    for row in requests_list:
        if int(row.get("requestId")) == int(request_id):
            return row
    return None


def maybe_download(session, url, output_path):
    output_path.write_bytes(download_bytes(session, url, timeout=60))


def parse_timestamp(value):
    if value is None:
        return None
    return dt.datetime.fromtimestamp(value / 1000, tz=dt.timezone.utc)


def build_payload(args):
    if args.payload_json:
        return json.loads(args.payload_json)

    payload = {
        "jobType": args.job_type,
        "params": {
            "shopId": None,
            "shopIds": [args.shop_id],
            "contentType": args.content_type,
            "language": args.language,
        },
    }
    if args.job_type == "SELLS_REPORT":
        if not args.date_from or not args.date_to:
            raise SystemExit("SELLS_REPORT requires --date-from and --date-to")
        date_from = parse_moscow_datetime(args.date_from)
        date_to = parse_moscow_datetime(args.date_to)
        payload["params"].update(
            {
                "group": args.group,
                "returns": args.returns,
                "dateFrom": to_epoch_ms(date_from),
                "dateTo": to_epoch_ms(date_to),
            }
        )
    return payload


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create and poll async seller document reports."
    )
    parser.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--report-prefix", default=f"document_report_{dt.date.today().isoformat()}")
    parser.add_argument("--job-type", choices=["LEFT_OUT_REPORT", "SELLS_REPORT"], required=True)
    parser.add_argument("--shop-id", type=int, default=int(os.getenv("MM_MY_SHOP_ID", "98")))
    parser.add_argument("--content-type", default="CSV")
    parser.add_argument("--language", default="ru")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--group", action="store_true")
    parser.add_argument("--returns", action="store_true")
    parser.add_argument("--payload-json")
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--download", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        token = require_access_token(args.token)
    except ValueError as exc:
        raise SystemExit(str(exc))

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args)

    with create_session() as session:
        created = create_request(session, token, payload, base_url=args.base_url)
        request_payload = created.get("payload") or {}
        request_id = request_payload.get("requestId")
        started = time.time()
        final_request = None
        while time.time() - started <= args.timeout_seconds:
            requests_payload = fetch_requests(session, token, base_url=args.base_url)
            found = find_request(requests_payload, request_id)
            if found and found.get("status") in {"COMPLETED", "FAILED"}:
                final_request = found
                break
            time.sleep(args.poll_interval)

        if not final_request:
            raise SystemExit(f"Timed out waiting for request {request_id}")

        json_path = report_dir / f"{args.report_prefix}.json"
        json_path.write_text(json.dumps(final_request, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {json_path}")

        result = final_request.get("result") or {}
        link = result.get("link")
        if args.download and link:
            filename = result.get("fileName") or f"{args.report_prefix}.bin"
            file_path = report_dir / filename
            maybe_download(session, link, file_path)
            print(f"Saved: {file_path}")


if __name__ == "__main__":
    main()
