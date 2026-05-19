#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path

from core.cubejs_api import fetch_cubejs_meta, flatten_results, run_cubejs_query
from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION
from core.dates import market_window_bounds
from core.io_utils import load_json, write_csv_rows, write_json
from core.paths import DASHBOARD_DIR, NORMALIZED_DIR, REPORTS_DIR, ensure_dir, today_tag


CUBE_NAME = "SalesReturn"


def parse_args():
    parser = argparse.ArgumentParser(description="Build manager-facing SalesReturn dashboard bundle from CubeJS.")
    parser.add_argument("--token", default="")
    parser.add_argument("--shop-id", type=int, default=98)
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--normalized-dir", default=str(NORMALIZED_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--report-prefix", default=f"sales_return_report_{today_tag()}")
    parser.add_argument("--input-json", default="")
    parser.add_argument("--meta-json", default="")
    return parser.parse_args()


def _haystack(item):
    return f"{item.get('name', '')} {item.get('title', '')} {item.get('shortTitle', '')}".lower()


def _pick_best(items, preferred_groups, predicate=None):
    scored = []
    for item in items:
        if predicate and not predicate(item):
            continue
        hay = _haystack(item)
        score = 0
        for index, group in enumerate(preferred_groups, start=1):
            if all(token in hay for token in group):
                score = max(score, 100 - index)
            elif any(token in hay for token in group):
                score = max(score, 30 - index)
        if score:
            scored.append((score, item))
    if scored:
        scored.sort(key=lambda row: (-row[0], row[1].get("name") or ""))
        return scored[0][1]
    return items[0] if items else None


def _find_cube(meta):
    cubes = meta.get("cubes") or []
    for cube in cubes:
        if cube.get("name") == CUBE_NAME:
            return cube
    raise SystemExit("Cube SalesReturn не найден в CubeJS meta.")


def _select_members(meta):
    cube = _find_cube(meta)
    measures = cube.get("measures") or []
    dimensions = cube.get("dimensions") or []

    exact_measures = {item.get("name"): item for item in measures}
    exact_dimensions = {item.get("name"): item for item in dimensions}

    members = {
        "count_measure": exact_measures.get("SalesReturn.returned_quantity_measure") or _pick_best(measures, [["returned", "quantity"], ["return", "number"], ["count"]]),
        "secondary_measure": exact_measures.get("SalesReturn.number_of_returns_by_cause") or _pick_best(measures, [["returns", "cause"], ["return", "number"]]),
        "shop_dimension": exact_dimensions.get("SalesReturn.shop_id") or _pick_best(dimensions, [["shop", "id"]]),
        "date_dimension": exact_dimensions.get("SalesReturn.returned_at") or _pick_best(dimensions, [["returned", "at"], ["date"]], predicate=lambda item: item.get("type") == "time"),
        "reason_dimension": exact_dimensions.get("SalesReturn.cause") or _pick_best(dimensions, [["cause"], ["reason"]]),
        "sku_dimension": exact_dimensions.get("SalesReturn.sku_id") or _pick_best(dimensions, [["sku", "id"], ["sku"]]),
        "title_dimension": None,
        "barcode_dimension": None,
        "product_dimension": exact_dimensions.get("SalesReturn.product_id") or _pick_best(dimensions, [["product", "id"], ["item", "id"]]),
        "amount_dimension": exact_dimensions.get("SalesReturn.amount_to_return") or _pick_best(dimensions, [["amount", "return"], ["amount"], ["sum"]]),
    }
    missing = [key for key in ["count_measure", "shop_dimension", "date_dimension"] if not members.get(key)]
    if missing:
        raise SystemExit(f"Недостаточно members в CubeJS meta для SalesReturn: {', '.join(missing)}")
    return {key: value.get("name") if value else None for key, value in members.items()}


def _date_window(window_days):
    date_from, date_to = market_window_bounds(window_days)
    return date_from.date().isoformat(), date_to.date().isoformat()


def _build_query(shop_id, member_names, measures, dimensions=None, window_days=30, granularity=None, limit=None, order_member=None):
    date_from, date_to = _date_window(window_days)
    time_dimension = {
        "dimension": member_names["date_dimension"],
        "dateRange": [date_from, date_to],
    }
    if granularity:
        time_dimension["granularity"] = granularity
    query = {
        "measures": [member for member in measures if member],
        "timezone": "Europe/Moscow",
        "timeDimensions": [time_dimension],
        "filters": [
            {
                "member": member_names["shop_dimension"],
                "operator": "equals",
                "values": [str(shop_id)],
            }
        ],
    }
    if dimensions:
        query["dimensions"] = [member for member in dimensions if member]
    if limit:
        query["limit"] = limit
    if order_member:
        query["order"] = {order_member: "desc"}
    return query


def _to_float(value):
    if value in (None, "", "null"):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _row_title(row):
    for key in ["title", "sku", "barcode", "product_id", "reason"]:
        if row.get(key):
            return str(row[key])
    return "Строка без названия"


