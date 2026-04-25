#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

from core.dashboard_schema import INDEX_SCHEMA_VERSION


COMPARABLE_KPI_KEYS = [
    "total_skus",
    "sold_skus",
    "revenue_total",
    "gross_profit_total",
    "stockout_risk_count",
    "stale_stock_count",
    "observed_seller_count",
    "observed_group_count",
    "observed_price_bands",
    "observed_idea_clusters",
    "overall_dominance_hhi",
    "novelty_proxy_index",
    "blind_spot_windows_count",
    "entry_ready_windows_count",
    "test_entry_windows_count",
    "avoid_windows_count",
    "priced_windows_count",
    "aggressive_price_windows_count",
    "market_price_windows_count",
    "test_price_windows_count",
    "do_not_discount_windows_count",
    "priority_cards_count",
    "price_trap_cards_count",
    "seo_needs_work_count",
    "seo_priority_fix_count",
    "market_supported_cards_count",
    "double_fix_count",
    "media_needs_work_count",
    "photo_gap_count",
    "spec_gap_count",
    "with_video_count",
    "description_needs_work_count",
    "thin_content_count",
    "description_gap_count",
    "storage_rows_count",
    "rows_with_amount_count",
    "rows_without_identity_count",
    "total_amount",
    "penalty_total",
    "avg_amount_per_row",
    "return_rows_count",
    "total_returns_count",
    "unique_return_reasons_count",
    "rows_without_reason_count",
    "top_reason_share_pct",
    "avg_returns_per_row",
    "waybill_rows_count",
    "historical_cogs_items_count",
    "total_quantity_supplied",
]


