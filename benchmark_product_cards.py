#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import html
import json
import os
import re
import urllib.parse
from collections import Counter
from pathlib import Path

from core.auth import bearer_headers
from core.http_client import build_mm_public_headers, create_session, request_json
from core.paths import REPORTS_DIR


MM_SEARCH_URL = "https://web-api.mm.ru/v2/goods/search"
KE_PRODUCT_URL = "https://api.kazanexpress.ru/api/v2/product/{product_id}"
SELLER_PRODUCTS_URL = (
    "https://api.business.kazanexpress.ru/api/seller/shop/{shop_id}/product/getProducts"
)
DEFAULT_CATEGORY_ID = 10162
DEFAULT_REPORT_DIR = str(REPORTS_DIR)
DEFAULT_MY_PRODUCTS_CSV = str(REPORTS_DIR / "my_shop_top_products.csv")
DEFAULT_REPORT_PREFIX = f"product_card_benchmark_{dt.date.today().isoformat()}"
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
    return build_mm_public_headers(device_id="mm-market-tools-card-benchmark")


def fetch_json(session, method, url, **kwargs):
    return request_json(session, method, url, timeout=20, **kwargs)


def seller_headers(token):
    return bearer_headers(token)


def fetch_my_products(session, token, shop_id, pages):
    products = []
    for page in range(pages):
        url = SELLER_PRODUCTS_URL.format(shop_id=shop_id) + "?" + urllib.parse.urlencode(
            {"size": 100, "page": page, "sortBy": "id", "order": "descending"}
        )
        data = fetch_json(session, "GET", url, headers=seller_headers(token))
        items = data.get("productList") or []
        if not items:
            break
        products.extend(items)
    return products


def fetch_public_product(session, product_id):
    return fetch_json(session, "GET", KE_PRODUCT_URL.format(product_id=product_id))["payload"][
        "data"
    ]


def load_products_from_csv(path):
    products = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            product_id = int(row["product_id"])
            products.append(
                {
                    "productId": product_id,
                    "title": row["title"],
                    "quantitySold": int(float(row["sold"] or 0)),
                    "price": float(row["price"] or 0),
                    "rating": float(row["rating"] or 0),
                    "feedbacksAmount": 0,
                    "active": int(float(row.get("active") or 0)),
                }
            )
    return products


def tokenize(text):
    text = re.sub(r"[^a-zA-Zа-яА-Я0-9 ]+", " ", text.lower())
    tokens = [token for token in text.split() if len(token) > 2 and token not in STOPWORDS]
    return tokens


def build_search_term(title, max_tokens=5):
    counts = Counter(tokenize(title))
    return " ".join([token for token, _ in counts.most_common(max_tokens)])


def search_similar_products(session, term, category_id, limit=30):
    payload = {
        "term": term,
        "pagination": {"limit": limit, "offset": 0},
        "sort": {"type": "popularity", "order": "desc"},
        "filters": [],
        "storeCode": "000",
        "categories": [category_id],
        "token": "",
        "correctQuery": True,
        "catalogType": "4",
        "storeType": "market",
    }
    return fetch_json(session, "POST", MM_SEARCH_URL, headers=mm_headers(), json=payload)


def similarity_score(a_title, b_title):
    a = set(tokenize(a_title))
    b = set(tokenize(b_title))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def strip_html(raw_html):
    cleaned = re.sub(r"<[^>]+>", " ", raw_html or "")
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def card_metrics(public_product):
    description_text = strip_html(public_product.get("description", ""))
    photos = public_product.get("photos") or []
    attrs = public_product.get("attributes") or []
    chars = public_product.get("characteristics") or []
    return {
        "title": public_product.get("title"),
        "seller_id": public_product.get("seller", {}).get("id"),
        "seller_title": public_product.get("seller", {}).get("title"),
        "orders": public_product.get("ordersAmount", 0),
        "rating": public_product.get("rating", 0),
        "reviews": public_product.get("reviewsAmount", 0),
        "description_chars": len(description_text),
        "description_words": len(description_text.split()),
        "photo_count": len(photos),
        "attribute_count": len(attrs),
        "characteristic_count": len(chars),
        "title_chars": len(public_product.get("title", "")),
    }


def choose_comparables(session, my_product, category_id, my_shop_id, max_comparables):
    term = build_search_term(my_product.get("title", ""))
    search = search_similar_products(session, term, category_id)
    candidates = []
    for item in search.get("items", []):
        store_code = int(item.get("storeCode") or 0)
        if store_code == my_shop_id:
            continue
        public_product = fetch_public_product(session, item["productId"])
        score = similarity_score(my_product.get("title", ""), public_product.get("title", ""))
        if score < 0.18:
            continue
        metrics = card_metrics(public_product)
        metrics["product_id"] = item["productId"]
        metrics["price"] = item.get("price")
        metrics["similarity"] = round(score, 3)
        candidates.append(metrics)
    candidates.sort(key=lambda row: (row["similarity"], row["orders"], row["reviews"]), reverse=True)
    return term, candidates[:max_comparables]


def my_metrics(product, shop_title):
    title = product.get("title", "")
    return {
        "product_id": product.get("productId"),
        "title": title,
        "seller_id": product.get("shopId", 98),
        "seller_title": shop_title,
        "orders": product.get("quantitySold", 0),
        "rating": float(product.get("rating") or 0),
        "reviews": product.get("feedbacksAmount") or 0,
        "description_chars": len(strip_html(product.get("description", ""))),
        "description_words": len(strip_html(product.get("description", "")).split()),
        "photo_count": len(product.get("photos") or []),
        "attribute_count": len(product.get("attributes") or []),
        "characteristic_count": len(product.get("characteristics") or []),
        "title_chars": len(title),
        "price": product.get("price"),
    }


