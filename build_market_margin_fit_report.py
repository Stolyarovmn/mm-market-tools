#!/usr/bin/env python3
# TASK-003: price_band breakdown and go/no-go economics (2026-04-24)
import argparse
import datetime as dt
from pathlib import Path

from core.io_utils import load_json, write_json
from core.paths import NORMALIZED_DIR, REPORTS_DIR


DEFAULT_INPUT_JSON = str(NORMALIZED_DIR / "competitor_market_analysis_2026-04-09g.json")
DEFAULT_REPORT_DIR = str(REPORTS_DIR)
DEFAULT_DATE = dt.date.today().isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Build a decision-focused market margin fit report from a market analysis bundle.")
    parser.add_argument("--input-json", default=DEFAULT_INPUT_JSON)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    return parser.parse_args()


def classify_price_band(price):
    """Classify price into price bands."""
    if price is None or price == 0:
        return "unknown"
    if price < 100:
        return "low"
    elif price < 300:
        return "mid_low"
    elif price < 1000:
        return "mid"
    elif price < 3000:
        return "high"
    else:
        return "premium"


def decide_go_no_go(row, target_margin_pct):
    """Decide go/no-go based on market_margin_fit_pct vs target margin."""
    market_margin_fit = row.get("market_margin_fit_pct")
    
    if market_margin_fit is None:
        return {"decision": "no_data", "reason": "missing economics"}
    
    target = target_margin_pct if target_margin_pct is not None else 20
    diff = market_margin_fit - target
    
    if diff >= 5:
        return {"decision": "go", "reason": "margin fits with cushion"}
    elif diff >= 0:
        return {"decision": "go_thin", "reason": "margin barely fits"}
    elif diff >= -5:
        return {"decision": "test", "reason": "improve sourcing 5pp"}
    else:
        return {"decision": "no_go", "reason": "margin below target by >5pp"}


def pick_windows(rows, bucket, limit=10):
    return [row for row in rows if row.get("entry_strategy_bucket") == bucket][:limit]


def top_unknown_economics(rows, limit=10):
    candidates = [row for row in rows if row.get("market_margin_fit_pct") is None]
    return sorted(candidates, key=lambda row: (row.get("entry_window_score") or 0, row.get("orders_sum") or 0), reverse=True)[:limit]


def classify_blind_spot(row, group_row):
    my_sku_count = group_row.get("my_sku_count") if group_row else None
    my_avg_price = row.get("my_avg_price")
    my_avg_cogs = row.get("my_avg_cogs")

    if my_avg_price is None or not my_sku_count:
        return {
            "blind_spot_type": "no_assortment_reference",
            "blind_spot_label": "нет опорного ассортимента",
            "next_step": "собрать 3-5 benchmark SKU и прикинуть целевую закупку до решения о входе",
        }
    if my_avg_cogs is None:
        return {
            "blind_spot_type": "missing_cogs",
            "blind_spot_label": "есть ассортимент, но нет cost-покрытия",
            "next_step": "дозаполнить себестоимость по своим SKU этой группы, иначе окно нельзя честно читать по прибыли",
        }
    return {
        "blind_spot_type": "other",
        "blind_spot_label": "прочая слепая зона",
        "next_step": "проверить связку между ассортиментом, себестоимостью и группировкой товаров",
    }


