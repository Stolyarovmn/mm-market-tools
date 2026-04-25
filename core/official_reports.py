#!/usr/bin/env python3
import csv
import math
from pathlib import Path

import requests

from core.product_identity import normalize_family_row, summarize_variant_families


MIN_WINNER_UNITS = 3
MIN_REORDER_AVG_DAILY = 0.2
MIN_WINNER_AVG_DAILY = 0.2
MIN_WINNER_NET_REVENUE = 1000.0
DEFAULT_WINDOW_DAYS = 7.0


def parse_decimal(value):
    raw = (value or "").strip().replace("\xa0", "").replace(" ", "")
    if not raw:
        return 0.0
    return float(raw.replace(",", "."))


def parse_int(value):
    raw = (value or "").strip().replace("\xa0", "").replace(" ", "")
    if not raw:
        return 0
    return int(float(raw.replace(",", ".")))


def load_text(path_or_url):
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        response = requests.get(path_or_url, timeout=60)
        response.raise_for_status()
        return response.text
    return Path(path_or_url).read_text(encoding="utf-8")


def make_key(row):
    return (
        (row.get("Seller SKU ID") or "").strip()
        or (row.get("SKU") or "").strip()
        or (row.get("Наименование") or "").strip()
    )


def load_sells_report(path_or_url):
    text = load_text(path_or_url)
    reader = csv.DictReader(text.splitlines())
    rows = []
    for row in reader:
        units = parse_int(row.get("Продано (ед.)"))
        revenue = parse_decimal(row.get("Выручка (руб.)"))
        cogs = parse_decimal(row.get("Себестоимость (руб.)"))
        net_revenue = parse_decimal(row.get("Выручка с вычетом комиссии (руб.)"))
        fee = parse_decimal(row.get("Комиссия маркетплейса (руб.)"))
        gross_profit = net_revenue - cogs
        rows.append(
            {
                "key": make_key(row),
                "sku": row.get("SKU") or "",
                "seller_sku_id": row.get("Seller SKU ID") or "",
                "title": row.get("Наименование") or "",
                "units_sold": units,
                "returns": parse_int(row.get("Количество возвратов (ед.)")),
                "revenue": round(revenue, 2),
                "cogs": round(cogs, 2),
                "net_revenue": round(net_revenue, 2),
                "marketplace_fee": round(fee, 2),
                "gross_profit": round(gross_profit, 2),
                "profit_margin_pct": round((gross_profit / net_revenue * 100), 2) if net_revenue else 0.0,
                "avg_unit_revenue": round(revenue / units, 2) if units else 0.0,
            }
        )
    return rows


def load_left_out_report(path_or_url):
    text = load_text(path_or_url)
    reader = csv.DictReader(text.splitlines())
    rows = []
    for row in reader:
        rows.append(
            {
                "key": make_key(row),
                "inventory_row_id": parse_int(row.get("ID")),
                "barcode": row.get("Штрихкод") or "",
                "sku": row.get("SKU") or "",
                "seller_sku_id": row.get("Seller SKU ID") or "",
                "title": row.get("Наименование") or "",
                "product_id": parse_int(row.get("ID товара")),
                "status": row.get("Статус") or "",
                "in_sale": parse_int(row.get("В продаже")),
                "to_ship": parse_int(row.get("К отправке")),
                "returns_stock": parse_int(row.get("Возврат")),
                "damaged": parse_int(row.get("Брак")),
                "total_stock": parse_int(row.get("Общий остаток")),
                "available_to_ship": parse_int(row.get("Доступно к отправке")),
                "avg_daily_sales_official": parse_decimal(row.get("Среднесуточные продажи (шт.)")),
                "avg_daily_stock_official": parse_decimal(row.get("Среднесуточные остатки, (шт.)")),
                "turnover_days_official": parse_decimal(row.get("Оборачиваемость")),
                "storage_cost_per_day": parse_decimal(row.get("Стоимость хранения (руб. в день)")),
                "sale_price": parse_decimal(row.get("Стоимость продажи (руб.)")),
                "stock_value_sale": parse_decimal(row.get("Стоимость продажи (сумма) (руб.)")),
            }
        )
    return rows


