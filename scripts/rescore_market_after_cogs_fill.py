#!/usr/bin/env python3
import argparse
import copy
import datetime as dt
from pathlib import Path

from core.io_utils import load_json, write_json
from core.market_dashboard import build_market_dashboard
from core.market_economics import (
    apply_market_margin_fit,
    load_cogs_override_rows,
    load_fill_cogs_rows,
    load_my_group_economics,
    merge_group_economics,
)
from core.paths import COGS_OVERRIDES_PATH, DASHBOARD_DIR, NORMALIZED_DIR, REPORTS_DIR, ensure_dir


DEFAULT_MARKET_JSON = str(NORMALIZED_DIR / "competitor_market_analysis_2026-04-09g.json")
DEFAULT_OFFICIAL_JSON = str(REPORTS_DIR / "official_period_analysis_2026-04-08.json")
DEFAULT_FILL_CSV = str(REPORTS_DIR / "cogs_fill_template_2026-04-09a.csv")
DEFAULT_REPORT_DIR = str(REPORTS_DIR)
DEFAULT_DATE = dt.date.today().isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Re-score market economics after filling COGS in the template CSV.")
    parser.add_argument("--market-json", default=DEFAULT_MARKET_JSON)
    parser.add_argument("--official-report-json", default=DEFAULT_OFFICIAL_JSON)
    parser.add_argument("--cogs-fill-csv", default=DEFAULT_FILL_CSV)
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--normalized-dir", default=str(NORMALIZED_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--cogs-overrides-json", default=str(COGS_OVERRIDES_PATH))
    parser.add_argument("--target-margin-pct", type=float, default=35.0)
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    return parser.parse_args()


def summarize_delta(before, after):
    before_summary = before.get("summary") or {}
    after_summary = after.get("summary") or {}
    before_windows = {(row["group"], row["price_band"]): row for row in before.get("entry_windows") or []}
    after_windows = {(row["group"], row["price_band"]): row for row in after.get("entry_windows") or []}

    promoted = []
    for key, row in after_windows.items():
        before_row = before_windows.get(key) or {}
        if before_row.get("entry_strategy_bucket") == row.get("entry_strategy_bucket"):
            continue
        promoted.append(
            {
                "group": row["group"],
                "price_band": row["price_band"],
                "before_bucket": before_row.get("entry_strategy_bucket"),
                "after_bucket": row.get("entry_strategy_bucket"),
                "before_score": before_row.get("entry_window_score"),
                "after_score": row.get("entry_window_score"),
                "after_margin_fit_pct": row.get("market_margin_fit_pct"),
            }
        )
    promoted.sort(key=lambda row: (row.get("after_score") or 0), reverse=True)

    return {
        "before_economics_coverage_windows_pct": before_summary.get("economics_coverage_windows_pct"),
        "after_economics_coverage_windows_pct": after_summary.get("economics_coverage_windows_pct"),
        "before_test_entry_windows_count": before_summary.get("test_entry_windows_count"),
        "after_test_entry_windows_count": after_summary.get("test_entry_windows_count"),
        "before_entry_ready_windows_count": before_summary.get("entry_ready_windows_count"),
        "after_entry_ready_windows_count": after_summary.get("entry_ready_windows_count"),
        "promoted_windows": promoted[:20],
    }


def write_markdown(path, delta, fill_rows_count):
    lines = [
        f"# Re-score Market After COGS Fill {DEFAULT_DATE}",
        "",
        f"- fill_rows_count: `{fill_rows_count}`",
        f"- economics_coverage_windows_pct before: `{delta.get('before_economics_coverage_windows_pct')}`",
        f"- economics_coverage_windows_pct after: `{delta.get('after_economics_coverage_windows_pct')}`",
        f"- test_entry_windows before: `{delta.get('before_test_entry_windows_count')}`",
        f"- test_entry_windows after: `{delta.get('after_test_entry_windows_count')}`",
        f"- entry_ready_windows before: `{delta.get('before_entry_ready_windows_count')}`",
        f"- entry_ready_windows after: `{delta.get('after_entry_ready_windows_count')}`",
        "",
        "## Окна, которые изменили решение",
        "",
    ]
    for row in delta.get("promoted_windows") or []:
        lines.append(
            f"- {row['group']} / {row['price_band']} | `{row.get('before_bucket')}` -> `{row.get('after_bucket')}` | score `{row.get('before_score')}` -> `{row.get('after_score')}` | margin fit `{row.get('after_margin_fit_pct')}`"
        )
    if not delta.get("promoted_windows"):
        lines.append("- Заполненные COGS пока не изменили strategy bucket ни для одного окна.")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse_args()
    market_payload = load_json(args.market_json)
    before_payload = copy.deepcopy(market_payload)
    base_group_economics = load_my_group_economics(args.official_report_json)
    override_rows = load_cogs_override_rows(args.cogs_overrides_json)
    fill_rows = load_fill_cogs_rows(args.cogs_fill_csv)
    merged_group_economics = merge_group_economics(base_group_economics, [*override_rows, *fill_rows])
    rescored_payload = apply_market_margin_fit(
        market_payload,
        merged_group_economics,
        target_margin_pct=args.target_margin_pct,
    )
    delta = summarize_delta(before_payload, rescored_payload)

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir = ensure_dir(Path(args.normalized_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))

    json_path = report_dir / f"market_rescored_after_cogs_{args.date_tag}.json"
    md_path = report_dir / f"market_rescored_after_cogs_{args.date_tag}.md"
    normalized_path = normalized_dir / f"market_rescored_after_cogs_{args.date_tag}.json"
    dashboard_path = dashboard_dir / f"market_rescored_after_cogs_{args.date_tag}.json"

    source_metadata = market_payload.get("metadata") or {}
    merged_metadata = {
        **source_metadata,
        "rescored_from_fill": True,
        "source_market_json": args.market_json,
        "source_official_report_json": args.official_report_json,
        "source_fill_csv": args.cogs_fill_csv,
        "source_cogs_overrides_json": args.cogs_overrides_json,
        "target_margin_pct": args.target_margin_pct,
        "fill_rows_count": len(fill_rows),
        "override_rows_count": len(override_rows),
    }
    output_payload = {
        "metadata": merged_metadata,
        "delta": delta,
        "payload": rescored_payload,
    }
    write_json(json_path, output_payload)
    write_markdown(md_path, delta, len(fill_rows))
    write_json(normalized_path, output_payload)
    write_json(dashboard_path, build_market_dashboard(rescored_payload, metadata=merged_metadata))
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {normalized_path}")
    print(f"Saved: {dashboard_path}")


if __name__ == "__main__":
    main()
