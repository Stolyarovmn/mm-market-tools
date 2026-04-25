#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path

from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION
from core.io_utils import load_json, write_json
from core.paths import DASHBOARD_DIR, REPORTS_DIR, ensure_dir, today_tag


def parse_args():
    parser = argparse.ArgumentParser(description="Build recommendation-first dynamic pricing report from market economics.")
    parser.add_argument("--market-json", default="/home/user/mm-market-tools/data/dashboard/market_rescored_after_cogs_2026-04-09b.json")
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--target-margin-pct", type=float, default=35.0)
    parser.add_argument("--report-prefix", default=f"dynamic_pricing_{today_tag()}")
    return parser.parse_args()


def required_price_for_margin(cogs, target_margin_pct):
    if not cogs or target_margin_pct >= 100:
        return None
    return round(float(cogs) / (1.0 - (float(target_margin_pct) / 100.0)), 2)


def recommend_window(row, target_margin_pct):
    cogs = row.get("my_avg_cogs")
    avg_price = float(row.get("avg_price") or 0.0)
    if not cogs or not avg_price:
        return None
    min_safe_price = required_price_for_margin(cogs, target_margin_pct)
    if not min_safe_price:
        return None
    margin_fit = row.get("market_margin_fit_pct")
    gap = row.get("price_gap_pct")
    suggested_price = None
    label = "наблюдать"
    reason = "пока мало данных"

    if margin_fit is not None and margin_fit >= target_margin_pct + 8:
        suggested_price = round(max(min_safe_price, avg_price * 0.98), 2)
        label = "можно агрессивно входить"
        reason = "рынок оставляет запас маржи даже при цене чуть ниже среднего"
    elif margin_fit is not None and margin_fit >= target_margin_pct:
        suggested_price = round(max(min_safe_price, avg_price), 2)
        label = "входить по рынку"
        reason = "средняя цена рынка уже совместима с целевой маржой"
    elif margin_fit is not None and margin_fit >= max(20.0, target_margin_pct - 10):
        suggested_price = round(max(min_safe_price, avg_price * 1.03), 2)
        label = "только точечный тест"
        reason = "вход возможен, но цена должна быть осторожнее среднего рынка"
    else:
        suggested_price = round(min_safe_price, 2)
        label = "не демпинговать"
        reason = "для целевой маржи нужна цена заметно выше текущего рынка"

    return {
        "group": row.get("group"),
        "price_band": row.get("price_band"),
        "avg_market_price": round(avg_price, 2),
        "my_avg_cogs": round(float(cogs), 2),
        "target_margin_pct": target_margin_pct,
        "min_safe_price": min_safe_price,
        "suggested_price": suggested_price,
        "market_margin_fit_pct": margin_fit,
        "price_gap_pct": gap,
        "entry_strategy_label": row.get("entry_strategy_label"),
        "pricing_label": label,
        "pricing_reason": reason,
        "orders_sum": row.get("orders_sum", 0),
        "dominance_hhi": row.get("dominance_hhi"),
        "novelty_proxy_index": row.get("novelty_proxy_index"),
    }


def build_markdown(rows, target_margin_pct):
    lines = [
        "# Dynamic Pricing Report",
        "",
        f"- target margin: `{target_margin_pct}%`",
        f"- priced windows: `{len(rows)}`",
        "",
        "## Recommendations",
        "",
    ]
    if not rows:
        lines.append("- Нет окон, где уже хватает economics coverage для ценовой рекомендации.")
        return "\n".join(lines)
    for row in rows[:20]:
        lines.extend(
            [
                f"### {row['group']} / {row['price_band']}",
                "",
                f"- market avg: `{row['avg_market_price']} ₽`",
                f"- my avg cogs: `{row['my_avg_cogs']} ₽`",
                f"- min safe price: `{row['min_safe_price']} ₽`",
                f"- suggested price: `{row['suggested_price']} ₽`",
                f"- pricing label: `{row['pricing_label']}`",
                f"- reason: `{row['pricing_reason']}`",
                "",
            ]
        )
    return "\n".join(lines)


