#!/usr/bin/env python3
import argparse
import json
import statistics
import sys
import time
from collections import Counter

from core.http_client import build_mm_public_headers, create_session, request_json


ROOT_CATEGORIES_URL = "https://api.kazanexpress.ru/api/category/v2/root-categories"
SEARCH_URL = "https://web-api.mm.ru/v2/goods/search"
FILTERS_URL = "https://web-api.mm.ru/v1/goods/filters"
PRODUCT_URL = "https://api.kazanexpress.ru/api/v2/product/{product_id}"
DEFAULT_CATEGORY_ID = 10162
DEFAULT_PAGE_SIZE = 50
DEFAULT_SORT = {"type": "popularity", "order": "desc"}
MAX_OFFSET = 1000
MAX_ACCESSIBLE_PRODUCTS = MAX_OFFSET + DEFAULT_PAGE_SIZE
PRICE_FILTER_ID = "0"
DEFAULT_SLEEP_SECONDS = 0.5


def build_mm_headers():
    return build_mm_public_headers()


def fetch_json(session, url, *, method="GET", headers=None, json_body=None, timeout=20, max_attempts=4):
    return request_json(
        session,
        method,
        url,
        headers=headers,
        json_body=json_body,
        timeout=timeout,
        max_attempts=max_attempts,
    )


def fetch_root_categories(session):
    return fetch_json(session, ROOT_CATEGORIES_URL)["payload"]


def find_category(node, category_id):
    if isinstance(node, list):
        for item in node:
            found = find_category(item, category_id)
            if found:
                return found
        return None

    if not isinstance(node, dict):
        return None

    if node.get("id") == category_id:
        return node

    for child in node.get("children") or []:
        found = find_category(child, category_id)
        if found:
            return found
    return None


def collect_leaf_categories(node, into):
    children = node.get("children") or []
    if not children:
        into.append(node)
        return
    for child in children:
        collect_leaf_categories(child, into)


def make_search_payload(category_id, limit, offset, filters):
    return {
        "term": "",
        "pagination": {"limit": limit, "offset": offset},
        "sort": DEFAULT_SORT,
        "filters": filters,
        "storeCode": "000",
        "categories": [category_id],
        "token": "",
        "correctQuery": True,
        "catalogType": "4",
        "storeType": "market",
    }


def search_category_products(session, headers, category_id, limit, offset, filters):
    payload = make_search_payload(category_id, limit, offset, filters)
    return fetch_json(
        session,
        SEARCH_URL,
        method="POST",
        headers=headers,
        json_body=payload,
    )


def fetch_category_filters(session, headers, category_id, filters):
    payload = {
        "categoryIDs": [category_id],
        "term": "",
        "client": "",
        "correctQuery": True,
        "filters": filters,
        "includeAdultGoods": True,
        "service": "",
        "storeCodes": ["000"],
        "catalogType": "4",
        "storeType": "market",
    }
    return fetch_json(
        session,
        FILTERS_URL,
        method="POST",
        headers=headers,
        json_body=payload,
    )


def fetch_seller_from_product(session, product_id):
    data = fetch_json(session, PRODUCT_URL.format(product_id=product_id))
    return data["payload"]["data"]["seller"]


def get_total_count(session, headers, category_id, filters):
    page = search_category_products(session, headers, category_id, 1, 0, filters)
    return int(page["pagination"]["totalCount"])


def replace_price_filter(filters, min_price, max_price):
    filtered = [flt for flt in filters if flt.get("id") != PRICE_FILTER_ID]
    filtered.append(
        {
            "id": PRICE_FILTER_ID,
            "type": "range",
            "range": {"min": int(min_price), "max": int(max_price)},
        }
    )
    return filtered


def get_price_bounds(session, headers, category_id, filters):
    data = fetch_category_filters(session, headers, category_id, filters)
    candidates = data.get("fastFilters") or data.get("filters") or []
    for candidate in candidates:
        if candidate.get("id") == PRICE_FILTER_ID and candidate.get("type") == "range":
            return int(candidate["minValue"]), int(candidate["maxValue"])
    return None


