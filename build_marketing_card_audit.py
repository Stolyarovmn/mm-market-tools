#!/usr/bin/env python3
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION
from core.io_utils import load_json, write_json
from core.market_analysis import classify_group, price_band_label
from core.paths import DASHBOARD_DIR, NORMALIZED_DIR, REPORTS_DIR, ensure_dir, today_tag


def _latest_report_path(prefix):
    matches = sorted(REPORTS_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build unified manager-facing marketing card audit from pricing, price-trap and title SEO layers."
    )
    parser.add_argument(
        "--normalized-json",
        default=str(NORMALIZED_DIR / "weekly_operational_report_2026-04-08.json"),
    )
    parser.add_argument(
        "--pricing-json",
        default=str(_latest_report_path("dynamic_pricing") or (REPORTS_DIR / f"dynamic_pricing_{today_tag()}.json")),
    )
    parser.add_argument(
        "--price-trap-json",
        default=str(_latest_report_path("price_trap_report") or (REPORTS_DIR / f"price_trap_report_{today_tag()}.json")),
    )
    parser.add_argument(
        "--title-seo-json",
        default=str(_latest_report_path("title_seo_report") or (REPORTS_DIR / f"title_seo_report_{today_tag()}.json")),
    )
    parser.add_argument(
        "--media-json",
        default=str(_latest_report_path("media_richness_report") or (REPORTS_DIR / f"media_richness_report_{today_tag()}.json")),
    )
    parser.add_argument(
        "--description-json",
        default=str(_latest_report_path("description_seo_report") or (REPORTS_DIR / f"description_seo_report_{today_tag()}.json")),
    )
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--report-prefix", default=f"marketing_card_audit_{today_tag()}")
    parser.add_argument("--top-rows", type=int, default=60)
    return parser.parse_args()


def _load_optional(path_string):
    path = Path(path_string)
    if not path.exists():
        return {}
    return load_json(path)


def _priority_bucket(card):
    content_fix = card["media_status"] in {"needs_work", "priority_fix"} or card["description_status"] in {"needs_work", "priority_fix"}
    if card["price_trap"] and card["seo_status"] in {"needs_work", "priority_fix"}:
        return "double_fix"
    if content_fix and (card["price_trap"] or card["seo_status"] in {"needs_work", "priority_fix"}):
        return "content_plus_commerce"
    if content_fix:
        return "content_fix"
    if card["price_trap"]:
        return "price_fix"
    if card["seo_status"] in {"needs_work", "priority_fix"}:
        return "title_fix"
    return "observe"


def _priority_score(card):
    score = 0.0
    if card["price_trap"]:
        score += 40
        score += max(0.0, 15.0 - float(card.get("overshoot_rub") or 0.0))
    if card["seo_status"] == "priority_fix":
        score += 35
    elif card["seo_status"] == "needs_work":
        score += 20
    if card.get("media_status") == "priority_fix":
        score += 25
    elif card.get("media_status") == "needs_work":
        score += 12
    if card.get("description_status") == "priority_fix":
        score += 25
    elif card.get("description_status") == "needs_work":
        score += 12
    score += min(float(card.get("stock_value_sale") or 0.0) / 1000.0, 40.0)
    score += min(float(card.get("units_sold") or 0.0) * 10.0, 30.0)
    if card.get("stale_stock"):
        score += 10
    if card.get("pricing_label") == "можно агрессивно входить":
        score += 8
    elif card.get("pricing_label") == "только точечный тест":
        score += 4
    return round(score, 2)


def _action_label(card):
    if card.get("media_status") in {"needs_work", "priority_fix"} and card.get("description_status") in {"needs_work", "priority_fix"}:
        return "Усилить контент карточки"
    if card["price_trap"] and card["seo_status"] in {"needs_work", "priority_fix"}:
        return "Исправить цену и title"
    if card.get("media_status") in {"needs_work", "priority_fix"}:
        return "Усилить медиа"
    if card.get("description_status") in {"needs_work", "priority_fix"}:
        return "Переписать описание"
    if card["price_trap"]:
        return "Тест цены"
    if card["seo_status"] in {"needs_work", "priority_fix"}:
        return "Переписать title"
    return "Наблюдать"


