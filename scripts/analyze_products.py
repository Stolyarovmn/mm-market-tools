#!/usr/bin/env python3
import argparse
import os
import sys
import time

from core.auth import bearer_headers, require_access_token
from core.http_client import create_session, request_json


DEFAULT_TIMEOUT = 20
DEFAULT_PAGE_SIZE = 100

def seller_headers(token):
    return bearer_headers(token)


def get_products(session, token, shop_id, pages, pause):
    products = []
    base_url = (
        f"https://api.business.kazanexpress.ru/api/seller/shop/{shop_id}/product/getProducts"
    )
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


def analyze_products(products, top):
    out_of_stock_hits = []
    dead_stock = []
    low_stock = []

    for product in products:
        sold = product.get("quantitySold", 0)
        active = product.get("quantityActive", 0)
        title = product.get("title", "No Title")

        if active == 0 and sold > 20:
            out_of_stock_hits.append((sold, title))
        if active > 10 and sold < 2:
            dead_stock.append((active, sold, title))
        if 0 < active <= 3 and sold > 5:
            low_stock.append((active, sold, title))

    out_of_stock_hits.sort(reverse=True)
    dead_stock.sort(key=lambda item: item[0], reverse=True)
    low_stock.sort(key=lambda item: item[1], reverse=True)

    print("### OUT OF STOCK BESTSELLERS ###")
    for sold, title in out_of_stock_hits[:top]:
        print(f"- {title}: sold={sold}")

    print("\n### DEAD STOCK ###")
    for active, sold, title in dead_stock[:top]:
        print(f"- {title}: active={active} sold={sold}")

    print("\n### LOW STOCK ###")
    for active, sold, title in low_stock[:top]:
        print(f"- {title}: active={active} sold={sold}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze stock and sales for a single seller shop."
    )
    parser.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    parser.add_argument("--shop-id", type=int, default=int(os.getenv("MM_MY_SHOP_ID", "98")))
    parser.add_argument("--pages", type=int, default=9)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--pause", type=float, default=0.5)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        token = require_access_token(args.token)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Loading products for shop {args.shop_id}...")
    with create_session() as session:
        products = get_products(session, token, args.shop_id, args.pages, args.pause)
    print(f"Loaded {len(products)} products.")
    analyze_products(products, args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
