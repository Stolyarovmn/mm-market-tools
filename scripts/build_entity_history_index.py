#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.entity_history import build_entity_history_index
from core.io_utils import write_json
from core.paths import DASHBOARD_DIR, ENTITY_HISTORY_INDEX_PATH


def parse_args():
    parser = argparse.ArgumentParser(description="Build entity history index for dashboard entity drilldown.")
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--output", default=str(ENTITY_HISTORY_INDEX_PATH))
    return parser.parse_args()


def main():
    args = parse_args()
    payload = build_entity_history_index(args.dashboard_dir)
    output = Path(args.output)
    write_json(output, payload)
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
