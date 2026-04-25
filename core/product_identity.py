#!/usr/bin/env python3
import re
from collections import defaultdict


def normalize_text(value):
    cleaned = re.sub(r"\s+", " ", (value or "").strip().lower())
    return cleaned


def normalize_barcode(value):
    raw = re.sub(r"\D+", "", value or "")
    return raw or None


def row_identity_key(row):
    barcode = normalize_barcode(row.get("barcode"))
    if barcode:
        return f"barcode:{barcode}"
    seller_sku_id = (row.get("seller_sku_id") or "").strip()
    if seller_sku_id:
        return f"seller_sku:{seller_sku_id}"
    sku = (row.get("sku") or "").strip()
    if sku:
        return f"sku:{sku}"
    product_id = row.get("product_id")
    if product_id:
        return f"product:{product_id}"
    title = normalize_text(row.get("title"))
    return f"title:{title}"


def row_family_key(row):
    product_id = row.get("product_id")
    if product_id:
        return f"product:{product_id}"
    title = normalize_text(row.get("title"))
    return f"title:{title}"


def build_variant_families(rows):
    families = defaultdict(list)
    for row in rows:
        families[row_family_key(row)].append(row)
    return families


def summarize_variant_families(rows):
    families = build_variant_families(rows)
    summary = []
    for family_key, items in families.items():
        barcodes = sorted({normalize_barcode(item.get("barcode")) for item in items if normalize_barcode(item.get("barcode"))})
        seller_skus = sorted({(item.get("seller_sku_id") or "").strip() for item in items if (item.get("seller_sku_id") or "").strip()})
        skus = sorted({(item.get("sku") or "").strip() for item in items if (item.get("sku") or "").strip()})
        product_ids = sorted({item.get("product_id") for item in items if item.get("product_id")})
        sold_units = sum(int(item.get("units_sold", 0) or 0) for item in items)
        stock_units = sum(int(item.get("total_stock", 0) or 0) for item in items)
        revenue = round(sum(float(item.get("net_revenue", 0.0) or 0.0) for item in items), 2)
        avg_daily = round(sum(float(item.get("avg_daily_sales_official", 0.0) or 0.0) for item in items), 3)
        summary.append(
            {
                "family_key": family_key,
                "title": max(items, key=lambda item: len(item.get("title") or ""))["title"],
                "variant_count": len(items),
                "barcode_count": len(barcodes),
                "seller_sku_count": len(seller_skus),
                "sku_count": len(skus),
                "product_ids": product_ids,
                "barcodes": barcodes,
                "seller_sku_ids": seller_skus,
                "skus": skus,
                "sold_units_sum": sold_units,
                "stock_units_sum": stock_units,
                "net_revenue_sum": revenue,
                "avg_daily_sales_sum": avg_daily,
                "variants": items,
            }
        )
    summary.sort(key=lambda row: (row["net_revenue_sum"], row["sold_units_sum"], row["avg_daily_sales_sum"]), reverse=True)
    return summary


def normalize_family_row(row):
    return {
        "family_key": row.get("family_key", ""),
        "title": row.get("title", ""),
        "variant_count": int(row.get("variant_count", 0) or 0),
        "barcode_count": int(row.get("barcode_count", 0) or 0),
        "seller_sku_count": int(row.get("seller_sku_count", 0) or 0),
        "sku_count": int(row.get("sku_count", 0) or 0),
        "product_ids": list(row.get("product_ids", []) or []),
        "barcodes": list(row.get("barcodes", []) or []),
        "seller_sku_ids": list(row.get("seller_sku_ids", []) or []),
        "skus": list(row.get("skus", []) or []),
        "sold_units_sum": int(row.get("sold_units_sum", 0) or 0),
        "stock_units_sum": int(row.get("stock_units_sum", 0) or 0),
        "net_revenue_sum": round(float(row.get("net_revenue_sum", 0.0) or 0.0), 2),
        "avg_daily_sales_sum": round(float(row.get("avg_daily_sales_sum", 0.0) or 0.0), 4),
        "stock_cover_days": row.get("stock_cover_days"),
        "stockout_risk": bool(row.get("stockout_risk")),
        "stale_stock": bool(row.get("stale_stock")),
        "current_winner": bool(row.get("current_winner")),
        "reorder_candidate": bool(row.get("reorder_candidate")),
        "variant_titles": list(row.get("variant_titles", []) or []),
    }