def _safe_float(value):
    if value in (None, "", "n/a", "н/д"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_kpis(current, previous):
    current = current or {}
    previous = previous or {}
    diffs = {}
    for key in COMPARABLE_KPI_KEYS:
        current_value = _safe_float(current.get(key))
        previous_value = _safe_float(previous.get(key))
        if current_value is None or previous_value is None:
            continue
        diffs[key] = {
            "current": current_value,
            "previous": previous_value,
            "delta": round(current_value - previous_value, 2),
            "delta_pct": round(((current_value - previous_value) / previous_value) * 100.0, 2) if previous_value else None,
        }
    return diffs


def summarize_change(report_kind, diffs):
    priority = {
        "weekly_operational": ["revenue_total", "gross_profit_total", "sold_skus", "stockout_risk_count", "stale_stock_count"],
        "official_period_analysis": ["revenue_total", "gross_profit_total", "sold_skus", "stockout_risk_count", "stale_stock_count"],
        "cubejs_period_compare": ["revenue_total", "sold_skus"],
        "competitor_market_analysis": ["overall_dominance_hhi", "novelty_proxy_index", "observed_seller_count", "blind_spot_windows_count", "entry_ready_windows_count"],
        "dynamic_pricing": ["priced_windows_count", "aggressive_price_windows_count", "market_price_windows_count", "test_price_windows_count", "do_not_discount_windows_count"],
        "marketing_card_audit": ["priority_cards_count", "price_trap_cards_count", "seo_needs_work_count", "market_supported_cards_count", "double_fix_count"],
        "media_richness_report": ["priority_cards_count", "media_needs_work_count", "photo_gap_count", "spec_gap_count", "with_video_count"],
        "description_seo_report": ["priority_cards_count", "description_needs_work_count", "thin_content_count", "description_gap_count"],
        "paid_storage_report": ["total_amount", "rows_with_amount_count", "rows_without_identity_count", "avg_amount_per_row"],
        "sales_return_report": ["total_returns_count", "unique_return_reasons_count", "rows_without_reason_count", "rows_without_identity_count", "top_reason_share_pct"],
        "waybill_cost_layer": ["total_amount", "rows_without_identity_count", "avg_amount_per_row", "waybill_rows_count", "historical_cogs_items_count", "total_quantity_supplied"],
    }.get(report_kind, COMPARABLE_KPI_KEYS)
    lines = []
    for key in priority:
        row = diffs.get(key)
        if not row or row["delta"] == 0:
            continue
        lines.append({"key": key, **row})
    return lines[:5]


def _sort_timestamp(item):
    value = item.get("generated_at")
    if value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    try:
        return Path(item["file_path"]).stat().st_mtime
    except OSError:
        return 0.0


def parse_dashboard_file(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    report_kind = detect_report_kind(Path(path).stem)
    if report_kind == "cubejs_period_compare":
        current = ((payload.get("periods") or {}).get("current_trailing_year") or {})
        metrics = current.get("metrics") or {}
        window = {
            "date_from": current.get("date_from"),
            "date_to": current.get("date_to"),
            "window_days": 365,
        }
        kpis = {
            "revenue_total": metrics.get("revenue_total", 0.0),
            "gross_profit_total": metrics.get("profit_total", 0.0),
            "sold_skus": metrics.get("items_sold_total", 0.0),
            "stockout_risk_count": 0,
            "stale_stock_count": 0,
            "total_skus": 0,
        }
    elif report_kind == "competitor_market_analysis":
        window = metadata.get("window") or {}
        kpis = payload.get("kpis") or {}
    else:
        window = metadata.get("window") or {}
        kpis = payload.get("kpis") or {}
    return {
        "schema_version": payload.get("schema_version") or "0.0.0",
        "file_name": Path(path).name,
        "file_path": str(Path(path)),
        "report_name": Path(path).stem,
        "report_kind": report_kind,
        "report_variant": detect_report_variant(Path(path).stem, report_kind),
        "generated_at": payload.get("generated_at"),
        "window": window,
        "kpis": kpis,
        "documents": metadata.get("documents") or {},
    }


def detect_report_kind(report_name):
    if report_name.startswith("weekly_operational_report_"):
        return "weekly_operational"
    if report_name.startswith("official_period_analysis_"):
        return "official_period_analysis"
    if report_name.startswith("cubejs_period_compare_"):
        return "cubejs_period_compare"
    if report_name.startswith("competitor_market_analysis_"):
        return "competitor_market_analysis"
    if report_name.startswith("market_rescored_after_cogs_"):
        return "competitor_market_analysis"
    if report_name.startswith("dynamic_pricing_"):
        return "dynamic_pricing"
    if report_name.startswith("marketing_card_audit_"):
        return "marketing_card_audit"
    if report_name.startswith("media_richness_report_"):
        return "media_richness_report"
    if report_name.startswith("description_seo_report_"):
        return "description_seo_report"
    if report_name.startswith("paid_storage_report_"):
        return "paid_storage_report"
    if report_name.startswith("sales_return_report_"):
        return "sales_return_report"
    if report_name.startswith("waybill_cost_layer_"):
        return "waybill_cost_layer"
    return "unknown"


def detect_report_variant(report_name, report_kind):
    if report_kind == "official_period_analysis":
        if "stricter_v2" in report_name:
            return "Strict V2"
        if "stricter" in report_name:
            return "Strict"
        if "family" in report_name:
            return "Family"
        if "dashboard" in report_name:
            return "Dashboard"
        return "Base"
    if report_kind == "competitor_market_analysis":
        if report_name.startswith("market_rescored_after_cogs_"):
            suffix = report_name.replace("market_rescored_after_cogs_", "")
            return f"Rescored {suffix}"
        suffix = report_name.replace("competitor_market_analysis_", "")
        return suffix
    if report_kind == "cubejs_period_compare":
        return "Long Range"
    if report_kind == "dynamic_pricing":
        suffix = report_name.replace("dynamic_pricing_", "")
        return suffix
    if report_kind == "marketing_card_audit":
        suffix = report_name.replace("marketing_card_audit_", "")
        return suffix
    if report_kind == "media_richness_report":
        suffix = report_name.replace("media_richness_report_", "")
        return suffix
    if report_kind == "description_seo_report":
        suffix = report_name.replace("description_seo_report_", "")
        return suffix
    if report_kind == "paid_storage_report":
        suffix = report_name.replace("paid_storage_report_", "")
        return suffix
    if report_kind == "sales_return_report":
        suffix = report_name.replace("sales_return_report_", "")
        return suffix
    if report_kind == "waybill_cost_layer":
        suffix = report_name.replace("waybill_cost_layer_", "")
        return suffix
    if report_kind == "weekly_operational":
        return "Weekly"
    return report_name


def build_dashboard_index(dashboard_dir):
    dashboard_dir = Path(dashboard_dir)
    items = []
    for path in sorted(dashboard_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        items.append(parse_dashboard_file(path))
    items.sort(key=_sort_timestamp, reverse=True)
    previous_by_kind = {}
    for item in items:
        previous_item = previous_by_kind.get(item["report_kind"])
        item["previous_same_kind"] = (
            {
                "file_name": previous_item["file_name"],
                "report_name": previous_item["report_name"],
                "generated_at": previous_item.get("generated_at"),
            }
            if previous_item
            else None
        )
        if previous_item:
            diffs = compare_kpis(item.get("kpis"), previous_item.get("kpis"))
            item["change_from_previous"] = {
                "previous_file_name": previous_item["file_name"],
                "previous_generated_at": previous_item.get("generated_at"),
                "diffs": diffs,
                "summary": summarize_change(item["report_kind"], diffs),
            }
        else:
            item["change_from_previous"] = None
        previous_by_kind[item["report_kind"]] = item
    latest = items[0] if items else None
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "items": items,
        "reports": items,
        "latest": latest,
        "latest_by_kind": {
            kind: next((item for item in items if item["report_kind"] == kind), None)
            for kind in sorted({item["report_kind"] for item in items})
        },
    }
