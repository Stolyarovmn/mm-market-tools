#!/usr/bin/env python3
"""Aggregate dashboard reports into the daily action plan payload.

This script bridges the existing report bundles in ``data/dashboard`` with the
SQLite/Pages UI contract used by ``scripts/build_sqlite.py`` and
``docs/index.html``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from core.reply_generator import generate_template_reply, load_config


ROOT = Path(__file__).parent
DEFAULT_INDEX = ROOT / "data" / "dashboard" / "index.json"
DEFAULT_OUTPUT = ROOT / "data" / "dashboard" / "daily_action_plan.json"
REPORTS_DIR = ROOT / "reports"

REASON_LABELS = {
    "REGULAR": "Стандартный возврат",
    "BAD_QUALITY": "Проблема с качеством",
    "DAMAGED": "Товар повреждён",
    "WRONG_ITEM": "Не тот товар",
    "Без причины": "Без указания причины",
}

REASON_ACTIONS = {
    "REGULAR": "Проверить карточку, фото и упаковку на предмет ложных ожиданий покупателя.",
    "BAD_QUALITY": "Проверить партию, себестоимость и последние жалобы на качество.",
    "DAMAGED": "Проверить упаковку и процесс отгрузки, чтобы исключить повреждения в пути.",
    "WRONG_ITEM": "Проверить маркировку и комплектацию перед следующими отгрузками.",
    "Без причины": "Проверить карточку товара и историю возвратов для уточнения причины.",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_report(index_payload: dict, kind: str) -> tuple[str | None, dict | None]:
    item = (index_payload.get("latest_by_kind") or {}).get(kind)
    if not item:
        return None, None
    report_path = ROOT / item["file_path"]
    if not report_path.exists():
        return item["file_name"], None
    return item["file_name"], read_json(report_path)


def insight_to_message(source_name: str, insight: dict) -> dict:
    tone = (insight.get("tone") or "info").lower()
    severity = "info"
    if tone in {"warn", "warning"}:
        severity = "warn"
    elif tone in {"bad", "danger", "critical", "high"}:
        severity = "high"
    title = insight.get("title")
    text = insight.get("text") or insight.get("message") or ""
    message = f"{title}: {text}" if title else text
    return {"source": source_name, "severity": severity, "message": message.strip()}


def maybe_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def score_band(value: float | None, default: float) -> float:
    if value is None:
        return default
    return round(float(value), 2)


def make_price_fix_actions(report: dict) -> list[dict]:
    rows = ((report.get("actions") or {}).get("price_tests") or [])[:8]
    out = []
    for row in rows:
        current = maybe_number(row.get("sale_price"))
        suggested = maybe_number(row.get("suggested_threshold_price"))
        market = maybe_number(row.get("avg_market_price"))
        priority = score_band(row.get("priority_score"), 70.0)
        meta = {
            "total_stock": row.get("total_stock"),
            "stale_stock": bool(row.get("stale_stock")),
            "market_median_price": market,
        }
        if current is not None and market:
            meta["price_vs_market_pct"] = round(((current - market) / market) * 100.0, 2)
        out.append({
            "action_type": "price_fix",
            "title": row.get("title") or row.get("key") or f"product-{row.get('product_id')}",
            "group": row.get("group"),
            "headline": row.get("action_label") or "Сдвинуть цену к психологическому порогу",
            "detail": row.get("action_reason") or "Цена висит немного выше рабочего порога.",
            "current_value": current,
            "suggested_value": suggested,
            "priority_score": priority,
            "compound_score": round(priority + 5.0, 2),
            "quick_win": True,
            "entity_key": row.get("key"),
            "product_id": row.get("product_id"),
            "meta": meta,
        })
    return out


def make_title_actions(report: dict) -> list[dict]:
    rows = ((report.get("actions") or {}).get("title_fixes") or [])[:8]
    out = []
    for row in rows:
        priority = score_band(row.get("priority_score"), 35.0)
        detail_parts = []
        if row.get("action_reason"):
            detail_parts.append(row["action_reason"])
        recs = row.get("seo_recommendations") or []
        if recs:
            detail_parts.append(" ".join(recs))
        out.append({
            "action_type": "title_seo",
            "title": row.get("title") or row.get("key") or f"product-{row.get('product_id')}",
            "group": row.get("group"),
            "headline": row.get("action_label") or "Переписать title карточки",
            "detail": " ".join(detail_parts).strip(),
            "current_value": None,
            "suggested_value": None,
            "priority_score": priority,
            "compound_score": priority,
            "quick_win": True,
            "entity_key": row.get("key"),
            "product_id": row.get("product_id"),
            "meta": {
                "total_stock": row.get("total_stock"),
                "stale_stock": bool(row.get("stale_stock")),
                "market_median_price": maybe_number(row.get("avg_market_price")),
            },
        })
    return out


def make_price_strategy_actions(report: dict) -> list[dict]:
    actions = report.get("actions") or {}
    buckets = ["aggressive_price", "price_at_market", "test_carefully"]
    out = []
    for bucket in buckets:
        for row in (actions.get(bucket) or [])[:8]:
            orders = maybe_number(row.get("orders_sum")) or 0.0
            score = min(95.0, 45.0 + (orders / 250.0))
            out.append({
                "action_type": "price_strategy",
                "title": f"{row.get('group') or 'Группа'} · {row.get('price_band') or 'price band'}",
                "group": row.get("group"),
                "headline": row.get("pricing_label") or "Пересмотреть рыночную цену",
                "detail": row.get("pricing_reason") or "Пересчитать безопасное окно входа по рынку.",
                "current_value": maybe_number(row.get("avg_market_price")),
                "suggested_value": maybe_number(row.get("suggested_price")),
                "priority_score": round(score, 2),
                "compound_score": round(score + (5.0 if bucket == "aggressive_price" else 0.0), 2),
                "quick_win": bucket == "aggressive_price",
                "entity_key": f"{row.get('group')}-{row.get('price_band')}",
                "product_id": None,
                "meta": {
                    "market_median_price": maybe_number(row.get("avg_market_price")),
                    "price_vs_market_pct": maybe_number(row.get("price_gap_pct")),
                },
            })
    return out[:8]


def make_return_actions(report: dict) -> tuple[list[dict], list[dict]]:
    review_rows = []
    plan_rows = []
    config = load_config()
    rows = ((report.get("actions") or {}).get("investigate_now") or [])[:8]
    for row in rows:
        reason_code = row.get("reason") or "Без причины"
        label = REASON_LABELS.get(reason_code, reason_code)
        review_item = {
            "kind": "review",
            "product_title": row.get("title") or "товар",
            "rating": None,
            "text": f"Возврат по причине {label}",
        }
        template = generate_template_reply(review_item, config)
        action_for_seller = REASON_ACTIONS.get(reason_code, REASON_ACTIONS["Без причины"])
        review_rows.append({
            "product_id": str(row.get("product_id") or ""),
            "sku": row.get("sku") or row.get("seller_sku_id") or "",
            "title": row.get("title") or row.get("identity") or "",
            "return_reason_code": reason_code,
            "reason_label": label,
            "return_count": int(maybe_number(row.get("return_count")) or 0),
            "template_response": template,
            "action_for_seller": action_for_seller,
            "priority": "high" if (maybe_number(row.get("return_count")) or 0) >= 2 else "medium",
        })
        count = maybe_number(row.get("return_count")) or 0.0
        score = min(85.0, 50.0 + count * 10.0)
        plan_rows.append({
            "action_type": "return_investigate",
            "title": row.get("title") or row.get("identity") or f"return-{row.get('product_id')}",
            "group": label,
            "headline": f"Разобрать возвраты: {label}",
            "detail": action_for_seller,
            "current_value": count,
            "suggested_value": None,
            "priority_score": round(score, 2),
            "compound_score": round(score, 2),
            "quick_win": False,
            "entity_key": row.get("identity") or row.get("sku"),
            "product_id": row.get("product_id"),
            "meta": {},
        })
    return review_rows, plan_rows


def make_storage_actions(report: dict) -> list[dict]:
    rows = ((report.get("actions") or {}).get("markdown_candidates") or [])[:8]
    out = []
    for row in rows:
        amount = maybe_number(row.get("amount"))
        score = min(90.0, 40.0 + ((amount or 0.0) / 250000.0))
        out.append({
            "action_type": "storage_cost",
            "title": row.get("title") or row.get("identity") or "SKU без названия",
            "group": "Платное хранение",
            "headline": "Проверить складской хвост и вариант уценки",
            "detail": "Платное хранение уже заметно в расходах; проверьте распродажу, комплектность и точность идентификации SKU.",
            "current_value": amount,
            "suggested_value": None,
            "priority_score": round(score, 2),
            "compound_score": round(score, 2),
            "quick_win": False,
            "entity_key": row.get("identity") or row.get("title"),
            "product_id": None,
            "meta": {},
        })
    return out


def load_cached_api_status() -> dict:
    files = sorted(REPORTS_DIR.glob("token_validation_*.json"))
    if not files:
        return {
            "checked_at": None,
            "shop_id": 98,
            "token_status": "unknown",
            "token_expires_moscow": None,
            "cubes": 0,
            "existing_documents": 0,
            "endpoints": [],
            "gaps": [],
        }
    payload = read_json(files[-1])
    docs_req = payload.get("documents_requests") or {}
    docs_create = payload.get("documents_create") or {}
    gaps = []
    if not docs_create.get("ok"):
        gaps.append({
            "name": "documents_create",
            "status": "todo",
            "note": "documents/create пока не даёт стабильный контракт; используем reuse completed reports.",
        })
    return {
        "checked_at": payload.get("token_health", {}).get("expires_at"),
        "shop_id": payload.get("shop_id", 98),
        "token_status": payload.get("token_health", {}).get("status", "unknown"),
        "token_expires_moscow": payload.get("token_health", {}).get("expires_at_moscow"),
        "cubes": payload.get("cubejs_meta", {}).get("cubes", 0),
        "existing_documents": docs_req.get("rows") or docs_req.get("total_elements") or 0,
        "endpoints": [
            {
                "url": "cubejs-api/v1/meta",
                "method": "GET",
                "status": "ok" if payload.get("cubejs_meta", {}).get("ok") else "todo",
                "note": "Кубы аналитики доступны." if payload.get("cubejs_meta", {}).get("ok") else "Meta endpoint требует проверки.",
            },
            {
                "url": "api/seller/documents/requests",
                "method": "GET",
                "status": "ok" if docs_req.get("ok") else "todo",
                "note": "Используем completed documents как основной источник seller reports.",
            },
            {
                "url": "api/seller/documents/create",
                "method": "POST",
                "status": "fix" if not docs_create.get("ok") else "ok",
                "note": "Validation failed, поэтому workflow не должен зависеть от create-контракта." if not docs_create.get("ok") else "create работает",
            },
        ],
        "gaps": gaps,
    }


def collect_api_status(shop_id: int, offline: bool, offline_fallback: bool) -> dict:
    if offline:
        return load_cached_api_status()

    token = None
    for env_name in ("KE_TOKEN", "CUBEJS_TOKEN", "MM_ANALYTICS_COOKIE"):
        value = __import__("os").environ.get(env_name)
        if value:
            token = value
            break

    if not token:
        if offline_fallback:
            return load_cached_api_status()
        raise RuntimeError("No token found for online api_status collection.")

    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            "python3",
            str(ROOT / "validate_token_integrations.py"),
            "--token",
            token,
            "--shop-id",
            str(shop_id),
            "--report-dir",
            tmp,
            "--report-prefix",
            "daily_action_plan_api",
        ]
        try:
            subprocess.run(cmd, cwd=str(ROOT), check=True, capture_output=True, text=True)
            files = sorted(Path(tmp).glob("daily_action_plan_api*.json"))
            if not files:
                raise RuntimeError("validate_token_integrations.py produced no report")
            payload = read_json(files[-1])
            docs_req = payload.get("documents_requests") or {}
            docs_create = payload.get("documents_create") or {}
            gaps = []
            if not docs_create.get("ok"):
                gaps.append({
                    "name": "documents_create",
                    "status": "todo",
                    "note": "documents/create пока нестабилен; используем completed reports и offline bundles.",
                })
            return {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "shop_id": payload.get("shop_id", shop_id),
                "token_status": payload.get("token_health", {}).get("status", "unknown"),
                "token_expires_moscow": payload.get("token_health", {}).get("expires_at_moscow"),
                "cubes": payload.get("cubejs_meta", {}).get("cubes", 0),
                "existing_documents": docs_req.get("rows") or docs_req.get("total_elements") or 0,
                "endpoints": [
                    {"url": "cubejs-api/v1/meta", "method": "GET", "status": "ok" if payload.get("cubejs_meta", {}).get("ok") else "todo", "note": "Live check from validate_token_integrations.py"},
                    {"url": "cubejs-api/v1/load", "method": "POST", "status": "ok" if payload.get("cubejs_load", {}).get("ok") else "todo", "note": "Live query health check"},
                    {"url": "api/seller/documents/requests", "method": "GET", "status": "ok" if docs_req.get("ok") else "todo", "note": "Completed reports visibility"},
                ],
                "gaps": gaps,
            }
        except Exception:
            if offline_fallback:
                return load_cached_api_status()
            raise


def load_applied_actions() -> dict:
    path = ROOT / "data" / "local" / "applied_actions.json"
    if not path.exists():
        return {"summary": {"total_entries": 0, "pending_count": 0, "measured_count": 0}, "entries": []}
    data = read_json(path)
    entries = data if isinstance(data, list) else (data.get("entries") or [])
    pending = len([e for e in entries if e.get("status") == "pending"])
    measured = len([e for e in entries if e.get("status") == "measured"])
    return {
        "summary": {"total_entries": len(entries), "pending_count": pending, "measured_count": measured},
        "entries": entries,
    }


def load_blockers() -> list[dict]:
    path = ROOT / "data" / "local" / "blockers.json"
    if path.exists():
        data = read_json(path)
        if isinstance(data, list):
            return data
    return [
        {
            "id": "B-031",
            "sev": "med",
            "title": "Workflow still depends on completed dashboard bundles",
            "body": "Automation can rebuild SQLite and Pages, but some source reports still rely on completed seller documents and cached offline bundles.",
        }
    ]


def load_iteration() -> dict:
    path = ROOT / "data" / "local" / "iteration.json"
    if path.exists():
        data = read_json(path)
        if isinstance(data, dict):
            return data
    return {
        "number": "012",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "uncertainty": 0.32,
    }


def build_plan(index_path: Path, output_path: Path, offline: bool, offline_fallback: bool, shop_id: int) -> dict:
    index_payload = read_json(index_path)

    report_specs = {
        "marketing_card_audit": latest_report(index_payload, "marketing_card_audit"),
        "dynamic_pricing": latest_report(index_payload, "dynamic_pricing"),
        "sales_return_report": latest_report(index_payload, "sales_return_report"),
        "paid_storage_report": latest_report(index_payload, "paid_storage_report"),
        "weekly_operational": latest_report(index_payload, "weekly_operational"),
        "competitor_market_analysis": latest_report(index_payload, "competitor_market_analysis"),
    }

    plan_actions = []
    plan_insights = []
    sources_used = []
    sources_skipped = []

    marketing_name, marketing = report_specs["marketing_card_audit"]
    if marketing:
        plan_actions.extend(make_price_fix_actions(marketing))
        plan_actions.extend(make_title_actions(marketing))
        plan_insights.extend(insight_to_message("plan", item) for item in (marketing.get("insights") or [])[:4])
        sources_used.append(f"marketing_card_audit ({len(plan_actions)} actions -> {marketing_name})")
    else:
        sources_skipped.append("marketing_card_audit")

    pricing_name, pricing = report_specs["dynamic_pricing"]
    if pricing:
        pricing_actions = make_price_strategy_actions(pricing)
        plan_actions.extend(pricing_actions)
        plan_insights.extend(insight_to_message("plan", item) for item in (pricing.get("insights") or [])[:3])
        sources_used.append(f"dynamic_pricing ({len(pricing_actions)} actions -> {pricing_name})")
    else:
        sources_skipped.append("dynamic_pricing")

    returns_name, returns = report_specs["sales_return_report"]
    review_rows = []
    if returns:
        review_rows, return_plan = make_return_actions(returns)
        plan_actions.extend(return_plan)
        sources_used.append(f"sales_return_report ({len(review_rows)} review rows -> {returns_name})")
    else:
        sources_skipped.append("sales_return_report")

    storage_name, storage = report_specs["paid_storage_report"]
    if storage:
        storage_actions = make_storage_actions(storage)
        plan_actions.extend(storage_actions)
        plan_insights.extend(insight_to_message("plan", item) for item in (storage.get("insights") or [])[:3])
        sources_used.append(f"paid_storage_report ({len(storage_actions)} actions -> {storage_name})")
    else:
        sources_skipped.append("paid_storage_report")

    plan_actions = sorted(plan_actions, key=lambda item: item.get("compound_score") or 0, reverse=True)
    for rank, item in enumerate(plan_actions, start=1):
        item["rank"] = rank

    by_type_count = Counter(item["action_type"] for item in plan_actions)
    quick_wins_count = len([item for item in plan_actions if item.get("quick_win")])
    potential_price_shift = 0.0
    for item in plan_actions:
        cur = item.get("current_value")
        sug = item.get("suggested_value")
        if isinstance(cur, (int, float)) and isinstance(sug, (int, float)) and cur > sug:
            potential_price_shift += cur - sug

    top_slice = plan_actions[:10]
    zero_stock = len([item for item in top_slice if ((item.get("meta") or {}).get("total_stock") == 0)])
    stockout_risk = len([item for item in top_slice if (((item.get("meta") or {}).get("total_stock") or 9999) < 5)])
    competitor_aware = len([item for item in top_slice if (item.get("meta") or {}).get("market_median_price") is not None])

    api_status = collect_api_status(shop_id=shop_id, offline=offline, offline_fallback=offline_fallback)
    applied_actions = load_applied_actions()
    blockers = load_blockers()
    iteration = load_iteration()

    stock_source_name, _stock = report_specs["weekly_operational"]
    comp_source_name, _comp = report_specs["competitor_market_analysis"]

    payload = {
        "plan": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kpis": {
                "actions_in_plan": len(plan_actions),
                "quick_wins_count": quick_wins_count,
                "by_type_count": dict(by_type_count),
                "potential_price_shift_rub": round(potential_price_shift, 2),
                "zero_stock_in_top": zero_stock,
                "stockout_risk_in_top": stockout_risk,
                "competitor_aware_in_top": competitor_aware,
            },
            "metadata": {
                "sources_used": sources_used,
                "sources_skipped": sources_skipped,
                "stock_context_source": stock_source_name,
                "competitor_context_source": comp_source_name,
                "stock_annotated": len([item for item in plan_actions if (item.get("meta") or {}).get("total_stock") is not None]),
                "competitor_annotated": len([item for item in plan_actions if (item.get("meta") or {}).get("market_median_price") is not None]),
            },
            "insights": [{"severity": item["severity"], "message": item["message"]} for item in plan_insights],
            "actions": plan_actions,
        },
        "review_booster": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kpis": {
                "responses_suggested": len(review_rows),
                "high_priority_responses": len([row for row in review_rows if row.get("priority") == "high"]),
                "reason_coverage": len({row.get("return_reason_code") for row in review_rows}),
            },
            "insights": [
                {
                    "severity": "info" if review_rows else "warn",
                    "message": "Шаблоны ответов собраны из sales_return_report." if review_rows else "Нет строк возвратов для review booster.",
                }
            ],
            "rows": review_rows,
        },
        "applied_actions": applied_actions,
        "api_status": api_status,
        "blockers": blockers,
        "iteration": iteration,
    }
    write_json(output_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--shop-id", type=int, default=98)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--offline-fallback", action="store_true")
    args = parser.parse_args()

    payload = build_plan(
        index_path=Path(args.index),
        output_path=Path(args.output),
        offline=args.offline,
        offline_fallback=args.offline_fallback,
        shop_id=args.shop_id,
    )
    print(
        "daily_action_plan built:",
        f"{len(payload['plan']['actions'])} actions,",
        f"{len(payload['review_booster']['rows'])} review rows -> {args.output}",
    )


if __name__ == "__main__":
    main()
