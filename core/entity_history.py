#!/usr/bin/env python3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from core.io_utils import load_json
from core.paths import DASHBOARD_DIR, ENTITY_HISTORY_INDEX_PATH


def _safe_timestamp(value):
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _snapshot_from_row(row, report_name, generated_at, file_name):
    return {
        "report_name": report_name,
        "file_name": file_name,
        "generated_at": generated_at,
        "title": row.get("title"),
        "sku": row.get("sku"),
        "seller_sku_id": row.get("seller_sku_id"),
        "barcode": row.get("barcode"),
        "product_id": row.get("product_id"),
        "entity_key": row.get("key") or row.get("product_id") or row.get("title"),
        "group": row.get("group"),
        "price_band": row.get("price_band"),
        "action_label": row.get("action_label"),
        "action_reason": row.get("action_reason"),
        "priority_bucket": row.get("priority_bucket"),
        "priority_score": row.get("priority_score"),
        "price_trap": bool(row.get("price_trap")),
        "seo_status": row.get("seo_status"),
        "seo_score": row.get("seo_score"),
        "pricing_label": row.get("pricing_label"),
        "sale_price": row.get("sale_price"),
        "threshold": row.get("threshold"),
        "suggested_threshold_price": row.get("suggested_threshold_price"),
        "pricing_suggested_price": row.get("pricing_suggested_price"),
        "avg_market_price": row.get("avg_market_price"),
        "stock_value_sale": row.get("stock_value_sale"),
        "units_sold": row.get("units_sold"),
        "total_stock": row.get("total_stock"),
        "stale_stock": bool(row.get("stale_stock")),
    }


def build_entity_history_index(dashboard_dir=DASHBOARD_DIR):
    dashboard_dir = Path(dashboard_dir)
    grouped = defaultdict(list)
    for path in sorted(dashboard_dir.glob("marketing_card_audit_*.json")):
        payload = load_json(path)
        generated_at = payload.get("generated_at")
        report_name = path.stem
        rows = ((payload.get("tables") or {}).get("priority_cards")) or []
        for row in rows:
            entity_key = row.get("key") or row.get("product_id") or row.get("title")
            if not entity_key:
                continue
            grouped[str(entity_key)].append(_snapshot_from_row(row, report_name, generated_at, path.name))

    entities = []
    for entity_key, snapshots in grouped.items():
        snapshots.sort(key=lambda row: _safe_timestamp(row.get("generated_at")), reverse=True)
        latest = snapshots[0]
        entities.append(
            {
                "entity_key": entity_key,
                "title": latest.get("title"),
                "latest": latest,
                "history": snapshots,
                "history_count": len(snapshots),
                "first_seen_at": snapshots[-1].get("generated_at"),
                "last_seen_at": latest.get("generated_at"),
                "price_trap_seen_count": sum(1 for row in snapshots if row.get("price_trap")),
                "seo_issue_seen_count": sum(1 for row in snapshots if row.get("seo_status") in {"needs_work", "priority_fix"}),
            }
        )
    entities.sort(key=lambda row: (_safe_timestamp(row.get("last_seen_at")), row.get("history_count", 0)), reverse=True)
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source_dir": str(dashboard_dir),
        "entity_count": len(entities),
        "entities": entities,
    }