def enrich_from_public_card(product, public_product):
    merged = dict(product)
    merged["description"] = public_product.get("description", "")
    merged["photos"] = public_product.get("photos") or []
    merged["attributes"] = public_product.get("attributes") or []
    merged["characteristics"] = public_product.get("characteristics") or []
    merged["feedbacksAmount"] = (
        merged.get("feedbacksAmount")
        or public_product.get("reviewsAmount")
        or 0
    )
    merged["shopId"] = (
        merged.get("shopId")
        or public_product.get("seller", {}).get("id")
        or 98
    )
    merged["title"] = merged.get("title") or public_product.get("title")
    if not merged.get("rating"):
        merged["rating"] = public_product.get("rating") or 0
    return merged


def render_markdown(results, path):
    lines = [
        "# Сравнение карточек товара",
        "",
        "Цель: понять, как заполненность карточек похожих товаров у лидеров категории соотносится с продажами и где улучшать текущие карточки магазина.",
        "",
    ]
    for result in results:
        lines.append(f"## Ваш товар: {result['my']['title']}")
        lines.append("")
        lines.append(f"- `product_id`: {result['my']['product_id']}")
        lines.append(f"- продажи: {result['my']['orders']}")
        lines.append(f"- цена: {result['my']['price']}")
        lines.append(f"- рейтинг: {result['my']['rating']}")
        lines.append(f"- отзывов: {result['my']['reviews']}")
        lines.append(f"- длина заголовка: {result['my']['title_chars']}")
        lines.append(f"- длина описания: {result['my']['description_chars']} символов")
        lines.append(f"- фото: {result['my']['photo_count']}")
        lines.append(f"- атрибуты: {result['my']['attribute_count']}")
        lines.append(f"- характеристики: {result['my']['characteristic_count']}")
        lines.append(f"- поисковый запрос для подбора аналогов: `{result['term']}`")
        lines.append("")
        for idx, comp in enumerate(result["comparables"], start=1):
            lines.append(f"### Аналог {idx}: {comp['title']}")
            lines.append(f"- продавец: {comp['seller_title']} ({comp['seller_id']})")
            lines.append(f"- similarity: {comp['similarity']}")
            lines.append(f"- продажи: {comp['orders']}")
            lines.append(f"- цена: {comp['price']}")
            lines.append(f"- рейтинг: {comp['rating']}")
            lines.append(f"- отзывов: {comp['reviews']}")
            lines.append(f"- длина заголовка: {comp['title_chars']}")
            lines.append(f"- длина описания: {comp['description_chars']} символов")
            lines.append(f"- фото: {comp['photo_count']}")
            lines.append(f"- атрибуты: {comp['attribute_count']}")
            lines.append(f"- характеристики: {comp['characteristic_count']}")
            lines.append("")
        lines.append("### Вывод")
        lines.append(result["conclusion"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def make_conclusion(my_row, comparables):
    if not comparables:
        return "Похожих публичных карточек с достаточной схожестью не найдено."
    best = comparables[0]
    notes = []
    if best["orders"] > my_row["orders"]:
        notes.append(
            f"у лучшего аналога продажи выше ({best['orders']} против {my_row['orders']})"
        )
    if best["description_chars"] > my_row["description_chars"]:
        notes.append("у аналога подробнее описание")
    if best["photo_count"] > my_row["photo_count"]:
        notes.append("у аналога больше фото")
    if best["attribute_count"] > my_row["attribute_count"]:
        notes.append("у аналога больше заполненных атрибутов")
    if best["characteristic_count"] > my_row["characteristic_count"]:
        notes.append("у аналога больше характеристик")
    if best["rating"] >= my_row["rating"] and best["reviews"] > my_row["reviews"]:
        notes.append("у аналога сильнее социальное доказательство: рейтинг/отзывы")
    if best["price"] is not None and my_row["price"] is not None and best["price"] <= my_row["price"]:
        notes.append("аналог не дороже вашего товара")
    if not notes:
        notes.append("карточка не слабее лучших аналогов по базовым метрикам")
    return "; ".join(notes) + "."


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark your product cards against similar public listings."
    )
    parser.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    parser.add_argument("--my-shop-id", type=int, default=int(os.getenv("MM_MY_SHOP_ID", "98")))
    parser.add_argument("--category-id", type=int, default=DEFAULT_CATEGORY_ID)
    parser.add_argument("--pages", type=int, default=12)
    parser.add_argument("--sample-size", type=int, default=4)
    parser.add_argument("--comparables", type=int, default=3)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--my-products-csv", default=DEFAULT_MY_PRODUCTS_CSV)
    parser.add_argument("--report-prefix", default=DEFAULT_REPORT_PREFIX)
    return parser.parse_args()


def main():
    args = parse_args()

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    with create_session() as session:
        if args.token:
            products = fetch_my_products(session, args.token, args.my_shop_id, args.pages)
        else:
            products = load_products_from_csv(args.my_products_csv)
        products.sort(key=lambda p: p.get("quantitySold", 0), reverse=True)
        chosen = products[: args.sample_size]
        results = []
        for product in chosen:
            public_product = fetch_public_product(session, product["productId"])
            product = enrich_from_public_card(product, public_product)
            term, comparables = choose_comparables(
                session,
                product,
                args.category_id,
                args.my_shop_id,
                args.comparables,
            )
            my_row = my_metrics(product, "Магазин детских развивающих игрушек")
            conclusion = make_conclusion(my_row, comparables)
            results.append(
                {
                    "term": term,
                    "my": my_row,
                    "comparables": comparables,
                    "conclusion": conclusion,
                }
            )

    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    render_markdown(results, md_path)

    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