def _normalize_reason(value):
    raw = str(value or "").strip()
    return raw if raw else "Без причины"


def _normalize_entity_rows(rows):
    normalized = []
    for row in rows:
        value = _to_float(row.get("count_value"))
        amount = _to_float(row.get("amount_value"))
        normalized.append(
            {
                "title": _row_title(row),
                "reason": _normalize_reason(row.get("reason")),
                "sku": str(row.get("sku") or "").strip() or None,
                "seller_sku_id": str(row.get("sku") or "").strip() or None,
                "barcode": str(row.get("barcode") or "").strip() or None,
                "product_id": str(row.get("product_id") or "").strip() or None,
                "return_count": round(value, 2),
                "amount_value": round(amount, 2) if amount else None,
                "identity": str(row.get("sku") or row.get("barcode") or row.get("product_id") or "").strip() or None,
            }
        )
    normalized.sort(key=lambda item: (item.get("return_count") or 0, item.get("amount_value") or 0), reverse=True)
    return normalized


def _aggregate_reasons(entity_rows):
    buckets = {}
    for row in entity_rows:
        key = row.get("reason") or "Без причины"
        current = buckets.get(key) or {"title": key, "reason": key, "return_count": 0.0, "amount_value": 0.0}
        current["return_count"] += row.get("return_count") or 0.0
        current["amount_value"] += row.get("amount_value") or 0.0
        buckets[key] = current
    items = list(buckets.values())
    for row in items:
        row["return_count"] = round(row["return_count"], 2)
        row["amount_value"] = round(row["amount_value"], 2)
    items.sort(key=lambda item: (item.get("return_count") or 0, item.get("amount_value") or 0), reverse=True)
    return items


def _build_daily_rows(rows):
    normalized = []
    for row in rows:
        date_key = next((value for key, value in row.items() if key.endswith(".day")), None)
        normalized.append({"day": date_key or "н/д", "return_count": round(_to_float(row.get("count_value")), 2)})
    return normalized


def _parse_live_rows(member_names, payloads):
    entity_rows = []
    entity_data = flatten_results(payloads["entity_payload"])
    for row in entity_data:
        entity_rows.append(
            {
                "reason": row.get(member_names.get("reason_dimension")) if member_names.get("reason_dimension") else None,
                "sku": row.get(member_names.get("sku_dimension")) if member_names.get("sku_dimension") else None,
                "title": row.get(member_names.get("title_dimension")) if member_names.get("title_dimension") else None,
                "barcode": row.get(member_names.get("barcode_dimension")) if member_names.get("barcode_dimension") else None,
                "product_id": row.get(member_names.get("product_dimension")) if member_names.get("product_dimension") else None,
                "count_value": row.get(member_names["count_measure"]),
                "amount_value": row.get(member_names.get("amount_dimension")) if member_names.get("amount_dimension") else None,
            }
        )
    return {
        "entity_rows": _normalize_entity_rows(entity_rows),
        "daily_rows": _build_daily_rows(flatten_results(payloads["daily_payload"])),
    }


def _parse_input_rows(input_payload):
    raw_rows = input_payload.get("entity_rows")
    if raw_rows is None:
        raw_rows = flatten_results(input_payload)
    daily_rows = input_payload.get("daily_rows") or []
    return {
        "entity_rows": _normalize_entity_rows(raw_rows),
        "daily_rows": [
            {"day": row.get("day") or row.get("date") or "н/д", "return_count": round(_to_float(row.get("return_count") or row.get("count_value")), 2)}
            for row in daily_rows
        ],
    }


def build_markdown(metadata, kpis, actions, reason_rows):
    lines = [
        "# Sales Return Report",
        "",
        f"- period: `{metadata['window']['date_from']} -> {metadata['window']['date_to']}`",
        f"- primary measure: `{metadata['cubejs']['count_measure']}`",
        f"- amount dimension: `{metadata['cubejs'].get('amount_dimension') or 'н/д'}`",
        f"- rows: `{kpis['return_rows_count']}`",
        f"- total returns: `{kpis['total_returns_count']}`",
        f"- reasons: `{kpis['unique_return_reasons_count']}`",
        "",
        "## Top reasons",
        "",
    ]
    if not reason_rows:
        lines.append("- Нет строк по причинам возврата.")
    else:
        for row in reason_rows[:12]:
            suffix = f", amount `{row['amount_value']}`" if row.get("amount_value") else ""
            lines.append(f"- `{row['reason']}`: count `{row['return_count']}`{suffix}")
    lines.extend(["", "## Priority rows", ""])
    for row in (actions.get("investigate_now") or [])[:12]:
        lines.append(f"- `{row.get('seller_sku_id') or row.get('title')}` / `{row.get('reason')}`: `{row.get('return_count')}`")
    return "\n".join(lines)


