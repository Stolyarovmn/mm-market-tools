#!/usr/bin/env python3
import argparse
import datetime as dt
from pathlib import Path

from core.cubejs_api import flatten_results, run_cubejs_query
from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION
from core.io_utils import write_csv_rows, write_json
from core.paths import DASHBOARD_DIR, NORMALIZED_DIR, REPORTS_DIR, ensure_dir, today_tag


PRIMARY_MEASURES = ["Sales.seller_revenue_without_delivery_measure"]
SECONDARY_MEASURES = ["Sales.orders_number", "Sales.item_sold_number"]


def iso_date(value):
    return value.isoformat()


def moscow_today():
    return dt.date.today()


def shift_years(value, years):
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def build_query(shop_id, date_from, date_to, measures, granularity=None):
    time_dimension = {
        "dimension": "Sales.created_at",
        "dateRange": [iso_date(date_from), iso_date(date_to)],
    }
    if granularity:
        time_dimension["granularity"] = granularity
    return {
        "measures": measures,
        "timezone": "Europe/Moscow",
        "timeDimensions": [time_dimension],
        "filters": [
            {
                "member": "Sales.shop_id",
                "operator": "equals",
                "values": [str(shop_id)],
            }
        ],
    }


def metric_value(row, key):
    value = row.get(key)
    if value in (None, ""):
        return 0.0
    return float(value)


def parse_aggregate_row(row):
    return {
        "revenue_total": metric_value(row, "Sales.seller_revenue_without_delivery_measure"),
        "orders_total": metric_value(row, "Sales.orders_number"),
        "items_sold_total": metric_value(row, "Sales.item_sold_number"),
    }


def growth_pct(current, previous):
    if previous == 0:
        return None
    return round((current - previous) / previous * 100.0, 2)


def compare_blocks(current, reference):
    return {
        "revenue_total_pct": growth_pct(current["revenue_total"], reference["revenue_total"]),
        "orders_total_pct": growth_pct(current["orders_total"], reference["orders_total"]),
        "items_sold_total_pct": growth_pct(current["items_sold_total"], reference["items_sold_total"]),
    }


def merge_metric_rows(primary_row, secondary_row):
    return {
        "revenue_total": metric_value(primary_row, "Sales.seller_revenue_without_delivery_measure"),
        "orders_total": metric_value(secondary_row, "Sales.orders_number"),
        "items_sold_total": metric_value(secondary_row, "Sales.item_sold_number"),
    }


