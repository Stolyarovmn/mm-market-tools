#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import statistics
from collections import defaultdict
from pathlib import Path

from core.http_client import build_mm_public_headers, create_session, request_json
from core.market_analysis import (
    classify_group,
    idea_fingerprint,
    novelty_proxy,
    price_band_label,
    summarize_market as summarize_market_payload,
)
from core.market_dashboard import build_market_dashboard
from core.market_economics import apply_market_margin_fit, load_cogs_override_rows, load_my_group_economics, merge_group_economics
from core.io_utils import write_json
from core.paths import COGS_OVERRIDES_PATH, DASHBOARD_DIR, NORMALIZED_DIR, ensure_dir
from core.market_crosstab import (
    calculate_hhi_by_band,
    build_group_price_band_crosstab,
    identify_coverage_gaps,
    calculate_entry_window_with_novelty_factoring,
    apply_configurable_price_bands,
    add_coverage_gap_to_entry_windows,
)


SEARCH_URL = "https://web-api.mm.ru/v2/goods/search"
DEFAULT_CATEGORY_ID = 10162
DEFAULT_REPORT_DIR = "/home/user/mm-market-tools/reports"
DEFAULT_DATE = dt.date.today().isoformat()
DEFAULT_TOP_SELLERS_JSON = "/home/user/mm_sellers_10162.json"
DEFAULT_MY_PRODUCTS_CSV = "/home/user/mm-market-tools/reports/my_shop_top_products.csv"
DEFAULT_OFFICIAL_REPORT_JSON = "/home/user/mm-market-tools/reports/official_period_analysis_2026-04-08.json"
DEFAULT_PRICE_BAND_BOUNDARIES = [50, 200, 500]  # Results in: 0-50, 50-200, 200-500, 500+

def search_page(session, category_id, limit, offset):
    payload = {
        "term": "",
        "pagination": {"limit": limit, "offset": offset},
        "sort": {"type": "popularity", "order": "desc"},
        "filters": [],
        "storeCode": "000",
        "categories": [category_id],
        "token": "",
        "correctQuery": True,
        "catalogType": "4",
        "storeType": "market",
    }
    return request_json(
        session,
        "POST",
        SEARCH_URL,
        headers=build_mm_public_headers(),
        json_body=payload,
        timeout=30,
    )


def load_seller_lookup(path):
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {int(row["id"]): row for row in data.get("sellers", [])}


def load_my_group_prices(path):
    rows = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            title = row["title"]
            group = classify_group(title)
            rows[group].append(float(row["price"] or 0))
    result = {}
    for group, prices in rows.items():
        result[group] = {
            "my_avg_price": round(sum(prices) / len(prices), 2),
            "my_median_price": round(statistics.median(prices), 2),
            "my_sku_count": len(prices),
        }
    return result


