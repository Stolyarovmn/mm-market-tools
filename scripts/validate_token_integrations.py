#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from core.auth import bearer_headers, require_access_token, token_expiry_info
from core.cubejs_api import fetch_cubejs_meta, run_cubejs_query
from core.dates import market_window_bounds
from core.documents_api import fetch_requests
from core.http_client import create_session
from core.io_utils import write_json
from core.paths import REPORTS_DIR, ensure_dir, today_tag


def build_simple_cubejs_query(shop_id):
    date_from, date_to = market_window_bounds(7)
    return {
        "measures": [
            "Sales.seller_revenue_without_delivery_measure",
        ],
        "timezone": "Europe/Moscow",
        "timeDimensions": [
            {
                "dimension": "Sales.created_at",
                "dateRange": [date_from.date().isoformat(), date_to.date().isoformat()],
                "granularity": "day",
            }
        ],
        "filters": [
            {
                "member": "Sales.shop_id",
                "operator": "equals",
                "values": [str(shop_id)],
            }
        ],
    }


def build_secondary_cubejs_query(shop_id):
    date_from, date_to = market_window_bounds(7)
    return {
        "measures": [
            "Sales.orders_number",
            "Sales.item_sold_number",
        ],
        "timezone": "Europe/Moscow",
        "timeDimensions": [
            {
                "dimension": "Sales.created_at",
                "dateRange": [date_from.date().isoformat(), date_to.date().isoformat()],
                "granularity": "day",
            }
        ],
        "filters": [
            {
                "member": "Sales.shop_id",
                "operator": "equals",
                "values": [str(shop_id)],
            }
        ],
    }


def check_documents_create(token, shop_id):
    payload = {
        "jobType": "LEFT_OUT_REPORT",
        "params": {
            "shopId": None,
            "shopIds": [shop_id],
            "contentType": "CSV",
            "language": "ru",
        },
    }
    with create_session() as session:
        response = session.post(
            "https://api.business.kazanexpress.ru/api/seller/documents/create",
            headers=bearer_headers(token),
            json=payload,
            timeout=30,
        )
        return {
            "ok": response.ok,
            "status_code": response.status_code,
            "body": response.text[:1000],
        }


def parse_args():
    parser = argparse.ArgumentParser(description="Validate all major token-based integrations for MM tools.")
    parser.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    parser.add_argument("--shop-id", type=int, default=int(os.getenv("MM_MY_SHOP_ID", "98")))
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--report-prefix", default=f"token_validation_{today_tag()}")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        token = require_access_token(args.token)
    except ValueError as exc:
        raise SystemExit(str(exc))
    report_dir = ensure_dir(Path(args.report_dir))
    result = {"shop_id": args.shop_id}
    result["token_health"] = token_expiry_info(token)

    try:
        meta = fetch_cubejs_meta(token=token)
        result["cubejs_meta"] = {
            "ok": True,
            "cubes": len(meta.get("cubes") or []),
            "sales_cube_present": any(cube.get("name") == "Sales" for cube in meta.get("cubes") or []),
        }
    except Exception as exc:
        result["cubejs_meta"] = {"ok": False, "error": str(exc)}

    try:
        query_payload = run_cubejs_query(build_simple_cubejs_query(args.shop_id), token=token)
        secondary_payload = run_cubejs_query(build_secondary_cubejs_query(args.shop_id), token=token)
        result["cubejs_load"] = {
            "ok": True,
            "revenue_rows": len(((query_payload.get("results") or [{}])[0].get("data") or [])),
            "orders_items_rows": len(((secondary_payload.get("results") or [{}])[0].get("data") or [])),
        }
    except Exception as exc:
        result["cubejs_load"] = {"ok": False, "error": str(exc)}

    try:
        with create_session() as session:
            requests_payload = fetch_requests(session, token, page=0, size=100)
        payload = requests_payload.get("payload") or {}
        result["documents_requests"] = {
            "ok": True,
            "total_elements": payload.get("totalElements"),
            "rows": len(payload.get("requests") or []),
        }
    except Exception as exc:
        result["documents_requests"] = {"ok": False, "error": str(exc)}

    try:
        result["documents_create"] = check_documents_create(token, args.shop_id)
    except Exception as exc:
        result["documents_create"] = {"ok": False, "error": str(exc)}

    output = report_dir / f"{args.report_prefix}.json"
    write_json(output, result)
    print(f"Saved: {output}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
