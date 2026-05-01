#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
from pathlib import Path

from build_zero_cogs_registry import build_registry, write_markdown as write_registry_markdown
from core.io_utils import load_json, write_json
from core.market_economics import apply_market_margin_fit, load_cogs_override_rows, load_my_group_economics, merge_group_economics
from core.market_dashboard import build_market_dashboard
from core.paths import COGS_OVERRIDES_PATH, DASHBOARD_DIR, NORMALIZED_DIR, REPORTS_DIR, ensure_dir
from ingest_cogs_fill import merge_rows


DEFAULT_DATE = dt.date.today().isoformat()
DEFAULT_OFFICIAL_JSON = str(REPORTS_DIR / "official_period_analysis_2026-04-08.json")
DEFAULT_BACKLOG_JSON = str(REPORTS_DIR / "cost_coverage_backlog_2026-04-09a.json")
DEFAULT_MARKET_JSON = str(NORMALIZED_DIR / "competitor_market_analysis_2026-04-09g.json")


def parse_args():
    parser = argparse.ArgumentParser(description="Run persistent COGS backfill cycle: ingest fill CSV, rebuild registry/template, and rescore market.")
    parser.add_argument("--fill-csv")
    parser.add_argument("--store-json", default=str(COGS_OVERRIDES_PATH))
    parser.add_argument("--official-json", default=DEFAULT_OFFICIAL_JSON)
    parser.add_argument("--backlog-json", default=DEFAULT_BACKLOG_JSON)
    parser.add_argument("--market-json", default=DEFAULT_MARKET_JSON)
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--normalized-dir", default=str(NORMALIZED_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--target-margin-pct", type=float, default=35.0)
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    return parser.parse_args()


