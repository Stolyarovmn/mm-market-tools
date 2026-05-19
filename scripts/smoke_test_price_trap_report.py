#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from core.paths import REPORTS_DIR


def parse_args():
    parser = argparse.ArgumentParser(description="Smoke test for price trap marketing report.")
    parser.add_argument(
        "--report-json",
        default=str(REPORTS_DIR / "price_trap_report_2026-04-10.json"),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    assert "rows" in payload, "missing rows"
    assert "summary" in payload, "missing summary"
    assert payload["summary"].get("matched_skus") is not None, "missing matched_skus"
    if payload["rows"]:
      row = payload["rows"][0]
      for key in ["title", "sale_price", "threshold", "suggested_price", "overshoot_rub"]:
          assert key in row, f"missing row field: {key}"
    print("SMOKE_PRICE_TRAP_OK")
    print(payload["summary"])


if __name__ == "__main__":
    main()