def build_dashboard_payload(source_payload, rows, args):
    counts = {
        "priced_windows_count": len(rows),
        "aggressive_price_windows_count": sum(1 for row in rows if row["pricing_label"] == "можно агрессивно входить"),
        "market_price_windows_count": sum(1 for row in rows if row["pricing_label"] == "входить по рынку"),
        "test_price_windows_count": sum(1 for row in rows if row["pricing_label"] == "только точечный тест"),
        "do_not_discount_windows_count": sum(1 for row in rows if row["pricing_label"] == "не демпинговать"),
    }
    observed_prices = [row["avg_market_price"] for row in rows if row.get("avg_market_price")]
    margin_fit_values = [row["market_margin_fit_pct"] for row in rows if row.get("market_margin_fit_pct") is not None]
    actions = {
        "aggressive_price": [row for row in rows if row["pricing_label"] == "можно агрессивно входить"][:8],
        "price_at_market": [row for row in rows if row["pricing_label"] == "входить по рынку"][:8],
        "test_carefully": [row for row in rows if row["pricing_label"] == "только точечный тест"][:8],
        "protect_margin": [row for row in rows if row["pricing_label"] == "не демпинговать"][:8],
    }
    tables = {
        "priced_windows": rows,
        "aggressive_entry": actions["aggressive_price"],
        "margin_protection": actions["protect_margin"],
    }
    charts = {
        "pricing_labels": [
            {"key": "Агрессивно входить", "count": counts["aggressive_price_windows_count"]},
            {"key": "Цена по рынку", "count": counts["market_price_windows_count"]},
            {"key": "Осторожный тест", "count": counts["test_price_windows_count"]},
            {"key": "Не демпинговать", "count": counts["do_not_discount_windows_count"]},
        ],
        "avg_market_price_by_band": [
            {
                "key": f"{row.get('group') or 'н/д'} / {row.get('price_band') or 'н/д'}",
                "value": row.get("avg_market_price") or 0,
            }
            for row in rows[:10]
        ],
    }
    insights = []
    if actions["aggressive_price"]:
        insights.append({
            "title": "Есть окна для агрессивного входа",
            "text": f"Нашлось {counts['aggressive_price_windows_count']} окон, где можно входить чуть ниже рынка и всё ещё удерживать целевую маржу {args.target_margin_pct}%.",
            "tone": "good",
        })
    if actions["price_at_market"]:
        insights.append({
            "title": "Часть окон можно брать по средней цене рынка",
            "text": f"В {counts['market_price_windows_count']} окнах средняя цена рынка уже совместима с вашей экономикой без дополнительного демпинга.",
            "tone": "good",
        })
    if actions["test_carefully"]:
        insights.append({
            "title": "Есть окна только для точечного теста",
            "text": f"{counts['test_price_windows_count']} окон требуют цены осторожнее рынка или сильного оффера, иначе маржа станет слишком тонкой.",
            "tone": "warn",
        })
    if actions["protect_margin"]:
        top = actions["protect_margin"][0]
        insights.append({
            "title": "Где нельзя демпинговать",
            "text": f"Например, {top.get('group') or 'н/д'} / {top.get('price_band') or 'н/д'} требует минимум {top.get('min_safe_price')} ₽, иначе целевая маржа уже не держится.",
            "tone": "bad",
        })
    metadata = {
        "window": (source_payload.get("metadata") or {}).get("window") or {},
        "documents": {},
        "pricing": {
            "mode": "recommendation-first",
            "target_margin_pct": args.target_margin_pct,
            "generated_from": args.market_json,
        },
    }
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "kpis": {
            "total_skus": len(rows),
            "sold_skus": len(rows),
            "revenue_total": 0.0,
            "gross_profit_total": 0.0,
            "stockout_risk_count": 0,
            "stale_stock_count": 0,
            "priced_windows_count": counts["priced_windows_count"],
            "aggressive_price_windows_count": counts["aggressive_price_windows_count"],
            "market_price_windows_count": counts["market_price_windows_count"],
            "test_price_windows_count": counts["test_price_windows_count"],
            "do_not_discount_windows_count": counts["do_not_discount_windows_count"],
            "target_margin_pct": args.target_margin_pct,
            "avg_observed_market_price": round(sum(observed_prices) / len(observed_prices), 2) if observed_prices else None,
            "avg_margin_fit_pct": round(sum(margin_fit_values) / len(margin_fit_values), 2) if margin_fit_values else None,
        },
        "actions": actions,
        "tables": tables,
        "charts": charts,
        "insights": insights,
    }


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))
    payload = load_json(Path(args.market_json))
    entry_windows = (payload.get("tables") or {}).get("entry_windows") or (payload.get("entry_windows") or [])
    rows = []
    for row in entry_windows:
        pricing = recommend_window(row, args.target_margin_pct)
        if pricing:
            rows.append(pricing)
    rows.sort(key=lambda row: (row["orders_sum"], -(row["min_safe_price"] - row["avg_market_price"])), reverse=True)

    result = {
        "generated_from": args.market_json,
        "target_margin_pct": args.target_margin_pct,
        "rows": rows,
    }
    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    dashboard_path = dashboard_dir / f"{args.report_prefix}.json"
    write_json(json_path, result)
    md_path.write_text(build_markdown(rows, args.target_margin_pct), encoding="utf-8")
    write_json(dashboard_path, build_dashboard_payload(payload, rows, args))
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {dashboard_path}")


if __name__ == "__main__":
    main()