def build_dashboard_payload(parsed, metadata):
    entity_rows = parsed["entity_rows"]
    daily_rows = parsed["daily_rows"]
    reason_rows = _aggregate_reasons(entity_rows)
    total_returns = round(sum(row.get("return_count") or 0 for row in entity_rows), 2)
    top_reason_value = reason_rows[0]["return_count"] if reason_rows else 0.0
    rows_without_reason = len([row for row in entity_rows if row.get("reason") == "Без причины"])
    rows_without_identity = len([row for row in entity_rows if not row.get("identity")])
    unique_reasons = len({row.get("reason") for row in entity_rows if row.get("reason")})
    top_reason_share = round((top_reason_value / total_returns) * 100.0, 2) if total_returns else 0.0
    avg_returns_per_row = round(total_returns / len(entity_rows), 2) if entity_rows else 0.0
    actions = {
        "investigate_now": entity_rows[:8],
        "reason_hotspots": reason_rows[:8],
        "identity_gaps": [row for row in entity_rows if not row.get("identity")][:8],
    }
    payload = {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "window": metadata["window"],
            "documents": {
                "sales_return_mode": metadata["mode"],
                "sales_return_source": metadata["source"],
            },
            "cubejs": metadata["cubejs"],
        },
        "kpis": {
            "return_rows_count": len(entity_rows),
            "total_returns_count": total_returns,
            "unique_return_reasons_count": unique_reasons,
            "rows_without_reason_count": rows_without_reason,
            "rows_without_identity_count": rows_without_identity,
            "top_reason_share_pct": top_reason_share,
            "avg_returns_per_row": avg_returns_per_row,
        },
        "actions": actions,
        "tables": {
            "current_winners": actions["investigate_now"],
            "profit_leaders": reason_rows[:12],
            "stockout_risk": actions["identity_gaps"],
            "stale_stock": entity_rows[:30],
        },
        "charts": {
            "reason_distribution": [{"key": row["reason"], "value": row["return_count"]} for row in reason_rows[:8]],
            "daily_returns": [{"key": row["day"], "value": row["return_count"]} for row in daily_rows[-14:]],
        },
        "insights": [],
    }
    return payload, reason_rows


def _run_live(args, member_names):
    count_measure = member_names["count_measure"]
    entity_dimensions = [
        member_names.get("reason_dimension"),
        member_names.get("sku_dimension"),
        member_names.get("product_dimension"),
    ]
    entity_query = _build_query(
        args.shop_id,
        member_names,
        measures=[count_measure],
        dimensions=entity_dimensions,
        window_days=args.window_days,
        limit=200,
        order_member=count_measure,
    )
    daily_query = _build_query(
        args.shop_id,
        member_names,
        measures=[count_measure],
        window_days=args.window_days,
        granularity="day",
        limit=400,
    )
    entity_payload = run_cubejs_query(entity_query, token=args.token)
    daily_payload = run_cubejs_query(daily_query, token=args.token)
    return _parse_live_rows(member_names, {"entity_payload": entity_payload, "daily_payload": daily_payload})


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    normalized_dir = ensure_dir(Path(args.normalized_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))
    date_from, date_to = _date_window(args.window_days)

    if args.input_json:
        input_payload = load_json(Path(args.input_json))
        parsed = _parse_input_rows(input_payload)
        cubejs_meta = load_json(Path(args.meta_json)) if args.meta_json else {}
        cubejs_members = cubejs_meta.get("cubejs") or {
            "count_measure": "SalesReturn.returns_count",
            "amount_measure": None,
            "reason_dimension": "SalesReturn.reason",
            "sku_dimension": "SalesReturn.sku",
            "title_dimension": "SalesReturn.title",
            "date_dimension": "SalesReturn.created_at",
            "shop_dimension": "SalesReturn.shop_id",
        }
        metadata = {
            "mode": "local",
            "source": str(Path(args.input_json)),
            "window": {"date_from": date_from, "date_to": date_to, "window_days": args.window_days},
            "cubejs": cubejs_members,
        }
    else:
        meta = fetch_cubejs_meta(token=args.token)
        member_names = _select_members(meta)
        parsed = _run_live(args, member_names)
        metadata = {
            "mode": "seller analytics",
            "source": "CubeJS / SalesReturn",
            "window": {"date_from": date_from, "date_to": date_to, "window_days": args.window_days},
            "cubejs": member_names,
        }

    dashboard_payload, reason_rows = build_dashboard_payload(parsed, metadata)
    markdown = build_markdown(metadata, dashboard_payload["kpis"], dashboard_payload["actions"], reason_rows)

    report_json = report_dir / f"{args.report_prefix}.json"
    report_md = report_dir / f"{args.report_prefix}.md"
    normalized_csv = normalized_dir / f"{args.report_prefix}.csv"
    dashboard_json = dashboard_dir / f"{args.report_prefix}.json"

    write_json(report_json, dashboard_payload)
    report_md.write_text(markdown, encoding="utf-8")
    write_csv_rows(normalized_csv, parsed["entity_rows"])
    write_json(dashboard_json, dashboard_payload)

    print(f"Saved: {report_json}")
    print(f"Saved: {report_md}")
    print(f"Saved: {normalized_csv}")
    print(f"Saved: {dashboard_json}")


if __name__ == "__main__":
    main()
