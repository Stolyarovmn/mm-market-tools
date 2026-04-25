#!/usr/bin/env python3
import datetime as dt
from collections import Counter, defaultdict

from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION


def _safe_round(value, digits=2):
    return round(float(value or 0.0), digits)


def normalize_operational_row(row):
    return {
        "key": row.get("key", ""),
        "barcode": row.get("barcode", ""),
        "sku": row.get("sku", ""),
        "seller_sku_id": row.get("seller_sku_id", ""),
        "product_id": row.get("product_id", 0),
        "title": row.get("title", ""),
        "status": row.get("status", ""),
        "in_sale": int(row.get("in_sale", 0) or 0),
        "to_ship": int(row.get("to_ship", 0) or 0),
        "total_stock": int(row.get("total_stock", 0) or 0),
        "available_to_ship": int(row.get("available_to_ship", 0) or 0),
        "units_sold": int(row.get("units_sold", 0) or 0),
        "returns": int(row.get("returns", 0) or 0),
        "avg_daily_sales_official": _safe_round(row.get("avg_daily_sales_official", 0.0), 4),
        "calendar_sales_velocity": _safe_round(row.get("calendar_sales_velocity", 0.0), 4),
        "sales_velocity_in_stock": _safe_round(row.get("sales_velocity_in_stock", 0.0), 4),
        "estimated_in_stock_days": _safe_round(row.get("estimated_in_stock_days", 0.0), 2),
        "estimated_oos_days": _safe_round(row.get("estimated_oos_days", 0.0), 2),
        "estimated_lost_units_oos": _safe_round(row.get("estimated_lost_units_oos", 0.0), 2),
        "turnover_days_official": _safe_round(row.get("turnover_days_official", 0.0), 2),
        "stock_cover_days": row.get("stock_cover_days"),
        "sale_price": _safe_round(row.get("sale_price", 0.0)),
        "revenue": _safe_round(row.get("revenue", 0.0)),
        "net_revenue": _safe_round(row.get("net_revenue", 0.0)),
        "gross_profit": _safe_round(row.get("gross_profit", 0.0)),
        "profit_margin_pct": _safe_round(row.get("profit_margin_pct", 0.0)),
        "stock_value_sale": _safe_round(row.get("stock_value_sale", 0.0)),
        "abc_revenue": row.get("abc_revenue", "C"),
        "abc_profit": row.get("abc_profit", "C"),
        "stockout_risk": bool(row.get("stockout_risk")),
        "reorder_candidate": bool(row.get("reorder_candidate")),
        "stale_stock": bool(row.get("stale_stock")),
        "historical_only_hit": bool(row.get("historical_only_hit")),
        "current_winner": bool(row.get("current_winner")),
    }


def normalize_operational_rows(rows):
    return [normalize_operational_row(row) for row in rows]


def normalize_family_row(row):
    return {
        "family_key": row.get("family_key", ""),
        "title": row.get("title", ""),
        "variant_count": int(row.get("variant_count", 0) or 0),
        "barcode_count": int(row.get("barcode_count", 0) or 0),
        "seller_sku_count": int(row.get("seller_sku_count", 0) or 0),
        "sku_count": int(row.get("sku_count", 0) or 0),
        "sold_units_sum": int(row.get("sold_units_sum", 0) or 0),
        "stock_units_sum": int(row.get("stock_units_sum", 0) or 0),
        "net_revenue_sum": _safe_round(row.get("net_revenue_sum", 0.0)),
        "avg_daily_sales_sum": _safe_round(row.get("avg_daily_sales_sum", 0.0), 4),
        "stock_cover_days": row.get("stock_cover_days"),
        "stockout_risk": bool(row.get("stockout_risk")),
        "stale_stock": bool(row.get("stale_stock")),
        "current_winner": bool(row.get("current_winner")),
        "reorder_candidate": bool(row.get("reorder_candidate")),
        "variant_titles": list(row.get("variant_titles", []) or []),
    }


def _top_rows(rows, sort_key, limit=10):
    return [
        normalize_operational_row(row)
        for row in sorted(rows, key=lambda item: item.get(sort_key, 0.0), reverse=True)[:limit]
    ]


def _counter_payload(rows, key):
    counts = Counter(row.get(key) or "UNKNOWN" for row in rows)
    return [{"key": name, "count": counts[name]} for name in sorted(counts)]


def _sum_by_key(rows, group_key, value_key):
    bucket = defaultdict(float)
    for row in rows:
        bucket[row.get(group_key) or "UNKNOWN"] += float(row.get(value_key) or 0.0)
    return [
        {"key": key, "value": round(value, 2)}
        for key, value in sorted(bucket.items(), key=lambda item: item[1], reverse=True)
    ]


