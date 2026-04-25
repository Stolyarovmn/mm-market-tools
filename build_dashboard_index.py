#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.dashboard_index import build_dashboard_index
from core.entity_history import build_entity_history_index
from core.io_utils import write_json
from core.paths import DASHBOARD_DIR, ENTITY_HISTORY_INDEX_PATH, ensure_dir


def parse_args():
    parser = argparse.ArgumentParser(description="Build dashboard index for browser UI.")
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--output", default=str(DASHBOARD_DIR / "index.json"))
    return parser.parse_args()


def main():
    args = parse_args()
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))
    output = Path(args.output)
    payload = build_dashboard_index(dashboard_dir)
    write_json(output, payload)
    entity_history = build_entity_history_index(dashboard_dir)
    write_json(ENTITY_HISTORY_INDEX_PATH, entity_history)
    print(f"Saved: {output}")
    print(f"Saved: {ENTITY_HISTORY_INDEX_PATH}")


if __name__ == "__main__":
    main()
