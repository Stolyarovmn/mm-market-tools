#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import requests

from core.auth import bearer_headers
from core.http_client import build_mm_public_headers, create_session, request_json


ROOT_CATEGORIES_URL = "https://api.kazanexpress.ru/api/category/v2/root-categories"
SEARCH_URL = "https://web-api.mm.ru/v2/goods/search"
FILTERS_URL = "https://web-api.mm.ru/v1/goods/filters"
PRODUCT_URL = "https://api.kazanexpress.ru/api/v2/product/{product_id}"
SELLER_PRODUCTS_URL = (
    "https://api.business.kazanexpress.ru/api/seller/shop/{shop_id}/product/getProducts"
)
DEFAULT_CATEGORY_ID = 10162
DEFAULT_MY_SHOP_ID = 98
DEFAULT_TOP_SELLERS_JSON = "/home/user/mm_sellers_10162.json"
DEFAULT_REPORT_DIR = "/home/user/mm-market-tools/reports"
DEFAULT_MY_PRODUCTS_CSV = "/home/user/mm-market-tools/reports/my_shop_top_products.csv"
DEFAULT_SORT = {"type": "popularity", "order": "desc"}
DEFAULT_PAGE_SIZE = 50
DEFAULT_REPORT_PREFIX = f"top10_overlap_report_{dt.date.today().isoformat()}"
MAX_OFFSET = 1000
MAX_ACCESSIBLE_PRODUCTS = MAX_OFFSET + DEFAULT_PAGE_SIZE
PRICE_FILTER_ID = "0"
STOPWORDS = {
    "для",
    "и",
    "с",
    "в",
    "на",
    "по",
    "из",
    "игра",
    "игрушка",
    "игрушки",
    "детские",
    "детский",
    "набор",
    "развивающая",
    "развивающий",
    "магнитная",
    "детям",
    "малышей",
}


def mm_headers():
    return build_mm_public_headers()


def seller_headers(token):
    return bearer_headers(token)


def fetch_json(session, method, url, **kwargs):
    return request_json(session, method, url, timeout=20, **kwargs)


def fetch_root_categories(session):
    return fetch_json(session, "GET", ROOT_CATEGORIES_URL)["payload"]


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


def make_term_search_payload(category_id, term, limit):
    return {
        "term": term,
        "pagination": {"limit": limit, "offset": 0},
        "sort": DEFAULT_SORT,
        "filters": [],
        "storeCode": "000",
        "categories": [category_id],
        "token": "",
        "correctQuery": True,
        "catalogType": "4",
        "storeType": "market",
    }


def search_category_products(session, headers, category_id, limit, offset, filters):
    return fetch_json(
        session,
        "POST",
        SEARCH_URL,
        headers=headers,
        json=make_search_payload(category_id, limit, offset, filters),
    )


