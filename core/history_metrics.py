#!/usr/bin/env python3
import datetime as dt
from pathlib import Path


def parse_iso_datetime(value):
    if not value:
        return None
    return dt.datetime.fromisoformat(value)


def parse_window_end(item):
    return parse_iso_datetime(((item.get("window") or {}).get("date_to")))


def sort_history_items(items):
    return sorted(items, key=lambda item: parse_window_end(item) or dt.datetime.min.replace(tzinfo=dt.timezone.utc))


def growth_pct(current_value, previous_value):
    current = float(current_value or 0.0)
    previous = float(previous_value or 0.0)
    if previous == 0:
        return None
    return round((current - previous) / previous * 100.0, 2)


def year_diff_days(current_end, candidate_end):
    return abs((current_end.date() - candidate_end.date()).days)


def find_period_offset_match(items, current_item, years_back):
    current_end = parse_window_end(current_item)
    if current_end is None:
        return None
    target_year = current_end.year - years_back
    candidates = []
    for item in items:
        item_end = parse_window_end(item)
        if item_end is None:
            continue
        if item_end.year != target_year:
            continue
        candidates.append((year_diff_days(current_end, item_end), item))
    if not candidates:
        return None
    candidates.sort(key=lambda entry: entry[0])
    best_diff, best_item = candidates[0]
    if best_diff > 45:
        return None
    return best_item


def build_kpi_series(items):
    rows = []
    for item in sort_history_items(items):
        kpis = item.get("kpis") or {}
        window = item.get("window") or {}
        rows.append(
            {
                "report_name": item.get("report_name"),
                "report_kind": item.get("report_kind"),
                "date_from": window.get("date_from"),
                "date_to": window.get("date_to"),
                "window_days": window.get("window_days"),
                "revenue_total": kpis.get("revenue_total", 0.0),
                "gross_profit_total": kpis.get("gross_profit_total", 0.0),
                "sold_skus": kpis.get("sold_skus", 0),
                "stockout_risk_count": kpis.get("stockout_risk_count", 0),
                "stale_stock_count": kpis.get("stale_stock_count", 0),
            }
        )
    return rows


def build_period_comparison(items):
    ordered = sort_history_items(items)
    if not ordered:
        return {
            "available_history_days": 0,
            "available_history_years": 0.0,
            "latest": None,
            "previous_period": None,
            "year_over_year": None,
            "three_year_comparison": None,
            "history_series": [],
        }

    latest = ordered[-1]
    latest_kpis = latest.get("kpis") or {}
    latest_end = parse_window_end(latest)
    earliest_end = parse_window_end(ordered[0])
    available_days = max(0, (latest_end.date() - earliest_end.date()).days) if latest_end and earliest_end else 0
    previous = ordered[-2] if len(ordered) >= 2 else None
    yoy = find_period_offset_match(ordered[:-1], latest, 1)
    three_year = find_period_offset_match(ordered[:-1], latest, 3)

    def build_compare_block(reference_item, label):
        if not reference_item:
            return None
        reference_kpis = reference_item.get("kpis") or {}
        return {
            "label": label,
            "reference_report": reference_item.get("report_name"),
            "reference_window": reference_item.get("window") or {},
            "delta": {
                "revenue_total_pct": growth_pct(latest_kpis.get("revenue_total"), reference_kpis.get("revenue_total")),
                "gross_profit_total_pct": growth_pct(latest_kpis.get("gross_profit_total"), reference_kpis.get("gross_profit_total")),
                "sold_skus_pct": growth_pct(latest_kpis.get("sold_skus"), reference_kpis.get("sold_skus")),
                "stockout_risk_count_pct": growth_pct(latest_kpis.get("stockout_risk_count"), reference_kpis.get("stockout_risk_count")),
                "stale_stock_count_pct": growth_pct(latest_kpis.get("stale_stock_count"), reference_kpis.get("stale_stock_count")),
            },
            "reference_kpis": reference_kpis,
        }

    return {
        "available_history_days": available_days,
        "available_history_years": round(available_days / 365.25, 2),
        "latest": latest,
        "previous_period": build_compare_block(previous, "previous_period"),
        "year_over_year": build_compare_block(yoy, "year_over_year"),
        "three_year_comparison": build_compare_block(three_year, "three_year_comparison"),
        "history_series": build_kpi_series(ordered),
    }


def build_comparison_markdown(comparison):
    lines = [
        "# Историческое сравнение периодов",
        "",
        f"- доступная история: `{comparison['available_history_days']}` дней",
        f"- доступная история: `{comparison['available_history_years']}` лет",
        "",
    ]
    latest = comparison.get("latest")
    if latest:
        kpis = latest.get("kpis") or {}
        lines.extend(
            [
                "## Latest",
                "",
                f"- report: `{latest.get('report_name')}`",
                f"- window: `{(latest.get('window') or {}).get('date_from')}` -> `{(latest.get('window') or {}).get('date_to')}`",
                f"- revenue: `{kpis.get('revenue_total', 0.0)} ₽`",
                f"- gross profit: `{kpis.get('gross_profit_total', 0.0)} ₽`",
                f"- sold skus: `{kpis.get('sold_skus', 0)}`",
                "",
            ]
        )

    def append_block(title, block):
        lines.extend([f"## {title}", ""])
        if not block:
            lines.append("- недоступно: не хватает исторической глубины")
            lines.append("")
            return
        delta = block.get("delta") or {}
        lines.extend(
            [
                f"- reference report: `{block.get('reference_report')}`",
                f"- revenue delta: `{delta.get('revenue_total_pct')}`%",
                f"- gross profit delta: `{delta.get('gross_profit_total_pct')}`%",
                f"- sold skus delta: `{delta.get('sold_skus_pct')}`%",
                f"- stockout risk delta: `{delta.get('stockout_risk_count_pct')}`%",
                f"- stale stock delta: `{delta.get('stale_stock_count_pct')}`%",
                "",
            ]
        )

    append_block("Previous Period", comparison.get("previous_period"))
    append_block("Year over Year", comparison.get("year_over_year"))
    append_block("3-Year Comparison", comparison.get("three_year_comparison"))
    return "\n".join(lines)