def build_summary(payload):
    summary = payload.get("summary") or {}
    windows = payload.get("entry_windows") or []
    groups = payload.get("groups") or []
    group_lookup = {row.get("group"): row for row in groups}
    target_margin_pct = summary.get("target_margin_pct") or 20

    # Enrich windows with price_band, go/no-go decision, and revenue estimates
    enriched_windows = []
    for row in windows:
        enriched = dict(row)
        avg_price = row.get("avg_price") or row.get("my_avg_price") or row.get("market_avg_price") or 0
        enriched["price_band"] = classify_price_band(avg_price)
        
        decision_info = decide_go_no_go(enriched, target_margin_pct)
        enriched["go_no_go_decision"] = decision_info["decision"]
        enriched["go_no_go_reason"] = decision_info["reason"]
        
        estimated_units = row.get("orders_sum") or row.get("orders_avg_monthly") or 0
        enriched["estimated_monthly_units"] = estimated_units
        enriched["estimated_monthly_revenue"] = estimated_units * avg_price
        
        enriched_windows.append(enriched)

    # Build price_band_summary
    price_band_summary = {}
    for window in enriched_windows:
        pb = window.get("price_band", "unknown")
        if pb not in price_band_summary:
            price_band_summary[pb] = {
                "windows_count": 0,
                "go_count": 0,
                "go_thin_count": 0,
                "test_count": 0,
                "no_go_count": 0,
                "no_data_count": 0,
                "total_monthly_units": 0,
                "total_monthly_revenue": 0,
                "margin_fits": [],
            }
        
        pb_data = price_band_summary[pb]
        pb_data["windows_count"] += 1
        pb_data["total_monthly_units"] += window.get("estimated_monthly_units", 0)
        pb_data["total_monthly_revenue"] += window.get("estimated_monthly_revenue", 0)
        
        decision = window.get("go_no_go_decision")
        if decision == "go":
            pb_data["go_count"] += 1
        elif decision == "go_thin":
            pb_data["go_thin_count"] += 1
        elif decision == "test":
            pb_data["test_count"] += 1
        elif decision == "no_go":
            pb_data["no_go_count"] += 1
        elif decision == "no_data":
            pb_data["no_data_count"] += 1
        
        if window.get("market_margin_fit_pct") is not None:
            pb_data["margin_fits"].append(window.get("market_margin_fit_pct"))
    
    # Calculate average margin per price band
    for pb_data in price_band_summary.values():
        if pb_data["margin_fits"]:
            pb_data["avg_market_margin_fit_pct"] = sum(pb_data["margin_fits"]) / len(pb_data["margin_fits"])
        else:
            pb_data["avg_market_margin_fit_pct"] = None
        del pb_data["margin_fits"]
    
    # Sort by windows_count DESC
    price_band_summary_sorted = dict(
        sorted(price_band_summary.items(), key=lambda x: x[1]["windows_count"], reverse=True)
    )

    # Build acceptance_windows_by_price_band (top 5 go/go_thin per price band)
    acceptance_windows_by_price_band = {}
    for pb in ["low", "mid_low", "mid", "high", "premium", "unknown"]:
        pb_windows = [w for w in enriched_windows if w.get("price_band") == pb and w.get("go_no_go_decision") in {"go", "go_thin"}]
        pb_windows_sorted = sorted(pb_windows, key=lambda w: w.get("estimated_monthly_revenue", 0), reverse=True)[:5]
        
        if pb_windows_sorted:
            acceptance_windows_by_price_band[pb] = [
                {
                    "group": w.get("group"),
                    "avg_price": w.get("avg_price"),
                    "market_margin_fit_pct": w.get("market_margin_fit_pct"),
                    "go_no_go_decision": w.get("go_no_go_decision"),
                    "estimated_monthly_units": w.get("estimated_monthly_units"),
                    "estimated_monthly_revenue": w.get("estimated_monthly_revenue"),
                }
                for w in pb_windows_sorted
            ]

    # Original logic
    enter_now = pick_windows(enriched_windows, "enter_now")
    test_entry = [row for row in enriched_windows if row.get("entry_strategy_bucket") in {"test_entry", "validate_economics"}][:10]
    sourcing_or_avoid = [row for row in enriched_windows if row.get("entry_strategy_bucket") in {"avoid", "improve_sourcing"}][:10]
    blind_spots = []
    for row in top_unknown_economics(enriched_windows, limit=10):
        group_row = group_lookup.get(row.get("group")) or {}
        row["my_sku_count"] = group_row.get("my_sku_count")
        row.update(classify_blind_spot(row, group_row))
        blind_spots.append(row)
    strongest_economic_groups = sorted(
        [row for row in groups if row.get("market_margin_fit_pct") is not None],
        key=lambda row: ((row.get("market_margin_fit_pct") or 0), (row.get("orders_sum") or 0)),
        reverse=True,
    )[:10]
    sourcing_candidates = sorted(
        [
            row for row in enriched_windows
            if row.get("entry_strategy_bucket") == "improve_sourcing"
            and row.get("market_margin_fit_pct") is not None
        ],
        key=lambda row: ((row.get("orders_sum") or 0), (row.get("market_margin_fit_pct") or -999)),
        reverse=True,
    )[:10]

    return {
        "summary": {
            "target_margin_pct": summary.get("target_margin_pct"),
            "economics_coverage_groups_pct": summary.get("economics_coverage_groups_pct"),
            "economics_coverage_windows_pct": summary.get("economics_coverage_windows_pct"),
            "entry_ready_windows_count": summary.get("entry_ready_windows_count"),
            "test_entry_windows_count": summary.get("test_entry_windows_count"),
            "avoid_windows_count": summary.get("avoid_windows_count"),
        },
        "price_band_summary": price_band_summary_sorted,
        "acceptance_windows_by_price_band": acceptance_windows_by_price_band,
        "enter_now": enter_now,
        "test_entry": test_entry,
        "sourcing_or_avoid": sourcing_or_avoid,
        "blind_spots": blind_spots,
        "sourcing_candidates": sourcing_candidates,
        "strongest_economic_groups": strongest_economic_groups,
    }