def build_family_rows(rows):
    families = summarize_variant_families(rows)
    prepared = []
    for family in families:
        sold_units = int(family.get("sold_units_sum", 0) or 0)
        net_revenue = float(family.get("net_revenue_sum", 0.0) or 0.0)
        avg_daily = float(family.get("sales_velocity_in_stock_sum", family.get("avg_daily_sales_sum", 0.0)) or 0.0)
        stock = int(family.get("stock_units_sum", 0) or 0)
        cover = stock / avg_daily if avg_daily else math.inf
        stockout_risk = avg_daily > 0 and cover <= 14
        current_winner = sold_units >= MIN_WINNER_UNITS or (
            sold_units >= 2 and (avg_daily >= MIN_WINNER_AVG_DAILY or net_revenue >= MIN_WINNER_NET_REVENUE)
        )
        reorder_candidate = stockout_risk and (
            sold_units >= MIN_WINNER_UNITS or (sold_units >= 2 and avg_daily >= MIN_REORDER_AVG_DAILY)
        )
        enriched = {
            **family,
            "stock_cover_days": None if math.isinf(cover) else round(cover, 1),
            "stockout_risk": stockout_risk,
            "stale_stock": sold_units == 0 and stock > 0 and avg_daily == 0,
            "current_winner": current_winner,
            "reorder_candidate": reorder_candidate,
            "variant_titles": sorted({(item.get("title") or "").strip() for item in family.get("variants", []) if (item.get("title") or "").strip()}),
        }
        prepared.append(enriched)
    prepared.sort(
        key=lambda row: (row.get("current_winner", False), row.get("net_revenue_sum", 0.0), row.get("sold_units_sum", 0)),
        reverse=True,
    )
    return prepared


def abc_classification(rows, metric):
    total = sum(max(0.0, row.get(metric, 0.0)) for row in rows)
    cumulative = 0.0
    result = {}
    for row in sorted(rows, key=lambda item: item.get(metric, 0.0), reverse=True):
        value = max(0.0, row.get(metric, 0.0))
        cumulative += (value / total) if total else 0.0
        if cumulative <= 0.8:
            abc = "A"
        elif cumulative <= 0.95:
            abc = "B"
        else:
            abc = "C"
        result[row["key"]] = abc
    return result


def is_current_winner(row):
    units_sold = int(row.get("units_sold", 0) or 0)
    net_revenue = float(row.get("net_revenue", 0.0) or 0.0)
    avg_daily = float(row.get("sales_velocity_in_stock", row.get("avg_daily_sales_official", 0.0)) or 0.0)
    if units_sold >= MIN_WINNER_UNITS:
        return True
    if units_sold >= 2 and (avg_daily >= MIN_WINNER_AVG_DAILY or net_revenue >= MIN_WINNER_NET_REVENUE):
        return True
    return False


def is_reorder_candidate(row):
    if not row.get("stockout_risk"):
        return False
    units_sold = int(row.get("units_sold", 0) or 0)
    avg_daily = float(row.get("sales_velocity_in_stock", row.get("avg_daily_sales_official", 0.0)) or 0.0)
    if units_sold >= MIN_WINNER_UNITS:
        return True
    if units_sold >= 2 and avg_daily >= MIN_REORDER_AVG_DAILY:
        return True
    return False


def estimate_in_stock_days(row, window_days):
    window_days = float(window_days or 0.0)
    if window_days <= 0:
        return 0.0
    units_sold = int(row.get("units_sold", 0) or 0)
    total_stock = int(row.get("total_stock", 0) or 0)
    official_avg_daily = float(row.get("avg_daily_sales_official", 0.0) or 0.0)
    if units_sold <= 0:
        return round(window_days if total_stock > 0 else 0.0, 2)
    if official_avg_daily > 0:
        estimated = units_sold / official_avg_daily
    else:
        estimated = 1.0
    estimated = max(1.0, min(window_days, estimated))
    return round(estimated, 2)