def search_by_term(session, headers, category_id, term, limit=20):
    return fetch_json(
        session,
        "POST",
        SEARCH_URL,
        headers=headers,
        json=make_term_search_payload(category_id, term, limit),
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
    return fetch_json(session, "POST", FILTERS_URL, headers=headers, json=payload)


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
    left = plan_query_segments(
        session,
        headers,
        category_id,
        replace_price_filter(filters, min_price, mid),
        depth + 1,
        max_depth,
    )
    right = plan_query_segments(
        session,
        headers,
        category_id,
        replace_price_filter(filters, mid + 1, max_price),
        depth + 1,
        max_depth,
    )
    return left + right


def tokenize(text):
    text = re.sub(r"[^a-zA-Zа-яА-Я0-9 ]+", " ", (text or "").lower())
    return [part for part in text.split() if len(part) > 2 and part not in STOPWORDS]


def normalize_title(text):
    return " ".join(tokenize(text))


def build_search_term(title, max_tokens=6):
    return " ".join(tokenize(title)[:max_tokens])


def title_similarity(a, b):
    sa = set(tokenize(a))
    sb = set(tokenize(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def fetch_public_product(session, product_id):
    data = fetch_json(session, "GET", PRODUCT_URL.format(product_id=product_id))
    payload = data.get("payload") or {}
    public = payload.get("data")
    if not public:
        raise RuntimeError(f"Public product {product_id} is unavailable")
    return public


def public_metrics(public_product):
    description = public_product.get("description") or ""
    return {
        "title": public_product.get("title"),
        "seller_id": public_product.get("seller", {}).get("id"),
        "seller_title": public_product.get("seller", {}).get("title"),
        "orders": public_product.get("ordersAmount", 0),
        "rating": public_product.get("rating", 0),
        "reviews": public_product.get("reviewsAmount", 0),
        "price": (
            ((public_product.get("skuList") or [{}])[0].get("fullPrice"))
            if public_product.get("skuList")
            else None
        ),
        "description_chars": len(re.sub(r"<[^>]+>", " ", description)),
        "photo_count": len(public_product.get("photos") or []),
        "attribute_count": len(public_product.get("attributes") or []),
        "characteristic_count": len(public_product.get("characteristics") or []),
    }


def fetch_my_products(session, token, shop_id):
    products = []
    for page in range(30):
        url = SELLER_PRODUCTS_URL.format(shop_id=shop_id)
        data = fetch_json(
            session,
            "GET",
            f"{url}?size=100&page={page}&sortBy=id&order=descending",
            headers=seller_headers(token),
        )
        items = data.get("productList") or []
        if not items:
            break
        products.extend(items)
    return products


def load_my_products_from_csv(path):
    products = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            products.append(
                {
                    "productId": int(row["product_id"]),
                    "title": row["title"],
                    "price": float(row["price"] or 0),
                    "quantitySold": int(float(row["sold"] or 0)),
                    "rating": float(row["rating"] or 0),
                    "feedbacksAmount": 0,
                    "active": int(float(row["active"] or 0)),
                }
            )
    return products


def build_my_index(products):
    exact = {}
    fuzzy = []
    for product in products:
        title = product.get("title") or ""
        key = normalize_title(title)
        row = {
            "product_id": int(product.get("productId")),
            "title": title,
            "price": product.get("price"),
            "orders": product.get("quantitySold", 0),
            "rating": float(product.get("rating") or 0),
            "reviews": int(product.get("feedbacksAmount") or 0),
            "active": int(product.get("active") or 0),
            "normalized_title": key,
        }
        if key:
            exact[key] = row
            fuzzy.append(row)
    return exact, fuzzy


def load_top_sellers(path, top_n, my_shop_id):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    sellers = sorted(data["sellers"], key=lambda s: s.get("products_seen", 0), reverse=True)
    return [row for row in sellers if int(row["id"]) != my_shop_id][:top_n]


def load_selected_sellers(path, seller_ids, my_shop_id):
    wanted = {int(seller_id) for seller_id in seller_ids if int(seller_id) != my_shop_id}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    sellers = {int(row["id"]): row for row in data["sellers"]}
    return [sellers[seller_id] for seller_id in wanted if seller_id in sellers]


def collect_target_products(session, category_id, seller_ids, sleep_seconds):
    headers = mm_headers()
    root = fetch_root_categories(session)
    category = find_category(root, category_id)
    if not category:
        raise RuntimeError(f"Category {category_id} not found")
    leaves = []
    collect_leaf_categories(category, leaves)

    products = {}
    for leaf in leaves:
        segments = plan_query_segments(session, headers, int(leaf["id"]), [])
        for filters, total_count in segments:
            for offset in range(0, total_count, DEFAULT_PAGE_SIZE):
                page = search_category_products(
                    session,
                    headers,
                    int(leaf["id"]),
                    DEFAULT_PAGE_SIZE,
                    offset,
                    filters,
                )
                for item in page.get("items") or []:
                    seller_id = int(item.get("storeCode") or 0)
                    if seller_id not in seller_ids:
                        continue
                    product_id = int(item.get("productId") or item.get("id"))
                    products[product_id] = {
                        "product_id": product_id,
                        "seller_id": seller_id,
                        "title": item.get("name") or "",
                        "price": (item.get("price") or 0) / 100,
                        "orders": int(item.get("orders") or 0),
                        "rating": float((item.get("ratings") or {}).get("rating") or 0),
                        "reviews": int((item.get("ratings") or {}).get("commentsCount") or 0),
                        "quantity": int(item.get("quantity") or 0),
                        "leaf_category_id": int(leaf["id"]),
                        "normalized_title": normalize_title(item.get("name") or ""),
                    }
                if sleep_seconds:
                    time.sleep(sleep_seconds)
    return list(products.values())


def collect_target_products_by_my_titles(
    session,
    category_id,
    seller_ids,
    my_products,
    sleep_seconds,
):
    headers = mm_headers()
    products = {}
    for product in my_products:
        term = build_search_term(product.get("title") or "")
        if not term:
            continue
        page = search_by_term(session, headers, category_id, term, limit=30)
        for item in page.get("items") or []:
            seller_id = int(item.get("storeCode") or 0)
            if seller_id not in seller_ids:
                continue
            product_id = int(item.get("productId") or item.get("id"))
            products[product_id] = {
                "product_id": product_id,
                "seller_id": seller_id,
                "title": item.get("name") or "",
                "price": (item.get("price") or 0) / 100,
                "orders": int(item.get("orders") or 0),
                "rating": float((item.get("ratings") or {}).get("rating") or 0),
                "reviews": int((item.get("ratings") or {}).get("commentsCount") or 0),
                "quantity": int(item.get("quantity") or 0),
                "normalized_title": normalize_title(item.get("name") or ""),
            }
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return list(products.values())


def find_best_my_match(comp, my_exact, my_rows, min_similarity):
    exact = my_exact.get(comp["normalized_title"])
    if exact:
        return exact, 1.0
    best = None
    best_score = 0.0
    for row in my_rows:
        score = title_similarity(comp["title"], row["title"])
        if score > best_score:
            best = row
            best_score = score
    if best_score >= min_similarity:
        return best, round(best_score, 3)
    return None, best_score


def compare_overlaps(session, my_products, competitor_products, top_sellers, min_similarity):
    seller_lookup = {int(row["id"]): row for row in top_sellers}
    my_exact, my_rows = build_my_index(my_products)
    overlaps = defaultdict(list)

    for comp in competitor_products:
        my_match, score = find_best_my_match(comp, my_exact, my_rows, min_similarity)
        if not my_match:
            continue
        public = fetch_public_product(session, comp["product_id"])
        comp_metrics = public_metrics(public)
        overlaps[comp["seller_id"]].append(
            {
                "similarity": score,
                "my": my_match,
                "competitor": {
                    **comp,
                    **comp_metrics,
                },
            }
        )

    report = []
    for seller_id, rows in overlaps.items():
        rows.sort(
            key=lambda row: (
                row["similarity"],
                row["competitor"].get("orders", 0) + row["my"].get("orders", 0),
            ),
            reverse=True,
        )
        seller = seller_lookup[seller_id]
        report.append(
            {
                "seller_id": seller_id,
                "seller_title": seller.get("title"),
                "seller_slug": seller.get("link"),
                "products_seen": seller.get("products_seen"),
                "overlap_count": len(rows),
                "overlaps": rows[:20],
            }
        )
    report.sort(key=lambda row: row["overlap_count"], reverse=True)
    return report


def write_markdown(report, path):
    lines = [
        "# Пересечения с топ-10 продавцов",
        "",
        "Сравнение ваших товаров с товарами топ-10 продавцов категории по нормализованным названиям внутри категории.",
        "",
    ]
    for seller in report:
        lines.append(f"## {seller['seller_title']} ({seller['seller_id']})")
        lines.append("")
        lines.append(f"- slug: `{seller['seller_slug']}`")
        lines.append(f"- товаров в категории: `{seller['products_seen']}`")
        lines.append(f"- найдено пересечений: `{seller['overlap_count']}`")
        lines.append("")
        for row in seller["overlaps"][:10]:
            my_row = row["my"]
            comp = row["competitor"]
            lines.append(f"### {my_row['title']}")
            lines.append(f"- similarity: `{row['similarity']}`")
            lines.append(
                f"- вы: `{my_row['orders']}` продаж, `{my_row['price']} ₽`, рейтинг `{my_row['rating']}`, отзывов `{my_row['reviews']}`"
            )
            lines.append(
                f"- конкурент: `{comp['title']}` | `{comp['orders']}` продаж, `{comp['price']} ₽`, рейтинг `{comp['rating']}`, отзывов `{comp['reviews']}`"
            )
            lines.append(
                f"- карточка: у вас фото `{my_row.get('photo_count', 'n/a')}`, у конкурента `{comp['photo_count']}`; атрибуты `{my_row.get('attribute_count', 'n/a')}` / `{comp['attribute_count']}`; характеристики `{my_row.get('characteristic_count', 'n/a')}` / `{comp['characteristic_count']}`"
            )
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def enrich_my_public_metrics(session, my_products):
    enriched = []
    for product in my_products:
        row = dict(product)
        try:
            public = fetch_public_product(session, int(product["productId"]))
        except Exception:
            row["photo_count"] = 0
            row["attribute_count"] = 0
            row["characteristic_count"] = 0
            enriched.append(row)
            continue
        row["photo_count"] = len(public.get("photos") or [])
        row["attribute_count"] = len(public.get("attributes") or [])
        row["characteristic_count"] = len(public.get("characteristics") or [])
        enriched.append(row)
    return enriched


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare your products with overlaps from top category sellers."
    )
    parser.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    parser.add_argument("--my-shop-id", type=int, default=DEFAULT_MY_SHOP_ID)
    parser.add_argument("--category-id", type=int, default=DEFAULT_CATEGORY_ID)
    parser.add_argument("--top-sellers-json", default=DEFAULT_TOP_SELLERS_JSON)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--my-products-csv", default=DEFAULT_MY_PRODUCTS_CSV)
    parser.add_argument("--sample-size", type=int, default=120)
    parser.add_argument("--min-similarity", type=float, default=0.55)
    parser.add_argument("--seller-ids", nargs="*", type=int)
    parser.add_argument("--report-prefix", default=DEFAULT_REPORT_PREFIX)
    return parser.parse_args()


def main():
    args = parse_args()

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    with create_session() as session:
        if args.seller_ids:
            top_sellers = load_selected_sellers(
                args.top_sellers_json,
                args.seller_ids,
                args.my_shop_id,
            )
        else:
            top_sellers = load_top_sellers(args.top_sellers_json, args.top_n, args.my_shop_id)
        if args.token:
            try:
                my_products = fetch_my_products(session, args.token, args.my_shop_id)
            except requests.HTTPError as exc:
                if exc.response is None or exc.response.status_code != 401:
                    raise
                my_products = load_my_products_from_csv(args.my_products_csv)
        else:
            my_products = load_my_products_from_csv(args.my_products_csv)
        my_products = enrich_my_public_metrics(session, my_products)
        my_products.sort(key=lambda row: row.get("quantitySold", 0), reverse=True)
        source_products = my_products[: args.sample_size]
        competitor_products = collect_target_products_by_my_titles(
            session,
            args.category_id,
            {int(row["id"]) for row in top_sellers},
            source_products,
            args.sleep_seconds,
        )
        report = compare_overlaps(
            session,
            source_products,
            competitor_products,
            top_sellers,
            args.min_similarity,
        )

    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    csv_path = report_dir / f"{args.report_prefix}.csv"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "seller_id",
                "seller_title",
                "similarity",
                "my_product_id",
                "my_title",
                "my_orders",
                "my_price",
                "competitor_product_id",
                "competitor_title",
                "competitor_orders",
                "competitor_price",
            ]
        )
        for seller in report:
            for row in seller["overlaps"]:
                writer.writerow(
                    [
                        seller["seller_id"],
                        seller["seller_title"],
                        row["similarity"],
                        row["my"]["product_id"],
                        row["my"]["title"],
                        row["my"]["orders"],
                        row["my"]["price"],
                        row["competitor"]["product_id"],
                        row["competitor"]["title"],
                        row["competitor"]["orders"],
                        row["competitor"]["price"],
                    ]
                )

    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
