#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from core.http_client import build_mm_public_headers, create_session, request_json
from core.market_analysis import classify_group, idea_fingerprint
from core.paths import REPORTS_DIR


SEARCH_URL = "https://web-api.mm.ru/v2/goods/search"
PRODUCT_URL = "https://api.kazanexpress.ru/api/v2/product/{product_id}"
DEFAULT_CATEGORY_ID = 10162
DEFAULT_REPORT_DIR = str(REPORTS_DIR)
DEFAULT_MY_PRODUCTS_CSV = str(REPORTS_DIR / "my_shop_top_products.csv")
DEFAULT_TOP_SELLERS_JSON = str(REPORTS_DIR / "mm_sellers_10162.json")
DEFAULT_DATE = dt.date.today().isoformat()
DEFAULT_REAL_COMPETITORS = [16685, 40319, 28064, 16100, 17382, 36530]
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
    "шт",
    "см",
}
def mm_headers():
    return build_mm_public_headers()


def fetch_json(session, method, url, **kwargs):
    return request_json(session, method, url, timeout=20, **kwargs)


def load_my_products(path):
    products = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            products.append(
                {
                    "rank": int(row["rank"]),
                    "product_id": int(row["product_id"]),
                    "title": row["title"],
                    "sold": int(float(row["sold"] or 0)),
                    "price": float(row["price"] or 0),
                    "active": int(float(row["active"] or 0)),
                    "rating": float(row["rating"] or 0),
                }
            )
    return products


def tokenize(text):
    normalized = re.sub(r"[^a-zA-Zа-яА-Я0-9 ]+", " ", (text or "").lower())
    return [token for token in normalized.split() if len(token) > 2 and token not in STOPWORDS]


def similarity_score(a, b):
    left = set(tokenize(a))
    right = set(tokenize(b))
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def assign_groups(products):
    grouped = []
    for product in products:
        row = dict(product)
        row["group"] = classify_group(row["title"])
        row["tokens"] = tokenize(row["title"])
        row["idea_cluster"] = idea_fingerprint(row["title"], row["group"])
        grouped.append(row)
    return grouped


def summarize_groups(products):
    groups = defaultdict(list)
    for product in products:
        groups[product["group"]].append(product)
    summary = []
    for group_name, rows in groups.items():
        rows.sort(key=lambda row: row["sold"], reverse=True)
        summary.append(
            {
                "group": group_name,
                "sku_count": len(rows),
                "sold_sum": sum(row["sold"] for row in rows),
                "avg_price": round(sum(row["price"] for row in rows) / len(rows), 2),
                "top_products": rows[:10],
            }
        )
    summary.sort(key=lambda row: row["sold_sum"], reverse=True)
    return summary


def load_top_sellers(path, top_n, exclude_id):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    sellers = sorted(data["sellers"], key=lambda row: row.get("products_seen", 0), reverse=True)
    return [row for row in sellers if int(row["id"]) != exclude_id][:top_n]


def load_selected_sellers(path, seller_ids, exclude_id):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    lookup = {int(row["id"]): row for row in data["sellers"]}
    return [lookup[sid] for sid in seller_ids if sid != exclude_id and sid in lookup]


def build_search_term(title, max_tokens=5):
    counts = Counter(tokenize(title))
    return " ".join([token for token, _ in counts.most_common(max_tokens)])


def search_products(session, term, category_id, limit=30):
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
    return fetch_json(session, "POST", SEARCH_URL, headers=mm_headers(), json=payload)


def fetch_public_product(session, cache, product_id):
    if product_id in cache:
        return cache[product_id]
    data = fetch_json(session, "GET", PRODUCT_URL.format(product_id=product_id))
    payload = data.get("payload") or {}
    public = payload.get("data")
    cache[product_id] = public
    return public


def idea_competition_report(session, groups, target_sellers, category_id, reps_per_group, min_similarity):
    seller_ids = {int(row["id"]) for row in target_sellers}
    product_cache = {}
    report = []
    for group in groups:
        representatives = group["top_products"][:reps_per_group]
        candidates = {}
        for product in representatives:
            term = build_search_term(product["title"])
            if not term:
                continue
            search = search_products(session, term, category_id)
            for item in search.get("items") or []:
                seller_id = int(item.get("storeCode") or 0)
                if seller_id not in seller_ids:
                    continue
                title = item.get("name") or ""
                score = max(
                    similarity_score(title, my_product["title"])
                    for my_product in representatives
                )
                if score < min_similarity:
                    continue
                product_id = int(item.get("productId") or item.get("id"))
                previous = candidates.get(product_id)
                if previous and previous["similarity"] >= score:
                    continue
                candidates[product_id] = {
                    "product_id": product_id,
                    "seller_id": seller_id,
                    "title": title,
                    "price": (item.get("price") or 0) / 100,
                    "orders": int(item.get("orders") or 0),
                    "rating": float((item.get("ratings") or {}).get("rating") or 0),
                    "reviews": int((item.get("ratings") or {}).get("commentsCount") or 0),
                    "similarity": round(score, 3),
                }

        by_seller = defaultdict(list)
        for candidate in candidates.values():
            public = fetch_public_product(session, product_cache, candidate["product_id"])
            if not public:
                continue
            candidate["photo_count"] = len(public.get("photos") or [])
            candidate["attribute_count"] = len(public.get("attributes") or [])
            candidate["characteristic_count"] = len(public.get("characteristics") or [])
            candidate["seller_title"] = public.get("seller", {}).get("title")
            by_seller[candidate["seller_id"]].append(candidate)

        seller_sections = []
        for seller in target_sellers:
            rows = by_seller.get(int(seller["id"]), [])
            if not rows:
                continue
            rows.sort(key=lambda row: (row["orders"], row["similarity"]), reverse=True)
            seller_sections.append(
                {
                    "seller_id": int(seller["id"]),
                    "seller_title": seller["title"],
                    "seller_slug": seller.get("link"),
                    "matched_items": len(rows),
                    "orders_sum": sum(row["orders"] for row in rows),
                    "avg_price": round(sum(row["price"] for row in rows) / len(rows), 2),
                    "examples": rows[:5],
                }
            )
        seller_sections.sort(key=lambda row: (row["matched_items"], row["orders_sum"]), reverse=True)
        report.append(
            {
                "group": group["group"],
                "my_sku_count": group["sku_count"],
                "my_sold_sum": group["sold_sum"],
                "my_avg_price": group["avg_price"],
                "my_top_products": group["top_products"][:5],
                "competitors": seller_sections,
            }
        )
    return report