def _action_reason(card):
    parts = []
    if card["price_trap"]:
        parts.append(
            f"цена {card.get('sale_price')} ₽ висит выше порога {card.get('threshold')} ₽ на {card.get('overshoot_rub')} ₽"
        )
    if card["seo_status"] in {"needs_work", "priority_fix"}:
        issues = ", ".join(card.get("seo_issues") or []) or "title требует улучшения"
        parts.append(f"SEO-сигнал: {issues}")
    if card.get("media_status") in {"needs_work", "priority_fix"}:
        parts.append(f"media: {card.get('media_status')}, фото {card.get('photo_count', 'н/д')}, spec {card.get('spec_count', 'н/д')}")
    if card.get("description_status") in {"needs_work", "priority_fix"}:
        parts.append(f"description: {card.get('description_status')}, {card.get('description_chars', 'н/д')} симв.")
    if card.get("pricing_label"):
        parts.append(f"рыночный контекст: {card.get('pricing_label')}")
    return "; ".join(parts) if parts else "нужен ручной контроль"


def _top_rows(rows, predicate, limit=8):
    return [row for row in rows if predicate(row)][:limit]


def build_markdown(rows, summary, args):
    lines = [
        "# Marketing Card Audit",
        "",
        f"- normalized source: `{args.normalized_json}`",
        f"- pricing source: `{args.pricing_json}`",
        f"- price trap source: `{args.price_trap_json}`",
        f"- title SEO source: `{args.title_seo_json}`",
        f"- media source: `{args.media_json}`",
        f"- description source: `{args.description_json}`",
        f"- audited cards: `{summary['audited_cards_count']}`",
        f"- priority cards: `{summary['priority_cards_count']}`",
        f"- price traps: `{summary['price_trap_cards_count']}`",
        f"- seo needs work: `{summary['seo_needs_work_count']}`",
        "",
        "## Top priority cards",
        "",
    ]
    if not rows:
        lines.append("- Нет карточек с marketing-сигналом.")
        return "\n".join(lines)
    for row in rows[:20]:
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- action: `{row['action_label']}`",
                f"- priority score: `{row['priority_score']}`",
                f"- group / price band: `{row['group']} / {row['price_band']}`",
                f"- sale price: `{row['sale_price']} ₽`",
                f"- SEO: `{row['seo_status']}` / score `{row['seo_score']}`",
                f"- media: `{row['media_status']}` / score `{row['media_score']}` / фото `{row['photo_count']}` / spec `{row['spec_count']}`",
                f"- description: `{row['description_status']}` / score `{row['description_score']}` / `{row['description_chars']}` символов",
                f"- price trap: `{row['price_trap']}`",
                f"- reason: `{row['action_reason']}`",
                "",
            ]
        )
    return "\n".join(lines)


