#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

from core.auth import bearer_headers, require_access_token
from core.http_client import create_session, request_json
from core.paths import SNAPSHOTS_DIR


DEFAULT_TIMEOUT = 20
DEFAULT_PAGE_SIZE = 100
DEFAULT_SNAPSHOT_DIR = str(SNAPSHOTS_DIR)

def seller_headers(token):
    return bearer_headers(token)


def get_products(session, token, shop_id, pages, pause):
    products = []
    base_url = f"https://api.business.kazanexpress.ru/api/seller/shop/{shop_id}/product/getProducts"
    for page in range(pages):
        data = request_json(
            session,
            "GET",
            base_url,
            headers=seller_headers(token),
            params={
                "size": DEFAULT_PAGE_SIZE,
                "page": page,
                "sortBy": "id",
                "order": "descending",
            },
            timeout=DEFAULT_TIMEOUT,
        )
        page_products = data.get("productList") or []
        if not page_products:
            break
        products.extend(page_products)
        if pause:
            time.sleep(pause)
    return products


def normalize_product(product):
    return {
        "product_id": int(product.get("productId")),
        "title": product.get("title", ""),
        "price": float(product.get("price") or 0),
        "sold_total": int(product.get("quantitySold") or 0),
        "active_qty": int(product.get("quantityActive") or 0),
        "rating": float(product.get("rating") or 0),
        "reviews": int(product.get("feedbacksAmount") or 0),
        "status": (product.get("status") or {}).get("value"),
    }


def write_snapshot(products, path, captured_at, shop_id):
    rows = [normalize_product(product) for product in products]
    payload = {
        "captured_at": captured_at,
        "shop_id": shop_id,
        "products_count": len(rows),
        "products": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_snapshot_csv(products, path):
    rows = [normalize_product(product) for product in products]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["product_id", "title", "price", "sold_total", "active_qty", "rating", "reviews", "status"]
        )
        for row in rows:
            writer.writerow(
                [
                    row["product_id"],
                    row["title"],
                    row["price"],
                    row["sold_total"],
                    row["active_qty"],
                    row["rating"],
                    row["reviews"],
                    row["status"],
                ]
            )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Capture a dated snapshot of your shop assortment for time-window analysis."
    )
    parser.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    parser.add_argument("--shop-id", type=int, default=int(os.getenv("MM_MY_SHOP_ID", "98")))
    parser.add_argument("--pages", type=int, default=12)
    parser.add_argument("--pause", type=float, default=0.3)
    parser.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument("--date-tag", default=dt.date.today().isoformat())
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        token = require_access_token(args.token)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    snapshot_dir = Path(args.snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    captured_at = dt.datetime.now(dt.timezone.utc).isoformat()

    with create_session() as session:
        products = get_products(session, token, args.shop_id, args.pages, args.pause)
    json_path = snapshot_dir / f"shop_{args.shop_id}_{args.date_tag}.json"
    csv_path = snapshot_dir / f"shop_{args.shop_id}_{args.date_tag}.csv"
    write_snapshot(products, json_path, captured_at, args.shop_id)
    write_snapshot_csv(products, csv_path)
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