def write_crosstab_csv(path, crosstab_data, hhi_by_band):
    """Write group × price_band cross-tabulation to CSV"""
    groups = sorted(set(row["group"] for row in crosstab_data if row["source"] == "market"))
    bands = sorted(set(row["price_band"] for row in crosstab_data if row["source"] == "market"))
    
    fieldnames = ["group"] + bands + ["hhi_by_band"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        
        for group in groups:
            row_dict = {"group": f"{group} (market)"}
            for band in bands:
                count = next((r["count"] for r in crosstab_data 
                             if r["group"] == group and r["price_band"] == band and r["source"] == "market"), 0)
                row_dict[band] = count
            row_dict["hhi_by_band"] = "-"
            writer.writerow(row_dict)
            
            row_dict = {"group": f"{group} (shop)"}
            for band in bands:
                count = next((r["count"] for r in crosstab_data 
                             if r["group"] == group and r["price_band"] == band and r["source"] == "shop"), 0)
                row_dict[band] = count
            row_dict["hhi_by_band"] = "-"
            writer.writerow(row_dict)
    
    # Write HHI by band separately
    hhi_path = path.parent / f"hhi_by_price_band_{path.stem.split('_')[-1]}.csv"
    with open(hhi_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["price_band", "hhi", "concentration_profile"])
        writer.writeheader()
        for band, hhi in sorted(hhi_by_band.items()):
            if hhi is None:
                profile = "insufficient_data"
            elif hhi >= 2500:
                profile = "high_concentration"
            elif hhi >= 1500:
                profile = "moderate_concentration"
            else:
                profile = "fragmented"
            writer.writerow({"price_band": band, "hhi": hhi, "concentration_profile": profile})


def write_coverage_gaps_csv(path, coverage_gaps):
    """Write coverage gaps analysis to CSV"""
    fieldnames = [
        "group",
        "price_band",
        "shop_sku_count",
        "market_sku_count",
        "gap_type",
        "gap_score",
        "market_volume_orders",
        "market_avg_price",
        "market_hhi_by_band",
        "novelty_proxy_index",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in coverage_gaps:
            writer.writerow({key: row.get(key) for key in fieldnames})


def write_markdown(path, payload, category_id, pages, page_size):
    lines = [
        f"# Анализ рынка конкурентов {DEFAULT_DATE}",
        "",
        f"- category_id: `{category_id}`",
        f"- pages scanned: `{pages}`",
        f"- page_size: `{page_size}`",
        f"- observed products: `{payload['summary']['observed_products']}`",
        f"- observed sellers: `{payload['summary']['observed_sellers']}`",
        f"- observed idea clusters: `{payload['summary']['observed_idea_clusters']}`",
        f"- overall dominance HHI: `{payload['summary'].get('overall_dominance_hhi')}`",
        f"- novelty proxy index: `{payload['summary'].get('novelty_proxy_index')}`",
        f"- target margin pct: `{payload['summary'].get('target_margin_pct')}`",
        f"- economics coverage groups pct: `{payload['summary'].get('economics_coverage_groups_pct')}`",
        f"- economics coverage windows pct: `{payload['summary'].get('economics_coverage_windows_pct')}`",
        "",
        "## Топ продавцы в наблюдаемой выборке",
        "",
    ]
    for row in payload["top_sellers"][:10]:
        lines.append(
            f"- {row['seller_title']} | orders `{row['orders_sum']}` | share `{row.get('share_of_observed_orders_pct', 0)}%` | products `{row['products_seen']}` | avg price `{row['avg_price']} ₽` | core group `{row['top_group']}` | novelty `{row.get('novelty_proxy_index')}` | profile `{row.get('novelty_profile')}`"
        )
    lines.extend(["", "## Что продаётся в рынке", ""])
    for row in payload["top_products"][:15]:
        lines.append(
            f"- {row['title']} | seller `{row['seller_title']}` | orders `{row['orders']}` | price `{row['price']} ₽`"
        )
    lines.extend(["", "## Группы товаров", ""])
    for row in payload["groups"][:10]:
        gap = "н/д" if row["price_gap_pct"] is None else f"{row['price_gap_pct']}%"
        lines.append(
            f"- {row['group']} | orders `{row['orders_sum']}` | sellers `{row['seller_count']}` | market avg `{row['avg_price']} ₽` | my avg `{row['my_avg_price']}` | gap `{gap}` | leader share `{row.get('leading_seller_share_pct')}` | HHI `{row.get('dominance_hhi')}` | profile `{row.get('competition_profile')}` | novelty `{row.get('novelty_proxy_index')}`"
        )
        for product in row["top_products"][:3]:
            lines.append(
                f"  - {product['title']} | seller `{product['seller_title']}` | orders `{product['orders']}` | price `{product['price']} ₽`"
            )
    lines.extend(["", "## Ценовые коридоры", ""])
    for row in payload.get("price_bands", [])[:10]:
        lines.append(
            f"- {row['price_band']} ₽ | orders `{row['orders_sum']}` | products `{row['products_seen']}` | sellers `{row['seller_count']}` | avg `{row['avg_price']} ₽`"
        )
    lines.extend(["", "## Кластеры товарных идей", ""])
    for row in payload.get("idea_clusters", [])[:10]:
        lines.append(
            f"- {row['idea_cluster']} | group `{row['group']}` | orders `{row['orders_sum']}` | products `{row['products_seen']}` | sellers `{row['seller_count']}` | avg `{row['avg_price']} ₽` | novelty `{row.get('novelty_proxy_index')}`"
        )
        for product in row["top_products"][:3]:
            lines.append(
                f"  - {product['title']} | seller `{product['seller_title']}` | orders `{product['orders']}` | price `{product['price']} ₽`"
            )
    lines.extend(["", "## Окна входа", ""])
    for row in payload.get("entry_windows", [])[:10]:
        lines.append(
            f"- {row['group']} / {row['price_band']} | score `{row['entry_window_score']}` | adj_score `{row.get('entry_window_score_adjusted')}` | profile `{row['entry_window_profile']}` | decision `{row.get('entry_strategy_label')}` | priority `{row.get('entry_priority_score')}` | HHI `{row['dominance_hhi']}` | novelty `{row.get('novelty_proxy_index')}` | margin fit `{row.get('market_margin_fit_pct')}` | orders `{row['orders_sum']}` | avg `{row['avg_price']} ₽`"
        )
    lines.extend(["", "## Куда входить первым", ""])
    for row in [row for row in payload.get("entry_windows", []) if row.get("entry_strategy_bucket") == "enter_now"][:10]:
        lines.append(
            f"- {row['group']} / {row['price_band']} | score `{row['entry_window_score']}` | priority `{row.get('entry_priority_score')}` | margin fit `{row.get('market_margin_fit_pct')}` | reason `{row.get('entry_strategy_reason')}`"
        )
    lines.extend(["", "## Где тестировать аккуратно", ""])
    for row in [row for row in payload.get("entry_windows", []) if row.get("entry_strategy_bucket") in {'test_entry', 'validate_economics'}][:10]:
        lines.append(
            f"- {row['group']} / {row['price_band']} | decision `{row.get('entry_strategy_label')}` | HHI `{row.get('dominance_hhi')}` | margin fit `{row.get('market_margin_fit_pct')}` | reason `{row.get('entry_strategy_reason')}`"
        )
    lines.extend(["", "## Где не входить или менять закупку", ""])
    for row in [row for row in payload.get("entry_windows", []) if row.get("entry_strategy_bucket") in {'avoid', 'improve_sourcing'}][:10]:
        lines.append(
            f"- {row['group']} / {row['price_band']} | decision `{row.get('entry_strategy_label')}` | HHI `{row.get('dominance_hhi')}` | margin fit `{row.get('market_margin_fit_pct')}` | reason `{row.get('entry_strategy_reason')}`"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_group_csv(path, groups):
    fieldnames = [
        "group",
        "products_seen",
        "seller_count",
        "orders_sum",
        "avg_price",
        "median_price",
        "my_avg_price",
        "my_median_price",
        "my_sku_count",
        "price_gap_pct",
        "leading_seller_share_pct",
        "dominance_hhi",
        "competition_profile",
        "novelty_proxy_index",
        "fresh_top_product_share_pct",
        "novelty_profile",
        "my_avg_cogs",
        "my_avg_gross_margin_pct",
        "market_margin_fit_pct",
        "target_margin_pct",
        "margin_vs_target_pct",
        "market_margin_fit_profile",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in groups:
            writer.writerow({key: row.get(key) for key in fieldnames})


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze competitor market demand and price structure for an MM category.")
    parser.add_argument("--category-id", type=int, default=DEFAULT_CATEGORY_ID)
    parser.add_argument("--pages", type=int, default=8)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--normalized-dir", default=str(NORMALIZED_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    parser.add_argument("--sellers-json", default=DEFAULT_TOP_SELLERS_JSON)
    parser.add_argument("--my-products-csv", default=DEFAULT_MY_PRODUCTS_CSV)
    parser.add_argument("--official-report-json", default=DEFAULT_OFFICIAL_REPORT_JSON)
    parser.add_argument("--cogs-overrides-json", default=str(COGS_OVERRIDES_PATH))
    parser.add_argument("--target-margin-pct", type=float, default=35.0)
    parser.add_argument("--price-band-boundaries", type=float, nargs="+", default=DEFAULT_PRICE_BAND_BOUNDARIES)
    return parser.parse_args()


def main():
    args = parse_args()
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir = ensure_dir(Path(args.normalized_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))
    seller_lookup = load_seller_lookup(args.sellers_json)
    my_group_prices = load_my_group_prices(args.my_products_csv)
    my_group_economics = merge_group_economics(
        load_my_group_economics(args.official_report_json),
        load_cogs_override_rows(args.cogs_overrides_json),
    )

    items = []
    seen_product_ids = set()
    with create_session() as session:
        for page in range(args.pages):
            data = search_page(session, args.category_id, args.page_size, page * args.page_size)
            page_items = data.get("items") or []
            if not page_items:
                break
            for row in page_items:
                product_id = int(row.get("productId") or row.get("id") or 0)
                if not product_id or product_id in seen_product_ids:
                    continue
                seen_product_ids.add(product_id)
                seller_id = int(row.get("storeCode") or 0)
                seller_meta = seller_lookup.get(seller_id) or {}
                item = {
                    "product_id": product_id,
                    "seller_id": seller_id,
                    "seller_title": seller_meta.get("title") or f"seller_{seller_id}",
                    "title": row.get("name") or "",
                    "price": round((row.get("price") or 0) / 100, 2),
                    "orders": int(row.get("orders") or 0),
                    "rating": float((row.get("ratings") or {}).get("rating") or 0),
                    "reviews": int((row.get("ratings") or {}).get("commentsCount") or 0),
                }
                item["group"] = classify_group(item["title"])
                item["price_band"] = price_band_label(item["price"])
                item["idea_cluster"] = idea_fingerprint(item["title"], item["group"])
                item.update(novelty_proxy(item))
                items.append(item)

    payload = summarize_market_payload(items, seller_lookup, my_group_prices)
    payload = apply_market_margin_fit(payload, my_group_economics, target_margin_pct=args.target_margin_pct)
    
    # NEW: Apply crosstab and HHI analysis
    items_by_band = defaultdict(list)
    for item in items:
        items_by_band[item["price_band"]].append(item)
    
    hhi_by_band = calculate_hhi_by_band(items_by_band)
    crosstab_data = build_group_price_band_crosstab(items, my_group_prices)
    coverage_gaps = identify_coverage_gaps(items, my_group_prices, hhi_by_band)
    
    # NEW: Factor novelty into entry window scoring
    payload["entry_windows"] = calculate_entry_window_with_novelty_factoring(
        payload.get("entry_windows", [])
    )
    
    # NEW: Add coverage gaps to entry windows and prioritize
    gaps_by_window = {(gap["group"], gap["price_band"]): gap for gap in coverage_gaps}
    payload["entry_windows"] = add_coverage_gap_to_entry_windows(
        payload.get("entry_windows", []), gaps_by_window
    )
    
    # Sort by new priority score
    payload["entry_windows"] = sorted(
        payload.get("entry_windows", []),
        key=lambda x: (x.get("entry_priority_score", 0), x.get("orders_sum", 0)),
        reverse=True
    )
    
    # NEW: Add metadata about crosstab and HHI
    payload["summary"]["hhi_by_band"] = hhi_by_band
    payload["summary"]["price_band_boundaries"] = list(args.price_band_boundaries)
    payload["summary"]["coverage_gaps_count"] = len(coverage_gaps)
    
    json_path = report_dir / f"competitor_market_analysis_{args.date_tag}.json"
    md_path = report_dir / f"competitor_market_analysis_{args.date_tag}.md"
    csv_path = report_dir / f"competitor_market_groups_{args.date_tag}.csv"
    crosstab_path = report_dir / f"competitor_market_crosstab_{args.date_tag}.csv"
    gaps_path = report_dir / f"competitor_market_coverage_gaps_{args.date_tag}.csv"
    normalized_path = normalized_dir / f"competitor_market_analysis_{args.date_tag}.json"
    dashboard_path = dashboard_dir / f"competitor_market_analysis_{args.date_tag}.json"
    
    metadata = {
        "window": {},
        "market_scope": {
            "category_id": args.category_id,
            "pages": args.pages,
            "page_size": args.page_size,
        },
        "cogs_overrides_json": args.cogs_overrides_json,
        "crosstab_implemented": True,
        "hhi_calculated": True,
        "coverage_gaps_identified": True,
        "entry_windows_prioritized": True,
    }
    
    write_json(json_path, payload)
    write_markdown(md_path, payload, args.category_id, args.pages, args.page_size)
    write_group_csv(csv_path, payload["groups"])
    write_crosstab_csv(crosstab_path, crosstab_data, hhi_by_band)
    write_coverage_gaps_csv(gaps_path, coverage_gaps)
    write_json(normalized_path, {"metadata": metadata, **payload})
    write_json(dashboard_path, build_market_dashboard(payload, metadata=metadata))
    
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {csv_path}")
    print(f"Saved: {crosstab_path}")
    print(f"Saved: {gaps_path}")
    print(f"Saved: {normalized_path}")
    print(f"Saved: {dashboard_path}")


if __name__ == "__main__":
    main()