def build_markdown(payload):
    current = payload["periods"]["current_trailing_year"]
    previous = payload["periods"]["previous_year_same_window"]
    three_year = payload["periods"]["three_year_same_window"]
    ytd = payload["periods"]["current_ytd"]
    ytd_prev = payload["periods"]["previous_ytd"]

    lines = [
        "# CubeJS периодическое сравнение",
        "",
        f"- monthly history months: `{len(payload['series_monthly'])}`",
        f"- history start: `{payload['history_window']['date_from']}`",
        f"- history end: `{payload['history_window']['date_to']}`",
        "",
        "## Trailing Year",
        "",
        f"- revenue: `{round(current['metrics']['revenue_total'], 2)} ₽`",
        f"- orders: `{round(current['metrics']['orders_total'], 2)}`",
        f"- items sold: `{round(current['metrics']['items_sold_total'], 2)}`",
        "",
        "## YoY Same Window",
        "",
    ]

    if previous:
        delta = previous["delta_vs_current"]
        lines.extend(
            [
                f"- reference: `{previous['date_from']}` -> `{previous['date_to']}`",
                f"- revenue delta: `{delta['revenue_total_pct']}`%",
                f"- orders delta: `{delta['orders_total_pct']}`%",
                f"- items sold delta: `{delta['items_sold_total_pct']}`%",
                "",
            ]
        )
    else:
        lines.extend(["- недоступно", ""])

    lines.extend(["## 3-Year Same Window", ""])
    if three_year:
        delta = three_year["delta_vs_current"]
        lines.extend(
            [
                f"- reference: `{three_year['date_from']}` -> `{three_year['date_to']}`",
                f"- revenue delta: `{delta['revenue_total_pct']}`%",
                f"- orders delta: `{delta['orders_total_pct']}`%",
                f"- items sold delta: `{delta['items_sold_total_pct']}`%",
                "",
            ]
        )
    else:
        lines.extend(["- недоступно", ""])

    lines.extend(["## YTD YoY", ""])
    if ytd_prev:
        delta = ytd_prev["delta_vs_current"]
        lines.extend(
            [
                f"- current YTD revenue: `{round(ytd['metrics']['revenue_total'], 2)} ₽`",
                f"- previous YTD revenue: `{round(ytd_prev['metrics']['revenue_total'], 2)} ₽`",
                f"- revenue delta: `{delta['revenue_total_pct']}`%",
                f"- orders delta: `{delta['orders_total_pct']}`%",
                "",
            ]
        )
    else:
        lines.extend(["- недоступно", ""])
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Build long-range period comparisons via CubeJS.")
    parser.add_argument("--token", required=True)
    parser.add_argument("--shop-id", type=int, default=98)
    parser.add_argument("--history-years", type=int, default=3)
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--normalized-dir", default=str(NORMALIZED_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--report-prefix", default=f"cubejs_period_compare_{today_tag()}")
    return parser.parse_args()


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    normalized_dir = ensure_dir(Path(args.normalized_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))

    today = moscow_today()
    current_start = today - dt.timedelta(days=364)
    prev_start = shift_years(current_start, -1)
    prev_end = shift_years(today, -1)
    three_start = shift_years(current_start, -3)
    three_end = shift_years(today, -3)
    ytd_start = dt.date(today.year, 1, 1)
    prev_ytd_start = dt.date(today.year - 1, 1, 1)
    prev_ytd_end = shift_years(today, -1)
    history_start = shift_years(today, -args.history_years).replace(day=1)

    def fetch_period_metrics(date_from, date_to):
        primary_payload = run_cubejs_query(build_query(args.shop_id, date_from, date_to, PRIMARY_MEASURES), token=args.token)
        secondary_payload = run_cubejs_query(build_query(args.shop_id, date_from, date_to, SECONDARY_MEASURES), token=args.token)
        primary_rows = flatten_results(primary_payload)
        secondary_rows = flatten_results(secondary_payload)
        return merge_metric_rows(primary_rows[0], secondary_rows[0])

    current_metrics = fetch_period_metrics(current_start, today)
    prev_metrics = fetch_period_metrics(prev_start, prev_end)
    three_metrics = fetch_period_metrics(three_start, three_end)
    ytd_metrics = fetch_period_metrics(ytd_start, today)
    prev_ytd_metrics = fetch_period_metrics(prev_ytd_start, prev_ytd_end)

    monthly_primary_payload = run_cubejs_query(
        build_query(args.shop_id, history_start, today, PRIMARY_MEASURES, granularity="month"),
        token=args.token,
    )
    monthly_secondary_payload = run_cubejs_query(
        build_query(args.shop_id, history_start, today, SECONDARY_MEASURES, granularity="month"),
        token=args.token,
    )
    primary_monthly_rows = flatten_results(monthly_primary_payload)
    secondary_monthly_rows = flatten_results(monthly_secondary_payload)
    secondary_by_month = {row.get("Sales.created_at.month"): row for row in secondary_monthly_rows}
    monthly_rows = []
    for row in primary_monthly_rows:
        month_key = row.get("Sales.created_at.month")
        combined = {"Sales.created_at.month": month_key}
        combined.update(row)
        combined.update(secondary_by_month.get(month_key, {}))
        monthly_rows.append(combined)

    payload = {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "history_window": {
            "date_from": iso_date(history_start),
            "date_to": iso_date(today),
            "history_years": args.history_years,
        },
        "periods": {
            "current_trailing_year": {
                "date_from": iso_date(current_start),
                "date_to": iso_date(today),
                "metrics": current_metrics,
            },
            "previous_year_same_window": {
                "date_from": iso_date(prev_start),
                "date_to": iso_date(prev_end),
                "metrics": prev_metrics,
                "delta_vs_current": compare_blocks(current_metrics, prev_metrics),
            },
            "three_year_same_window": {
                "date_from": iso_date(three_start),
                "date_to": iso_date(three_end),
                "metrics": three_metrics,
                "delta_vs_current": compare_blocks(current_metrics, three_metrics),
            },
            "current_ytd": {
                "date_from": iso_date(ytd_start),
                "date_to": iso_date(today),
                "metrics": ytd_metrics,
            },
            "previous_ytd": {
                "date_from": iso_date(prev_ytd_start),
                "date_to": iso_date(prev_ytd_end),
                "metrics": prev_ytd_metrics,
                "delta_vs_current": compare_blocks(ytd_metrics, prev_ytd_metrics),
            },
        },
        "series_monthly": monthly_rows,
    }

    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    csv_path = report_dir / f"{args.report_prefix}.csv"
    normalized_path = normalized_dir / f"{args.report_prefix}.json"
    dashboard_path = dashboard_dir / f"{args.report_prefix}.json"
    write_json(json_path, payload)
    write_json(normalized_path, payload)
    write_json(dashboard_path, payload)
    write_csv_rows(csv_path, monthly_rows)
    md_path.write_text(build_markdown(payload), encoding="utf-8")
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {normalized_path}")
    print(f"Saved: {dashboard_path}")


if __name__ == "__main__":
    main()
