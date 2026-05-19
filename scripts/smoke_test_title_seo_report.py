#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from core.paths import REPORTS_DIR


def parse_args():
    parser = argparse.ArgumentParser(description="Smoke test for title SEO report.")
    parser.add_argument(
        "--report-json",
        default=str(REPORTS_DIR / "title_seo_report_2026-04-10.json"),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    assert "summary" in payload, "missing summary"
    assert "rows" in payload, "missing rows"
    summary = payload["summary"]
    for key in [
        "audited_rows",
        "priority_fix_count",
        "needs_work_count",
        "strong_count",
        "main_noun_late_count",
        "entity_late_count",
    ]:
        assert key in summary, f"missing summary key: {key}"
    if payload["rows"]:
        row = payload["rows"][0]
        for key in ["title", "seo_score", "seo_status", "issues", "recommendations"]:
            assert key in row, f"missing row field: {key}"
    print("SMOKE_TITLE_SEO_OK")
    print(summary)


if __name__ == "__main__":
    main()