def merge_reports(sells_rows, left_rows, window_days=DEFAULT_WINDOW_DAYS):
    left_by_key = {row["key"]: row for row in left_rows if row["key"]}
    merged = []
    keys_seen = set()
    zero_sales = {
        "units_sold": 0,
        "returns": 0,
        "revenue": 0.0,
        "cogs": 0.0,
        "net_revenue": 0.0,
        "marketplace_fee": 0.0,
        "gross_profit": 0.0,
        "profit_margin_pct": 0.0,
        "avg_unit_revenue": 0.0,
    }
    for sell in sells_rows:
        key = sell["key"]
        left = left_by_key.get(key, {})
        merged.append({**left, **sell, "key": key})
        keys_seen.add(key)
    for key, left in left_by_key.items():
        if key not in keys_seen:
            merged.append({**left, **zero_sales, "key": key})

    abc_revenue = abc_classification(merged, "net_revenue")
    abc_profit = abc_classification(merged, "gross_profit")
    for row in merged:
        row["abc_revenue"] = abc_revenue.get(row["key"], "C")
        row["abc_profit"] = abc_profit.get(row["key"], "C")
        row["window_days"] = round(float(window_days or DEFAULT_WINDOW_DAYS), 2)
        row["calendar_sales_velocity"] = round((row.get("units_sold", 0) / row["window_days"]), 4) if row["window_days"] else 0.0
        row["estimated_in_stock_days"] = estimate_in_stock_days(row, row["window_days"])
        row["estimated_oos_days"] = round(max(0.0, row["window_days"] - row["estimated_in_stock_days"]), 2)
        if row["estimated_in_stock_days"] > 0:
            row["sales_velocity_in_stock"] = round(row.get("units_sold", 0) / row["estimated_in_stock_days"], 4)
        else:
            row["sales_velocity_in_stock"] = 0.0
        row["estimated_lost_units_oos"] = round(
            max(0.0, (row["sales_velocity_in_stock"] * row["window_days"]) - row.get("units_sold", 0)),
            2,
        )
        avg_daily = row.get("sales_velocity_in_stock", 0.0)
        stock = row.get("total_stock", 0)
        cover = stock / avg_daily if avg_daily else math.inf
        row["stock_cover_days"] = None if math.isinf(cover) else round(cover, 1)
        row["stockout_risk"] = avg_daily > 0 and cover <= 14
        row["stale_stock"] = row.get("units_sold", 0) == 0 and stock > 0 and avg_daily == 0
        row["historical_only_hit"] = row.get("units_sold", 0) == 0 and avg_daily == 0 and stock == 0
        row["current_winner"] = is_current_winner(row)
        row["reorder_candidate"] = is_reorder_candidate(row)
    merged.sort(key=lambda row: (row.get("net_revenue", 0.0), row.get("units_sold", 0)), reverse=True)
    return merged


def make_summary(rows):
    sold_rows = [row for row in rows if row.get("units_sold", 0) > 0]
    current_winners = [row for row in rows if row.get("current_winner")]
    stockout_risk = [row for row in rows if row.get("stockout_risk")]
    reorder_now = [row for row in rows if row.get("reorder_candidate")]
    stale = [row for row in rows if row.get("stale_stock")]
    profit_leaders = sorted(rows, key=lambda row: row.get("gross_profit", 0.0), reverse=True)
    family_rows = build_family_rows(rows)
    sold_families = [row for row in family_rows if row.get("sold_units_sum", 0) > 0]
    family_current_winners = [row for row in family_rows if row.get("current_winner")]
    family_reorder_now = [row for row in family_rows if row.get("reorder_candidate")]
    family_stale = [row for row in family_rows if row.get("stale_stock")]
    multi_variant_families = [row for row in family_rows if row.get("variant_count", 0) > 1]
    return {
        "rows": len(rows),
        "sold_skus": len(sold_rows),
        "winner_skus": len(current_winners),
        "family_rows": len(family_rows),
        "sold_families": len(sold_families),
        "winner_families": len(family_current_winners),
        "multi_variant_families": len(multi_variant_families),
        "revenue_total": round(sum(row.get("net_revenue", 0.0) for row in rows), 2),
        "gross_profit_total": round(sum(row.get("gross_profit", 0.0) for row in rows), 2),
        "estimated_lost_units_oos_total": round(sum(row.get("estimated_lost_units_oos", 0.0) for row in rows), 2),
        "window_days": rows[0].get("window_days") if rows else DEFAULT_WINDOW_DAYS,
        "velocity_method": "proxy_units_sold_div_in_stock_days_estimated_from_official_avg_daily",
        "stockout_risk_count": len(stockout_risk),
        "reorder_now_count": len(reorder_now),
        "stale_stock_count": len(stale),
        "current_winners": current_winners[:20],
        "soft_signal_products": sorted(
            [row for row in sold_rows if not row.get("current_winner")],
            key=lambda row: (row.get("units_sold", 0), row.get("net_revenue", 0.0)),
            reverse=True,
        )[:20],
        "reorder_now": sorted(
            reorder_now,
            key=lambda row: (row.get("sales_velocity_in_stock", 0.0), row.get("units_sold", 0)),
            reverse=True,
        )[:20],
        "stockout_risk": sorted(stockout_risk, key=lambda row: (row.get("sales_velocity_in_stock", 0.0), row.get("units_sold", 0)), reverse=True)[:20],
        "stale_stock": sorted(stale, key=lambda row: row.get("stock_value_sale", 0.0), reverse=True)[:20],
        "profit_leaders": profit_leaders[:20],
        "family_current_winners": [normalize_family_row(row) for row in family_current_winners[:20]],
        "family_soft_signal_products": [
            normalize_family_row(row)
            for row in sorted(
                [row for row in sold_families if not row.get("current_winner")],
                key=lambda row: (row.get("sold_units_sum", 0), row.get("net_revenue_sum", 0.0)),
                reverse=True,
            )[:20]
        ],
        "family_reorder_now": [
            normalize_family_row(row)
            for row in sorted(
                family_reorder_now,
                key=lambda row: (row.get("avg_daily_sales_sum", 0.0), row.get("sold_units_sum", 0)),
                reverse=True,
            )[:20]
        ],
        "family_stockout_risk": [
            normalize_family_row(row)
            for row in sorted(
                [row for row in family_rows if row.get("stockout_risk")],
                key=lambda row: (row.get("avg_daily_sales_sum", 0.0), row.get("sold_units_sum", 0)),
                reverse=True,
            )[:20]
        ],
        "family_stale_stock": [
            normalize_family_row(row)
            for row in sorted(family_stale, key=lambda row: row.get("stock_units_sum", 0), reverse=True)[:20]
        ],
        "largest_multi_variant_families": [
            normalize_family_row(row)
            for row in sorted(
                multi_variant_families,
                key=lambda row: (row.get("variant_count", 0), row.get("stock_units_sum", 0), row.get("sold_units_sum", 0)),
                reverse=True,
            )[:20]
        ],
        "family_rows_payload": [normalize_family_row(row) for row in family_rows],
    }