def write_markdown(path, report):
    summary = report["summary"]
    lines = [
        f"# Market Margin Fit {DEFAULT_DATE}",
        "",
        f"- target_margin_pct: `{summary.get('target_margin_pct')}`",
        f"- economics_coverage_groups_pct: `{summary.get('economics_coverage_groups_pct')}`",
        f"- economics_coverage_windows_pct: `{summary.get('economics_coverage_windows_pct')}`",
        f"- entry_ready_windows_count: `{summary.get('entry_ready_windows_count')}`",
        f"- test_entry_windows_count: `{summary.get('test_entry_windows_count')}`",
        f"- avoid_windows_count: `{summary.get('avoid_windows_count')}`",
        "",
        "## Price Band Summary",
        "",
    ]
    for pb, data in (report.get("price_band_summary") or {}).items():
        lines.append(
            f"- {pb}: {data.get('windows_count')} windows | go={data.get('go_count')} go_thin={data.get('go_thin_count')} test={data.get('test_count')} no_go={data.get('no_go_count')} | units={data.get('total_monthly_units')} | revenue={data.get('total_monthly_revenue'):.0f} | avg_margin={data.get('avg_market_margin_fit_pct')}"
        )
    
    lines.extend(["", "## Входить первым", ""])
    for row in report["enter_now"] or []:
        lines.append(
            f"- {row['group']} / {row['price_band']} | score `{row.get('entry_window_score')}` | margin fit `{row.get('market_margin_fit_pct')}` | go/no-go `{row.get('go_no_go_decision')}` | reason `{row.get('entry_strategy_reason')}`"
        )
    if not report["enter_now"]:
        lines.append("- Нет окон, которые уже проходят жёсткий фильтр первого входа.")

    lines.extend(["", "## Тестировать точечно", ""])
    for row in report["test_entry"] or []:
        lines.append(
            f"- {row['group']} / {row['price_band']} | decision `{row.get('entry_strategy_label')}` | HHI `{row.get('dominance_hhi')}` | margin fit `{row.get('market_margin_fit_pct')}` | reason `{row.get('entry_strategy_reason')}`"
        )
    if not report["test_entry"]:
        lines.append("- Нет окон для тестового входа.")

    lines.extend(["", "## Не входить или менять закупку", ""])
    for row in report["sourcing_or_avoid"] or []:
        lines.append(
            f"- {row['group']} / {row['price_band']} | decision `{row.get('entry_strategy_label')}` | margin fit `{row.get('market_margin_fit_pct')}` | HHI `{row.get('dominance_hhi')}` | reason `{row.get('entry_strategy_reason')}`"
        )
    if not report["sourcing_or_avoid"]:
        lines.append("- Нет критичных окон в текущей выборке.")

    lines.extend(["", "## Слепые зоны по экономике", ""])
    for row in report["blind_spots"] or []:
        lines.append(
            f"- {row['group']} / {row['price_band']} | score `{row.get('entry_window_score')}` | orders `{row.get('orders_sum')}` | type `{row.get('blind_spot_label')}` | my_sku_count `{row.get('my_sku_count')}` | next `{row.get('next_step')}`"
        )
    if not report["blind_spots"]:
        lines.append("- Существенных слепых зон не осталось.")

    lines.extend(["", "## Где сначала менять закупку", ""])
    for row in report["sourcing_candidates"] or []:
        lines.append(
            f"- {row['group']} / {row['price_band']} | margin fit `{row.get('market_margin_fit_pct')}` | target gap `{row.get('margin_vs_target_pct')}` | orders `{row.get('orders_sum')}` | reason `{row.get('entry_strategy_reason')}`"
        )
    if not report["sourcing_candidates"]:
        lines.append("- Нет выраженных окон, где спрос уже есть, а проблема только в закупке.")

    lines.extend(["", "## Сильнейшие группы по экономике", ""])
    for row in report["strongest_economic_groups"] or []:
        lines.append(
            f"- {row['group']} | market avg `{row.get('avg_price')}` | margin fit `{row.get('market_margin_fit_pct')}` | orders `{row.get('orders_sum')}` | profile `{row.get('market_margin_fit_profile')}`"
        )
    if not report["strongest_economic_groups"]:
        lines.append("- Нет групп, где экономика уже подтверждена.")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse_args()
    payload = load_json(args.input_json)
    report = build_summary(payload)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"market_margin_fit_{args.date_tag}.json"
    md_path = report_dir / f"market_margin_fit_{args.date_tag}.md"
    write_json(json_path, report)
    write_markdown(md_path, report)
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