def write_group_csv(grouped_products, path):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "product_id", "group", "title", "sold", "price", "active", "rating"])
        for row in grouped_products:
            writer.writerow(
                [
                    row["rank"],
                    row["product_id"],
                    row["group"],
                    row["title"],
                    row["sold"],
                    row["price"],
                    row["active"],
                    row["rating"],
                ]
            )


def write_group_markdown(groups, path):
    lines = ["# Группы товаров", "", "Группировка всего ассортимента магазина по товарным идеям.", ""]
    for group in groups:
        lines.append(f"## {group['group']}")
        lines.append("")
        lines.append(f"- SKU: `{group['sku_count']}`")
        lines.append(f"- суммарные продажи: `{group['sold_sum']}`")
        lines.append(f"- средняя цена: `{group['avg_price']} ₽`")
        lines.append("")
        for product in group["top_products"][:5]:
            lines.append(f"- {product['title']} | sold `{product['sold']}` | price `{product['price']} ₽`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_competition_markdown(title, report, path):
    lines = [f"# {title}", "", "Сравнение по товарным идеям, а не по точному совпадению названий.", ""]
    for group in report:
        lines.append(f"## {group['group']}")
        lines.append("")
        lines.append(
            f"- у вас: `{group['my_sku_count']}` SKU, `{group['my_sold_sum']}` продаж, средняя цена `{group['my_avg_price']} ₽`"
        )
        lines.append("")
        for product in group["my_top_products"]:
            lines.append(f"- ваш топ: {product['title']} | sold `{product['sold']}` | price `{product['price']} ₽`")
        lines.append("")
        if not group["competitors"]:
            lines.append("- похожих товарных идей у выбранных конкурентов не найдено")
            lines.append("")
            continue
        for seller in group["competitors"][:5]:
            lines.append(f"### {seller['seller_title']} ({seller['seller_id']})")
            lines.append(f"- найдено похожих товаров: `{seller['matched_items']}`")
            lines.append(f"- суммарные продажи найденных товаров: `{seller['orders_sum']}`")
            lines.append(f"- средняя цена найденных товаров: `{seller['avg_price']} ₽`")
            for example in seller["examples"][:3]:
                lines.append(
                    f"- пример: {example['title']} | sold `{example['orders']}` | price `{example['price']} ₽` | similarity `{example['similarity']}`"
                )
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Group all your products by idea and compare those groups with competitors."
    )
    parser.add_argument("--category-id", type=int, default=DEFAULT_CATEGORY_ID)
    parser.add_argument("--my-products-csv", default=DEFAULT_MY_PRODUCTS_CSV)
    parser.add_argument("--top-sellers-json", default=DEFAULT_TOP_SELLERS_JSON)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--real-competitors", nargs="*", type=int, default=DEFAULT_REAL_COMPETITORS)
    parser.add_argument("--group-representatives", type=int, default=5)
    parser.add_argument("--min-similarity", type=float, default=0.22)
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    return parser.parse_args()


def main():
    args = parse_args()
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    my_products = load_my_products(args.my_products_csv)
    grouped_products = assign_groups(my_products)
    groups = summarize_groups(grouped_products)
    top10_sellers = load_top_sellers(args.top_sellers_json, args.top_n, 98)
    real_sellers = load_selected_sellers(args.top_sellers_json, args.real_competitors, 98)

    with create_session() as session:
        top10_report = idea_competition_report(
            session,
            groups,
            top10_sellers,
            args.category_id,
            args.group_representatives,
            args.min_similarity,
        )
        real_report = idea_competition_report(
            session,
            groups,
            real_sellers,
            args.category_id,
            args.group_representatives,
            args.min_similarity,
        )

    groups_json = report_dir / f"my_product_groups_{args.date_tag}.json"
    groups_csv = report_dir / f"my_product_groups_{args.date_tag}.csv"
    groups_md = report_dir / f"my_product_groups_{args.date_tag}.md"
    top10_json = report_dir / f"idea_competitor_comparison_top10_{args.date_tag}.json"
    top10_md = report_dir / f"idea_competitor_comparison_top10_{args.date_tag}.md"
    real_json = report_dir / f"idea_competitor_comparison_real_{args.date_tag}.json"
    real_md = report_dir / f"idea_competitor_comparison_real_{args.date_tag}.md"

    groups_json.write_text(json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")
    write_group_csv(grouped_products, groups_csv)
    write_group_markdown(groups, groups_md)
    top10_json.write_text(json.dumps(top10_report, ensure_ascii=False, indent=2), encoding="utf-8")
    real_json.write_text(json.dumps(real_report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_competition_markdown("Сравнение групп с top-10 продавцов", top10_report, top10_md)
    write_competition_markdown("Сравнение групп с реальными ассортиментными конкурентами", real_report, real_md)

    for path in [groups_json, groups_csv, groups_md, top10_json, top10_md, real_json, real_md]:
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