def _abc_examples(rows, abc_key, sort_key, limit_per_bucket=8):
    buckets = {"A": [], "B": [], "C": []}
    for abc in buckets:
        matched = [row for row in rows if row.get(abc_key) == abc]
        buckets[abc] = [
            normalize_operational_row(row)
            for row in sorted(
                matched,
                key=lambda item: (item.get(sort_key, 0.0), item.get("units_sold", 0)),
                reverse=True,
            )[:limit_per_bucket]
        ]
    return buckets


def build_operational_dashboard(rows, summary, metadata=None):
    metadata = metadata or {}
    normalized_rows = normalize_operational_rows(rows)
    current_winners = [row for row in normalized_rows if row.get("current_winner")]
    reorder_now = [row for row in normalized_rows if row.get("reorder_candidate")]
    soft_signal_products = summary.get("soft_signal_products", []) or []
    stale_stock = [row for row in normalized_rows if row["stale_stock"]]
    family_rows = summary.get("family_rows_payload", []) or []
    family_current_winners = [row for row in family_rows if row.get("current_winner")]
    family_reorder_now = [row for row in family_rows if row.get("reorder_candidate")]
    family_soft_signals = summary.get("family_soft_signal_products", []) or []
    family_multi_variant = [row for row in family_rows if int(row.get("variant_count", 0) or 0) > 1]

    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "metadata": metadata,
        "kpis": {
            "total_skus": int(summary.get("rows", 0) or 0),
            "sold_skus": int(summary.get("sold_skus", 0) or 0),
            "family_count": int(summary.get("family_rows", 0) or 0),
            "multi_variant_family_count": int(summary.get("multi_variant_families", 0) or 0),
            "revenue_total": _safe_round(summary.get("revenue_total", 0.0)),
            "gross_profit_total": _safe_round(summary.get("gross_profit_total", 0.0)),
            "estimated_lost_units_oos_total": _safe_round(summary.get("estimated_lost_units_oos_total", 0.0)),
            "stockout_risk_count": int(summary.get("stockout_risk_count", 0) or 0),
            "stale_stock_count": int(summary.get("stale_stock_count", 0) or 0),
        },
        "tables": {
            "current_winners": _top_rows(current_winners, "net_revenue", limit=15),
            "soft_signal_products": [normalize_operational_row(row) for row in soft_signal_products[:15]],
            "profit_leaders": _top_rows(normalized_rows, "gross_profit", limit=15),
            "stockout_risk": [normalize_operational_row(row) for row in summary.get("stockout_risk", [])[:15]],
            "stale_stock": _top_rows(stale_stock, "stock_value_sale", limit=15),
        },
        "charts": {
            "abc_revenue_counts": _counter_payload(normalized_rows, "abc_revenue"),
            "abc_profit_counts": _counter_payload(normalized_rows, "abc_profit"),
            "status_counts": _counter_payload(normalized_rows, "status"),
            "revenue_by_abc": _sum_by_key(normalized_rows, "abc_revenue", "net_revenue"),
            "profit_by_abc": _sum_by_key(normalized_rows, "abc_profit", "gross_profit"),
            "stock_value_by_status": _sum_by_key(normalized_rows, "status", "stock_value_sale"),
            "abc_revenue_examples": _abc_examples(rows, "abc_revenue", "net_revenue"),
            "abc_profit_examples": _abc_examples(rows, "abc_profit", "gross_profit"),
        },
        "actions": {
            "reorder_now": _top_rows(reorder_now, "sales_velocity_in_stock", limit=20),
            "markdown_candidates": _top_rows(stale_stock, "stock_value_sale", limit=20),
            "protect_winners": _top_rows(current_winners, "gross_profit", limit=20),
            "watchlist_signals": [normalize_operational_row(row) for row in soft_signal_products[:20]],
        },
        "family_tables": {
            "family_current_winners": [normalize_family_row(row) for row in family_current_winners[:15]],
            "family_reorder_now": [normalize_family_row(row) for row in family_reorder_now[:15]],
            "family_soft_signal_products": [normalize_family_row(row) for row in family_soft_signals[:15]],
            "largest_multi_variant_families": [
                normalize_family_row(row)
                for row in sorted(
                    family_multi_variant,
                    key=lambda item: (item.get("variant_count", 0), item.get("stock_units_sum", 0)),
                    reverse=True,
                )[:15]
            ],
        },
    }
