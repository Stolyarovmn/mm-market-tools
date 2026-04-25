#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill schema_version into existing dashboard bundles.")
    parser.add_argument("--dashboard-dir", default="/home/user/mm-market-tools/data/dashboard")
    return parser.parse_args()


def main():
    args = parse_args()
    dashboard_dir = Path(args.dashboard_dir)
    updated = 0
    for path in sorted(dashboard_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version"):
            continue
        payload["schema_version"] = DASHBOARD_SCHEMA_VERSION
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        updated += 1
        print(f"Updated: {path}")
    print(f"Done. updated={updated}")


if __name__ == "__main__":
    main()
