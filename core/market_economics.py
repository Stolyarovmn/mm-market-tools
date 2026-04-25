#!/usr/bin/env python3
import csv
import statistics
from collections import defaultdict
from pathlib import Path

from core.market_analysis import classify_group, entry_window_profile, entry_window_strategy, market_margin_fit_profile
from core.io_utils import load_json


def load_my_group_economics(path):
    report_path = Path(path)
    if not report_path.exists():
        return {}

    payload = load_json(report_path)
    rows = payload.get("rows_payload") or payload.get("rows") or []
    grouped = defaultdict(list)
    for row in rows:
        title = row.get("title") or ""
        group = classify_group(title)
        sale_price = float(row.get("sale_price") or 0.0)
        cogs = float(row.get("cogs") or 0.0)
        if sale_price > 0 and cogs > 0:
            grouped[group].append(
                {
                    "sale_price": sale_price,
                    "cogs": cogs,
                    "gross_margin_pct": ((sale_price - cogs) / sale_price) * 100 if sale_price else 0.0,
                    "source": "official",
                }
            )
    return _aggregate_group_economics(grouped)


def load_fill_cogs_rows(path):
    fill_path = Path(path)
    if not fill_path.exists():
        return []
    rows = []
    with open(fill_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_cogs = (row.get("fill_cogs") or "").strip().replace(",", ".")
            if not raw_cogs:
                continue
            try:
                cogs = float(raw_cogs)
            except ValueError:
                continue
            sale_price = float((row.get("sale_price") or 0) or 0)
            if sale_price <= 0 or cogs <= 0:
                continue
            group = row.get("group") or classify_group(row.get("title") or "")
            rows.append(
                {
                    "group": group,
                    "title": row.get("title"),
                    "sku": row.get("sku"),
                    "sale_price": sale_price,
                    "cogs": cogs,
                    "gross_margin_pct": ((sale_price - cogs) / sale_price) * 100 if sale_price else 0.0,
                    "source": row.get("fill_source") or "fill_template",
                    "comment": row.get("fill_comment") or "",
                }
            )
    return rows


def load_cogs_override_rows(path):
    store_path = Path(path)
    if not store_path.exists():
        return []
    payload = load_json(store_path)
    rows = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows:
        try:
            cogs = float(row.get("cogs") or row.get("fill_cogs") or 0.0)
            sale_price = float(row.get("sale_price") or 0.0)
        except (TypeError, ValueError):
            continue
        if sale_price <= 0 or cogs <= 0:
            continue
        group = row.get("group") or classify_group(row.get("title") or "")
        result.append(
            {
                "group": group,
                "title": row.get("title"),
                "sku": row.get("sku"),
                "seller_sku_id": row.get("seller_sku_id"),
                "product_id": row.get("product_id"),
                "sale_price": sale_price,
                "cogs": cogs,
                "gross_margin_pct": ((sale_price - cogs) / sale_price) * 100 if sale_price else 0.0,
                "source": row.get("source") or "cogs_override_store",
                "comment": row.get("comment") or row.get("fill_comment") or "",
            }
        )
    return result


def merge_group_economics(base_group_economics, fill_rows):
    grouped = defaultdict(list)
    for group, metrics in (base_group_economics or {}).items():
        sample_size = int(metrics.get("sample_size") or 0)
        avg_sale = float(metrics.get("my_avg_sale_price") or 0.0)
        avg_cogs = float(metrics.get("my_avg_cogs") or 0.0)
        avg_margin = float(metrics.get("my_avg_gross_margin_pct") or 0.0)
        for _ in range(sample_size):
            grouped[group].append(
                {
                    "sale_price": avg_sale,
                    "cogs": avg_cogs,
                    "gross_margin_pct": avg_margin,
                    "source": "official_aggregate",
                }
            )
    for row in fill_rows or []:
        grouped[row["group"]].append(row)
    return _aggregate_group_economics(grouped)


def apply_market_margin_fit(payload, my_group_economics, *, target_margin_pct):
    payload = dict(payload)
    payload["groups"] = [dict(row) for row in payload.get("groups", [])]
    payload["entry_windows"] = [dict(row) for row in payload.get("entry_windows", [])]

    groups_with_fit = 0
    for row in payload.get("groups", []):
        economics = my_group_economics.get(row["group"]) or {}
        avg_cogs = economics.get("my_avg_cogs")
        market_avg = row.get("avg_price") or 0.0
        market_margin_fit_pct = None
        if avg_cogs and market_avg:
            market_margin_fit_pct = round(((market_avg - avg_cogs) / market_avg) * 100, 2)
            groups_with_fit += 1
        row["my_avg_cogs"] = avg_cogs
        row["my_avg_gross_margin_pct"] = economics.get("my_avg_gross_margin_pct")
        row["economics_sample_size"] = economics.get("sample_size")
        row["market_margin_fit_pct"] = market_margin_fit_pct
        row["target_margin_pct"] = target_margin_pct
        row["margin_vs_target_pct"] = round(market_margin_fit_pct - target_margin_pct, 2) if market_margin_fit_pct is not None else None
        row["market_margin_fit_profile"] = market_margin_fit_profile(
            market_margin_fit_pct,
            target_margin_pct=target_margin_pct,
        )

    windows_with_fit = 0
    for row in payload.get("entry_windows", []):
        economics = my_group_economics.get(row["group"]) or {}
        avg_cogs = economics.get("my_avg_cogs")
        market_avg = row.get("avg_price") or 0.0
        market_margin_fit_pct = None
        if avg_cogs and market_avg:
            market_margin_fit_pct = round(((market_avg - avg_cogs) / market_avg) * 100, 2)
            windows_with_fit += 1
        row["my_avg_cogs"] = avg_cogs
        row["my_avg_gross_margin_pct"] = economics.get("my_avg_gross_margin_pct")
        row["economics_sample_size"] = economics.get("sample_size")
        row["market_margin_fit_pct"] = market_margin_fit_pct
        row["target_margin_pct"] = target_margin_pct
        row["margin_vs_target_pct"] = round(market_margin_fit_pct - target_margin_pct, 2) if market_margin_fit_pct is not None else None
        row["market_margin_fit_profile"] = market_margin_fit_profile(
            market_margin_fit_pct,
            target_margin_pct=target_margin_pct,
        )

        base_score = float(row.get("entry_window_score") or 0.0)
        if market_margin_fit_pct is not None:
            if market_margin_fit_pct < max(20.0, target_margin_pct - 15):
                base_score -= 25
            elif market_margin_fit_pct < max(25.0, target_margin_pct - 10):
                base_score -= 10
            elif market_margin_fit_pct >= target_margin_pct + 10:
                base_score += 8
        base_score = round(max(0.0, min(100.0, base_score)), 2)
        row["entry_window_score"] = base_score
        row["entry_window_profile"] = entry_window_profile(base_score)
        row.update(
            entry_window_strategy(
                score=base_score,
                hhi=row.get("dominance_hhi"),
                novelty_index=row.get("novelty_proxy_index"),
                leader_share=row.get("leading_seller_share_pct"),
                market_margin_fit_pct=market_margin_fit_pct,
                target_margin_pct=target_margin_pct,
            )
        )

    payload["entry_windows"] = sorted(
        payload.get("entry_windows", []),
        key=lambda row: (row["entry_window_score"], row["orders_sum"]),
        reverse=True,
    )
    summary = dict(payload.get("summary") or {})
    group_count = len(payload.get("groups", []))
    window_count = len(payload.get("entry_windows", []))
    summary["target_margin_pct"] = target_margin_pct
    summary["economics_coverage_groups_pct"] = round((groups_with_fit / group_count) * 100, 2) if group_count else None
    summary["economics_coverage_windows_pct"] = round((windows_with_fit / window_count) * 100, 2) if window_count else None
    summary["entry_ready_windows_count"] = sum(1 for row in payload.get("entry_windows", []) if row.get("entry_strategy_bucket") == "enter_now")
    summary["test_entry_windows_count"] = sum(1 for row in payload.get("entry_windows", []) if row.get("entry_strategy_bucket") in {"test_entry", "validate_economics"})
    summary["avoid_windows_count"] = sum(1 for row in payload.get("entry_windows", []) if row.get("entry_strategy_bucket") in {"avoid", "improve_sourcing"})
    payload["summary"] = summary
    return payload


def _aggregate_group_economics(grouped):
    result = {}
    for group, items in grouped.items():
        if not items:
            continue
        sale_prices = [item["sale_price"] for item in items]
        cogs_values = [item["cogs"] for item in items]
        margins = [item["gross_margin_pct"] for item in items]
        result[group] = {
            "my_avg_sale_price": round(sum(sale_prices) / len(sale_prices), 2),
            "my_avg_cogs": round(sum(cogs_values) / len(cogs_values), 2),
            "my_median_cogs": round(statistics.median(cogs_values), 2),
            "my_avg_gross_margin_pct": round(sum(margins) / len(margins), 2),
            "sample_size": len(items),
        }
    return result
