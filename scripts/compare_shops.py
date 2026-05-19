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
            params={"size": DEFAULT_PAGE_SIZE, "page": page},
            timeout=DEFAULT_TIMEOUT,
        )
        page_products = data.get("productList") or []
        if not page_products:
            break
        products.extend(page_products)
        if pause:
            time.sleep(pause)
    return products


def build_title_map(products):
    result = {}
    for product in products:
        title = (product.get("title") or "").strip().lower()
        if title:
            result[title] = product
    return result


def compare_products(my_products, competitor_products, top):
    my_titles = build_title_map(my_products)
    competitor_titles = build_title_map(competitor_products)

    overlaps = []
    for title, competitor_product in competitor_titles.items():
        if title not in my_titles:
            continue
        my_product = my_titles[title]
        overlaps.append(
            {
                "title": competitor_product.get("title", ""),
                "my_price": my_product.get("price"),
                "competitor_price": competitor_product.get("price"),
                "diff": (my_product.get("price") or 0) - (competitor_product.get("price") or 0),
            }
        )

    overlaps.sort(key=lambda item: item["diff"], reverse=True)

    competitor_hits = [
        product
        for product in competitor_products
        if (product.get("title") or "").strip().lower() not in my_titles
        and product.get("quantitySold", 0) > 100
    ]
    competitor_hits.sort(key=lambda item: item.get("quantitySold", 0), reverse=True)

    print("### PRICE OVERLAPS ###")
    if not overlaps:
        print("No exact title overlaps found.")
    else:
        for item in overlaps[:top]:
            status = "MY_PRICE_HIGHER" if item["diff"] > 0 else "MY_PRICE_LOWER_OR_EQUAL"
            print(
                f"- {item['title']}\n"
                f"  my_price={item['my_price']} competitor_price={item['competitor_price']} "
                f"diff={item['diff']} status={status}"
            )

    print("\n### COMPETITOR EXCLUSIVE HITS ###")
    if not competitor_hits:
        print("No exclusive competitor hits found with quantitySold > 100.")
    else:
        for product in competitor_hits[:top]:
            print(
                f"- {product.get('title', '')}\n"
                f"  sold={product.get('quantitySold', 0)} price={product.get('price')}"
            )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare your shop products with a competitor using seller API."
    )
    parser.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    parser.add_argument("--my-shop-id", type=int, default=int(os.getenv("MM_MY_SHOP_ID", "98")))
    parser.add_argument(
        "--competitor-shop-id",
        type=int,
        default=int(os.getenv("MM_COMPETITOR_SHOP_ID", "40319")),
    )
    parser.add_argument("--my-pages", type=int, default=9)
    parser.add_argument("--competitor-pages", type=int, default=5)
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--pause", type=float, default=0.3)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        token = require_access_token(args.token)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    with create_session() as session:
        print(f"Loading products for my shop {args.my_shop_id}...")
        my_products = get_products(session, token, args.my_shop_id, args.my_pages, args.pause)
        print(f"Loaded {len(my_products)} products.")

        print(f"Loading products for competitor shop {args.competitor_shop_id}...")
        competitor_products = get_products(
            session, token, args.competitor_shop_id, args.competitor_pages, args.pause
        )
        print(f"Loaded {len(competitor_products)} products.")

    compare_products(my_products, competitor_products, args.top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
