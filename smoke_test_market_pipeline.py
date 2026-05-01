#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from core.paths import DASHBOARD_DIR


def parse_args():
    parser = argparse.ArgumentParser(description="Smoke test for competitor market dashboard bundle.")
    parser.add_argument(
        "--dashboard-json",
        default=str(DASHBOARD_DIR / "competitor_market_analysis_2026-04-08d.json"),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = json.loads(Path(args.dashboard_json).read_text(encoding="utf-8"))
    assert payload.get("kpis"), "missing kpis"
    assert payload.get("tables"), "missing tables"
    assert payload.get("charts"), "missing charts"
    assert payload.get("metadata", {}).get("market_scope"), "missing market_scope metadata"
    assert "top_sellers" in payload["tables"], "missing top_sellers table"
    assert "price_bands" in payload["charts"], "missing price_bands chart"
    print("SMOKE_MARKET_OK")
    print(payload["metadata"]["market_scope"])
    print(payload["kpis"])


if __name__ == "__main__":
    main()
