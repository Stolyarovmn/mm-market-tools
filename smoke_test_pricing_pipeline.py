#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from core.paths import DASHBOARD_DIR


def parse_args():
    parser = argparse.ArgumentParser(description="Smoke test for dynamic pricing dashboard bundle.")
    parser.add_argument(
        "--dashboard-json",
        default=str(DASHBOARD_DIR / "dynamic_pricing_2026-04-10.json"),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = json.loads(Path(args.dashboard_json).read_text(encoding="utf-8"))
    assert payload.get("metadata", {}).get("pricing"), "missing pricing metadata"
    assert payload.get("kpis"), "missing kpis"
    assert payload.get("actions"), "missing actions"
    assert payload.get("tables"), "missing tables"
    assert payload.get("charts"), "missing charts"
    assert "priced_windows" in payload["tables"], "missing priced_windows table"
    assert "pricing_labels" in payload["charts"], "missing pricing_labels chart"
    assert payload["kpis"].get("priced_windows_count") is not None, "missing priced_windows_count"
    print("SMOKE_PRICING_OK")
    print(payload["metadata"]["pricing"])
    print(payload["kpis"])


if __name__ == "__main__":
    main()
