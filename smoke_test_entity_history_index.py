#!/usr/bin/env python3
import argparse
from pathlib import Path

from core.io_utils import load_json


def parse_args():
    parser = argparse.ArgumentParser(description="Smoke-test entity history index for dashboard drilldown.")
    parser.add_argument(
        "--entity-history-json",
        default="/home/user/mm-market-tools/data/local/entity_history_index.json",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = load_json(Path(args.entity_history_json))
    assert payload.get("schema_version"), "missing schema_version"
    assert "entity_count" in payload, "missing entity_count"
    assert "entities" in payload, "missing entities"
    if payload["entities"]:
        first = payload["entities"][0]
        assert "entity_key" in first, "entity missing entity_key"
        assert "history" in first, "entity missing history"
        assert "latest" in first, "entity missing latest"
    print("SMOKE_ENTITY_HISTORY_OK")


if __name__ == "__main__":
    main()