def write_markdown(summary, path, sells_source, left_source):
    lines = [
        "# Официальный анализ по seller reports",
        "",
        f"- sells source: `{sells_source}`",
        f"- left-out source: `{left_source}`",
        f"- SKU в объединённом отчёте: `{summary['rows']}`",
        f"- SKU с продажами за период: `{summary['sold_skus']}`",
        f"- выручка с вычетом комиссии: `{summary['revenue_total']} ₽`",
        f"- валовая прибыль после комиссии и себестоимости: `{summary['gross_profit_total']} ₽`",
        f"- velocity method: `{summary.get('velocity_method')}`",
        f"- estimated lost units from OOS: `{summary.get('estimated_lost_units_oos_total')}`",
        "",
        "## Что уверенно продаётся сейчас",
        "",
    ]
    for row in summary["current_winners"][:15]:
        lines.append(
            f"- {row['title']} | sold `{row['units_sold']}` | net `{row['net_revenue']} ₽` | profit `{row['gross_profit']} ₽` | ABC rev `{row['abc_revenue']}`"
        )
    lines.extend(["", "## Что пока лишь слабый сигнал", ""])
    for row in summary["soft_signal_products"][:10]:
        lines.append(
            f"- {row['title']} | sold `{row['units_sold']}` | net `{row['net_revenue']} ₽` | velocity(in-stock) `{row['sales_velocity_in_stock']}` | oos days est `{row['estimated_oos_days']}`"
        )
    lines.extend(["", "## Что стоит дозакупить сейчас", ""])
    for row in summary["reorder_now"][:15]:
        lines.append(
            f"- {row['title']} | velocity(in-stock) `{row['sales_velocity_in_stock']}` | stock `{row['total_stock']}` | cover `{row['stock_cover_days']}` days | lost units est `{row['estimated_lost_units_oos']}`"
        )
    lines.extend(["", "## Что рискует закончиться", ""])
    for row in summary["stockout_risk"][:15]:
        lines.append(
            f"- {row['title']} | velocity(in-stock) `{row['sales_velocity_in_stock']}` | stock `{row['total_stock']}` | cover `{row['stock_cover_days']}` days | oos days est `{row['estimated_oos_days']}`"
        )
    lines.extend(["", "## Что лежит без движения", ""])
    for row in summary["stale_stock"][:15]:
        lines.append(
            f"- {row['title']} | stock `{row['total_stock']}` | stock value `{row['stock_value_sale']} ₽` | status `{row.get('status', '')}`"
        )
    lines.extend(["", "## Лидеры по прибыли", ""])
    for row in summary["profit_leaders"][:15]:
        lines.append(
            f"- {row['title']} | profit `{row['gross_profit']} ₽` | sold `{row['units_sold']}` | margin `{row['profit_margin_pct']}%`"
        )
    lines.extend(["", "## Семейства товаров с вариантами", ""])
    lines.append(
        f"- всего семейств: `{summary.get('family_rows', 0)}` | семейств с несколькими вариантами: `{summary.get('multi_variant_families', 0)}`"
    )
    lines.extend(["", "### Что продаётся на уровне семейства", ""])
    for row in summary["family_current_winners"][:10]:
        lines.append(
            f"- {row['title']} | variants `{row['variant_count']}` | sold `{row['sold_units_sum']}` | net `{row['net_revenue_sum']} ₽`"
        )
    lines.extend(["", "### Где проблема может быть в конкретных вариантах, а не в карточке целиком", ""])
    for row in summary["largest_multi_variant_families"][:10]:
        lines.append(
            f"- {row['title']} | variants `{row['variant_count']}` | barcodes `{row['barcode_count']}` | stock `{row['stock_units_sum']}` | sold `{row['sold_units_sum']}`"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