def build_dashboard_payload(rows, summary, args):
    actions = {
        "fix_now": _top_rows(rows, lambda row: row["priority_bucket"] == "double_fix"),
        "price_tests": _top_rows(rows, lambda row: row["price_trap"]),
        "title_fixes": _top_rows(rows, lambda row: row["seo_status"] in {"needs_work", "priority_fix"}),
        "market_supported": _top_rows(rows, lambda row: row.get("pricing_label") in {"можно агрессивно входить", "входить по рынку"}),
        "content_fixes": _top_rows(rows, lambda row: row.get("media_status") in {"needs_work", "priority_fix"} or row.get("description_status") in {"needs_work", "priority_fix"}),
    }
    charts = {
        "priority_buckets": [
            {"key": "Цена + title", "value": summary["double_fix_count"]},
            {"key": "Контент + commerce", "value": summary["content_plus_commerce_count"]},
            {"key": "Контент", "value": summary["content_fix_count"]},
            {"key": "Только цена", "value": summary["price_fix_count"]},
            {"key": "Только title", "value": summary["title_fix_count"]},
            {"key": "Наблюдать", "value": summary["observe_count"]},
        ],
        "seo_status_counts": [
            {"key": "Needs work", "value": summary["seo_needs_work_count"]},
            {"key": "Priority fix", "value": summary["seo_priority_fix_count"]},
            {"key": "Strong", "value": summary["seo_strong_count"]},
        ],
        "issue_type_counts": [
            {"key": "Price trap", "value": summary["price_trap_cards_count"]},
            {"key": "Main noun late", "value": summary["main_noun_late_count"]},
            {"key": "Entity late", "value": summary["entity_late_count"]},
            {"key": "Generic lead", "value": summary["generic_lead_count"]},
            {"key": "Media needs work", "value": summary["media_needs_work_count"]},
            {"key": "Thin content", "value": summary["description_needs_work_count"]},
        ],
    }
    insights = []
    if summary["double_fix_count"] > 0:
        insights.append({
            "title": "Есть карточки с двойной проблемой",
            "text": f"Нашлось {summary['double_fix_count']} карточек, где одновременно виден ценовой trap и слабый title. Это лучший список для быстрых побед без смены ассортимента.",
            "tone": "warn",
        })
    if summary["price_trap_cards_count"] > 0:
        insights.append({
            "title": "Психологические пороги уже дают действия",
            "text": f"В {summary['price_trap_cards_count']} карточках цена находится чуть выше сильного порога. Это дешёвый тест, особенно когда товар уже лежит на складе.",
            "tone": "good",
        })
    if summary["seo_needs_work_count"] > 0:
        insights.append({
            "title": "Title-слой тоже даёт заметный резерв",
            "text": f"{summary['seo_needs_work_count']} карточек выглядят слабо по title-priority. Это не guarantee роста, но хороший пласт для content-улучшений без новой закупки.",
            "tone": "warn",
        })
    if summary["market_supported_cards_count"] > 0:
        insights.append({
            "title": "Часть карточек лежит в окнах с рабочей рыночной экономикой",
            "text": f"{summary['market_supported_cards_count']} карточек попали в группы/ценовые коридоры, где рынок в целом поддерживает вход или тест по вашей марже.",
            "tone": "good",
        })
    if summary["content_fix_count"] > 0 or summary["content_plus_commerce_count"] > 0:
        insights.append({
            "title": "Контент карточки теперь тоже попал в общий приоритет",
            "text": f"В unified audit уже видно {summary['content_fix_count']} чисто контентных карточек и {summary['content_plus_commerce_count']} карточек, где контентная и коммерческая проблема совпадают. Это сокращает разрыв между marketing- и content-работой.",
            "tone": "good",
        })
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "window": {},
            "documents": {},
            "marketing_audit": {
                "mode": "manager-facing combined audit",
                "normalized_json": args.normalized_json,
                "pricing_json": args.pricing_json,
                "price_trap_json": args.price_trap_json,
                "title_seo_json": args.title_seo_json,
                "media_json": args.media_json,
                "description_json": args.description_json,
            },
        },
        "kpis": {
            "total_skus": summary["audited_cards_count"],
            "sold_skus": summary["cards_with_sales_count"],
            "revenue_total": summary["priority_stock_value_sale_total"],
            "gross_profit_total": summary["priority_gross_profit_total"],
            "stockout_risk_count": 0,
            "stale_stock_count": summary["stale_priority_cards_count"],
            "priority_cards_count": summary["priority_cards_count"],
            "price_trap_cards_count": summary["price_trap_cards_count"],
            "seo_needs_work_count": summary["seo_needs_work_count"],
            "seo_priority_fix_count": summary["seo_priority_fix_count"],
            "market_supported_cards_count": summary["market_supported_cards_count"],
            "double_fix_count": summary["double_fix_count"],
            "content_plus_commerce_count": summary["content_plus_commerce_count"],
            "content_fix_count": summary["content_fix_count"],
            "media_needs_work_count": summary["media_needs_work_count"],
            "description_needs_work_count": summary["description_needs_work_count"],
        },
        "actions": actions,
        "tables": {
            "priority_cards": rows[: min(len(rows), 25)],
            "price_traps": _top_rows(rows, lambda row: row["price_trap"], 25),
            "seo_fixes": _top_rows(rows, lambda row: row["seo_status"] in {"needs_work", "priority_fix"}, 25),
            "content_fixes": _top_rows(rows, lambda row: row.get("media_status") in {"needs_work", "priority_fix"} or row.get("description_status") in {"needs_work", "priority_fix"}, 25),
            "market_context": _top_rows(rows, lambda row: bool(row.get("pricing_label")), 25),
        },
        "charts": charts,
        "insights": insights,
    }


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))

    normalized = _load_optional(args.normalized_json)
    pricing = _load_optional(args.pricing_json)
    price_trap = _load_optional(args.price_trap_json)
    title_seo = _load_optional(args.title_seo_json)
    media_audit = _load_optional(args.media_json)
    description_audit = _load_optional(args.description_json)

    source_rows = normalized.get("rows") or []
    source_map = {row.get("key"): row for row in source_rows if row.get("key")}
    price_trap_map = {row.get("key"): row for row in (price_trap.get("rows") or []) if row.get("key")}
    title_seo_map = {row.get("key"): row for row in (title_seo.get("rows") or []) if row.get("key")}
    media_map = {row.get("key"): row for row in (media_audit.get("rows") or []) if row.get("key")}
    description_map = {row.get("key"): row for row in (description_audit.get("rows") or []) if row.get("key")}
    pricing_map = {}
    for row in pricing.get("rows") or []:
        pricing_map[(row.get("group"), row.get("price_band"))] = row

    merged = []
    candidate_keys = list(dict.fromkeys(list(price_trap_map.keys()) + list(title_seo_map.keys())))
    if not candidate_keys:
        candidate_keys = [row.get("key") for row in source_rows if row.get("key")]
    for key in candidate_keys:
        source = source_map.get(key)
        if not source:
            continue
        title = source.get("title")
        if not key or not title:
            continue
        group = classify_group(title)
        price_band = price_band_label(source.get("sale_price"))
        trap = price_trap_map.get(key) or {}
        seo = title_seo_map.get(key) or {}
        media = media_map.get(key) or {}
        description = description_map.get(key) or {}
        pricing_row = pricing_map.get((group, price_band)) or {}
        card = {
            "key": key,
            "product_id": source.get("product_id"),
            "barcode": source.get("barcode"),
            "title": title,
            "group": group,
            "price_band": price_band,
            "sale_price": float(source.get("sale_price") or 0.0),
            "units_sold": source.get("units_sold", 0),
            "gross_profit": float(source.get("gross_profit") or 0.0),
            "net_revenue": float(source.get("net_revenue") or 0.0),
            "stock_value_sale": float(source.get("stock_value_sale") or 0.0),
            "total_stock": int(source.get("total_stock") or 0),
            "stale_stock": bool(source.get("stale_stock")),
            "current_winner": bool(source.get("current_winner")),
            "price_trap": bool(trap),
            "threshold": trap.get("threshold"),
            "overshoot_rub": trap.get("overshoot_rub"),
            "overshoot_pct": trap.get("overshoot_pct"),
            "suggested_threshold_price": trap.get("suggested_price"),
            "seo_status": seo.get("seo_status", "strong"),
            "seo_score": seo.get("seo_score", 100),
            "seo_issues": seo.get("issues") or [],
            "seo_recommendations": seo.get("recommendations") or [],
            "media_status": media.get("media_status", "strong"),
            "media_score": media.get("media_score", 100),
            "media_issues": media.get("issues") or [],
            "media_recommendations": media.get("recommendations") or [],
            "photo_count": media.get("photo_count", 0),
            "spec_count": media.get("spec_count", 0),
            "video_count": media.get("video_count", 0),
            "description_status": description.get("description_status", "strong"),
            "description_score": description.get("description_score", 100),
            "description_issues": description.get("issues") or [],
            "description_recommendations": description.get("recommendations") or [],
            "description_chars": description.get("description_chars", 0),
            "pricing_label": pricing_row.get("pricing_label"),
            "pricing_reason": pricing_row.get("pricing_reason"),
            "pricing_suggested_price": pricing_row.get("suggested_price"),
            "avg_market_price": pricing_row.get("avg_market_price"),
            "market_margin_fit_pct": pricing_row.get("market_margin_fit_pct"),
            "entry_strategy_label": pricing_row.get("entry_strategy_label"),
        }
        if (
            not card["price_trap"]
            and card["seo_status"] == "strong"
            and card["media_status"] == "strong"
            and card["description_status"] == "strong"
        ):
            continue
        card["priority_bucket"] = _priority_bucket(card)
        card["priority_score"] = _priority_score(card)
        card["action_label"] = _action_label(card)
        card["action_reason"] = _action_reason(card)
        merged.append(card)

    merged.sort(
        key=lambda row: (
            row["priority_score"],
            row["units_sold"],
            row["stock_value_sale"],
        ),
        reverse=True,
    )
    if args.top_rows and len(merged) > args.top_rows:
        merged = merged[: args.top_rows]

    priority_counter = Counter(row["priority_bucket"] for row in merged)
    summary = {
        "audited_cards_count": len(merged),
        "priority_cards_count": len(merged),
        "cards_with_sales_count": sum(1 for row in merged if (row.get("units_sold") or 0) > 0),
        "price_trap_cards_count": sum(1 for row in merged if row["price_trap"]),
        "seo_needs_work_count": sum(1 for row in merged if row["seo_status"] == "needs_work"),
        "seo_priority_fix_count": sum(1 for row in merged if row["seo_status"] == "priority_fix"),
        "seo_strong_count": sum(1 for row in merged if row["seo_status"] == "strong"),
        "market_supported_cards_count": sum(
            1 for row in merged if row.get("pricing_label") in {"можно агрессивно входить", "входить по рынку"}
        ),
        "double_fix_count": priority_counter.get("double_fix", 0),
        "content_plus_commerce_count": priority_counter.get("content_plus_commerce", 0),
        "content_fix_count": priority_counter.get("content_fix", 0),
        "price_fix_count": priority_counter.get("price_fix", 0),
        "title_fix_count": priority_counter.get("title_fix", 0),
        "observe_count": priority_counter.get("observe", 0),
        "media_needs_work_count": sum(1 for row in merged if row["media_status"] in {"needs_work", "priority_fix"}),
        "description_needs_work_count": sum(1 for row in merged if row["description_status"] in {"needs_work", "priority_fix"}),
        "stale_priority_cards_count": sum(1 for row in merged if row.get("stale_stock")),
        "priority_stock_value_sale_total": round(sum(float(row.get("stock_value_sale") or 0.0) for row in merged), 2),
        "priority_gross_profit_total": round(sum(float(row.get("gross_profit") or 0.0) for row in merged), 2),
        "main_noun_late_count": sum(1 for row in merged if "main_noun_late" in (row.get("seo_issues") or [])),
        "entity_late_count": sum(1 for row in merged if "entity_late" in (row.get("seo_issues") or [])),
        "generic_lead_count": sum(1 for row in merged if "generic_lead" in (row.get("seo_issues") or [])),
    }

    result = {
        "generated_from": {
            "normalized_json": args.normalized_json,
            "pricing_json": args.pricing_json,
            "price_trap_json": args.price_trap_json,
            "title_seo_json": args.title_seo_json,
            "media_json": args.media_json,
            "description_json": args.description_json,
        },
        "summary": summary,
        "rows": merged,
    }

    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    dashboard_path = dashboard_dir / f"{args.report_prefix}.json"
    write_json(json_path, result)
    md_path.write_text(build_markdown(merged, summary, args), encoding="utf-8")
    write_json(dashboard_path, build_dashboard_payload(merged, summary, args))
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {dashboard_path}")


if __name__ == "__main__":
    main()