def plan_query_segments(session, headers, category_id, filters, depth=0, max_depth=20):
    total_count = get_total_count(session, headers, category_id, filters)
    if total_count == 0:
        return []
    if total_count <= MAX_ACCESSIBLE_PRODUCTS:
        return [(filters, total_count)]
    if depth >= max_depth:
        return [(filters, total_count)]

    bounds = get_price_bounds(session, headers, category_id, filters)
    if not bounds:
        return [(filters, total_count)]

    min_price, max_price = bounds
    if min_price >= max_price:
        return [(filters, total_count)]

    mid = (min_price + max_price) // 2
    left_filters = replace_price_filter(filters, min_price, mid)
    right_filters = replace_price_filter(filters, mid + 1, max_price)

    left = plan_query_segments(session, headers, category_id, left_filters, depth + 1, max_depth)
    right = plan_query_segments(session, headers, category_id, right_filters, depth + 1, max_depth)
    return left + right


def load_checkpoint(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None

    sellers = {
        int(row["id"]): {
            "id": int(row["id"]),
            "title": row["title"],
            "link": row.get("link"),
        }
        for row in data.get("sellers", [])
    }
    seller_counts = Counter(
        {int(row["id"]): int(row.get("products_seen", 0)) for row in data.get("sellers", [])}
    )
    return {
        "visited_products": int(data.get("visited_products", 0)),
        "truncated_segments": list(data.get("truncated_segments", [])),
        "completed_leaf_category_ids": set(data.get("completed_leaf_category_ids", [])),
        "sellers": sellers,
        "seller_counts": seller_counts,
        "leaf_category_stats": {
            int(row["category_id"]): row for row in data.get("leaf_category_stats", [])
        },
    }


def collect_sellers_for_category(
    session,
    category_id,
    page_size,
    sleep_seconds,
    progress=False,
    checkpoint_path=None,
):
    headers = build_mm_headers()
    root = find_category(fetch_root_categories(session), category_id)
    if not root:
        raise ValueError(f"Category {category_id} not found in root categories")

    leaf_categories = []
    collect_leaf_categories(root, leaf_categories)

    checkpoint = load_checkpoint(checkpoint_path) if checkpoint_path else None
    sellers = checkpoint["sellers"] if checkpoint else {}
    seller_counts = checkpoint["seller_counts"] if checkpoint else Counter()
    visited_products = checkpoint["visited_products"] if checkpoint else 0
    truncated_segments = checkpoint["truncated_segments"] if checkpoint else []
    leaf_category_stats = checkpoint["leaf_category_stats"] if checkpoint else {}
    completed_leaf_category_ids = (
        checkpoint["completed_leaf_category_ids"] if checkpoint else set()
    )

    for index, leaf in enumerate(leaf_categories, start=1):
        if leaf["id"] in completed_leaf_category_ids:
            if progress:
                print(
                    f"[{index}/{len(leaf_categories)}] {leaf['title']} ({leaf['id']}) skipped",
                    file=sys.stderr,
                )
            continue
        if progress:
            print(
                f"[{index}/{len(leaf_categories)}] {leaf['title']} ({leaf['id']})",
                file=sys.stderr,
            )
        leaf_prices = []
        leaf_orders = 0
        leaf_products_seen = 0
        segments = plan_query_segments(session, headers, leaf["id"], [])
        if progress and len(segments) > 1:
            print(f"  split into {len(segments)} price segments", file=sys.stderr)

        for filters, expected_count in segments:
            if expected_count > MAX_ACCESSIBLE_PRODUCTS:
                truncated_segments.append(
                    {
                        "category_id": leaf["id"],
                        "category_title": leaf["title"],
                        "filters": filters,
                        "expected_count": expected_count,
                    }
                )

            offset = 0
            while True:
                page = search_category_products(
                    session, headers, leaf["id"], page_size, offset, filters
                )
                items = page.get("items", [])
                pagination = page.get("pagination") or {}

                if not items:
                    break

                for item in items:
                    visited_products += 1
                    leaf_products_seen += 1
                    seller_id = int(item["storeCode"])
                    seller_counts[seller_id] += 1
                    price_rub = round((item.get("price") or 0) / 100, 2)
                    if price_rub > 0:
                        leaf_prices.append(price_rub)
                    leaf_orders += int(item.get("orders") or 0)
                    if seller_id not in sellers:
                        seller = fetch_seller_from_product(session, item["productId"])
                        sellers[seller_id] = {
                            "id": seller["id"],
                            "title": seller["title"],
                            "link": seller.get("link"),
                        }
                        if progress:
                            print(
                                f"  new seller: {seller['title']} ({seller['id']})",
                                file=sys.stderr,
                            )

                offset += len(items)
                if (
                    not pagination.get("hasMore")
                    or offset >= pagination.get("totalCount", 0)
                    or offset > MAX_OFFSET
                ):
                    break
                if sleep_seconds:
                    time.sleep(sleep_seconds)

        leaf_category_stats[leaf["id"]] = {
            "category_id": leaf["id"],
            "category_title": leaf["title"],
            "products_seen": leaf_products_seen,
            "orders_sum": leaf_orders,
            "avg_price": round(sum(leaf_prices) / len(leaf_prices), 2) if leaf_prices else 0.0,
            "median_price": round(statistics.median(leaf_prices), 2) if leaf_prices else 0.0,
            "min_price": round(min(leaf_prices), 2) if leaf_prices else 0.0,
            "max_price": round(max(leaf_prices), 2) if leaf_prices else 0.0,
        }
        completed_leaf_category_ids.add(leaf["id"])
        if checkpoint_path:
            write_output(
                checkpoint_path,
                {
                    "root_category": {"id": root["id"], "title": root["title"]},
                    "leaf_categories": leaf_categories,
                    "visited_products": visited_products,
                    "sellers": sellers,
                    "seller_counts": seller_counts,
                    "leaf_category_stats": leaf_category_stats,
                    "truncated_segments": truncated_segments,
                    "completed_leaf_category_ids": sorted(completed_leaf_category_ids),
                },
            )

    return {
        "root_category": {"id": root["id"], "title": root["title"]},
        "leaf_categories": leaf_categories,
        "visited_products": visited_products,
        "sellers": sellers,
        "seller_counts": seller_counts,
        "leaf_category_stats": leaf_category_stats,
        "truncated_segments": truncated_segments,
        "completed_leaf_category_ids": sorted(completed_leaf_category_ids),
    }


def write_output(path, result):
    rows = []
    for seller_id, count in result["seller_counts"].most_common():
        seller = result["sellers"][seller_id]
        rows.append(
            {
                "id": seller["id"],
                "title": seller["title"],
                "link": seller["link"],
                "products_seen": count,
            }
        )
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "category": result["root_category"],
                "leaf_categories_count": len(result["leaf_categories"]),
                "visited_products": result["visited_products"],
                "truncated_segments": result["truncated_segments"],
                "completed_leaf_category_ids": result.get("completed_leaf_category_ids", []),
                "leaf_category_stats": sorted(
                    result.get("leaf_category_stats", {}).values(),
                    key=lambda row: row.get("orders_sum", 0),
                    reverse=True,
                ),
                "sellers": rows,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Collect unique sellers across all leaf subcategories of an MM category."
    )
    parser.add_argument("--category-id", type=int, default=DEFAULT_CATEGORY_ID)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--output", default="/home/user/mm_sellers_10162.json")
    parser.add_argument("--progress", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    with create_session() as session:
        result = collect_sellers_for_category(
            session=session,
            category_id=args.category_id,
            page_size=args.page_size,
            sleep_seconds=args.sleep,
            progress=args.progress,
            checkpoint_path=args.output,
        )

    write_output(args.output, result)

    print(
        f"Category: {result['root_category']['title']} ({result['root_category']['id']})"
    )
    print(f"Leaf categories: {len(result['leaf_categories'])}")
    print(f"Visited products: {result['visited_products']}")
    print(f"Unique sellers: {len(result['sellers'])}")
    print(f"Saved: {args.output}")
    if result["truncated_segments"]:
        print(f"Truncated segments: {len(result['truncated_segments'])}")
    print("")
    print("### SELLERS ###")
    for seller_id, count in result["seller_counts"].most_common():
        seller = result["sellers"][seller_id]
        suffix = f", slug: {seller['link']}" if seller.get("link") else ""
        print(
            f"- {seller['title']} (ID: {seller_id}, products seen: {count}{suffix})"
        )


if __name__ == "__main__":
    main()