def write_template_csv(path, payload):
    rows = []
    for item in payload.get("items", []):
        rows.append(
            {
                "group": item.get("group"),
                "title": item.get("title"),
                "sku": item.get("sku"),
                "seller_sku_id": item.get("seller_sku_id"),
                "product_id": item.get("product_id"),
                "sale_price": item.get("sale_price"),
                "total_stock": item.get("total_stock"),
                "units_sold_window": item.get("units_sold"),
                "priority_score": item.get("priority_score"),
                "fill_cogs": "",
                "fill_source": "",
                "fill_comment": "",
            }
        )
    fieldnames = [
        "group", "title", "sku", "seller_sku_id", "product_id", "sale_price",
        "total_stock", "units_sold_window", "priority_score", "fill_cogs", "fill_source", "fill_comment",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_cycle_markdown(path, *, date_tag, import_summary, registry_summary, rescored_summary, created_files):
    lines = [
        f"# COGS Backfill Cycle {date_tag}",
        "",
        "## Import",
        "",
        f"- imported_rows: `{import_summary.get('fill_rows_imported', 0)}`",
        f"- created_rows: `{import_summary.get('created_rows', 0)}`",
        f"- updated_rows: `{import_summary.get('updated_rows', 0)}`",
        "",
        "## Coverage",
        "",
        f"- zero_cogs_group_count: `{registry_summary.get('zero_cogs_group_count')}`",
        f"- zero_cogs_sku_total: `{registry_summary.get('zero_cogs_sku_total')}`",
        "",
    ]
    if rescored_summary:
        lines.extend(
            [
                "## Rescore",
                "",
                f"- economics_coverage_windows_pct: `{rescored_summary.get('economics_coverage_windows_pct')}`",
                f"- entry_ready_windows_count: `{rescored_summary.get('entry_ready_windows_count')}`",
                f"- test_entry_windows_count: `{rescored_summary.get('test_entry_windows_count')}`",
                f"- avoid_windows_count: `{rescored_summary.get('avoid_windows_count')}`",
                "",
            ]
        )
    lines.extend(["## Артефакты", ""])
    for file_path in created_files:
        lines.append(f"- `{file_path}`")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    normalized_dir = ensure_dir(Path(args.normalized_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))
    store_path = Path(args.store_json)
    ensure_dir(store_path.parent)

    existing_rows = load_cogs_override_rows(store_path)
    import_summary = {"fill_rows_imported": 0, "created_rows": 0, "updated_rows": 0}
    if args.fill_csv:
        from core.market_economics import load_fill_cogs_rows
        fill_rows = load_fill_cogs_rows(args.fill_csv)
        merged_rows, created, updated = merge_rows(existing_rows, fill_rows)
        store_payload = {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "date_tag": args.date_tag,
            "source_fill_csv": args.fill_csv,
            "summary": {
                "items_total": len(merged_rows),
                "fill_rows_imported": len(fill_rows),
                "created_rows": created,
                "updated_rows": updated,
            },
            "items": merged_rows,
        }
        write_json(store_path, store_payload)
        existing_rows = merged_rows
        import_summary = store_payload["summary"]

    official_payload = load_json(args.official_json)
    backlog_payload = load_json(args.backlog_json)
    registry_payload = build_registry(official_payload, backlog_payload, existing_rows)

    registry_json = report_dir / f"zero_cogs_registry_{args.date_tag}.json"
    registry_md = report_dir / f"zero_cogs_registry_{args.date_tag}.md"
    template_csv = report_dir / f"cogs_fill_template_{args.date_tag}.csv"
    write_json(registry_json, registry_payload)
    write_registry_markdown(registry_md, registry_payload, args.date_tag)
    write_template_csv(template_csv, registry_payload)

    created_files = [str(registry_json), str(registry_md), str(template_csv)]
    rescored_summary = None
    market_path = Path(args.market_json)
    if market_path.exists():
        market_payload = load_json(market_path)
        merged_group_economics = merge_group_economics(
            load_my_group_economics(args.official_json),
            existing_rows,
        )
        rescored_payload = apply_market_margin_fit(
            market_payload,
            merged_group_economics,
            target_margin_pct=args.target_margin_pct,
        )
        rescored_summary = rescored_payload.get("summary") or {}
        rescored_json = report_dir / f"market_rescored_after_cogs_{args.date_tag}.json"
        rescored_md = report_dir / f"market_rescored_after_cogs_{args.date_tag}.md"
        rescored_normalized = normalized_dir / f"market_rescored_after_cogs_{args.date_tag}.json"
        rescored_dashboard = dashboard_dir / f"market_rescored_after_cogs_{args.date_tag}.json"
        payload = {
            "metadata": {
                **(market_payload.get("metadata") or {}),
                "rescored_from_store": True,
                "source_market_json": args.market_json,
                "source_official_json": args.official_json,
                "source_cogs_overrides_json": str(store_path),
                "target_margin_pct": args.target_margin_pct,
            },
            "payload": rescored_payload,
        }
        write_json(rescored_json, payload)
        write_json(rescored_normalized, payload)
        write_json(rescored_dashboard, build_market_dashboard(rescored_payload, metadata=payload["metadata"]))
        rescored_md.write_text(
            "\n".join(
                [
                    f"# Market Rescored After COGS {args.date_tag}",
                    "",
                    f"- economics_coverage_windows_pct: `{rescored_summary.get('economics_coverage_windows_pct')}`",
                    f"- entry_ready_windows_count: `{rescored_summary.get('entry_ready_windows_count')}`",
                    f"- test_entry_windows_count: `{rescored_summary.get('test_entry_windows_count')}`",
                    f"- avoid_windows_count: `{rescored_summary.get('avoid_windows_count')}`",
                ]
            ),
            encoding="utf-8",
        )
        created_files.extend([str(rescored_json), str(rescored_md), str(rescored_normalized), str(rescored_dashboard)])

    cycle_md = report_dir / f"cogs_backfill_cycle_{args.date_tag}.md"
    write_cycle_markdown(
        cycle_md,
        date_tag=args.date_tag,
        import_summary=import_summary,
        registry_summary=registry_payload.get("summary") or {},
        rescored_summary=rescored_summary,
        created_files=created_files,
    )
    print(f"Saved: {cycle_md}")
    for path in created_files:
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
