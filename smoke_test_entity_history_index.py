#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from core.io_utils import load_json

PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args():
    parser = argparse.ArgumentParser(description="Smoke-test entity history index for dashboard drilldown.")
    return parser.parse_args()


def main():
    parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dashboard_dir = tmp_path / "dashboard"
        output_json = tmp_path / "entity_history_index.json"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        fixture = {
            "generated_at": "2026-04-13T00:00:00Z",
            "tables": {
                "priority_cards": [
                    {
                        "key": "sku-1",
                        "product_id": 101,
                        "title": "Пазл Три кота",
                        "seo_status": "needs_work",
                        "price_trap": True,
                    }
                ]
            },
        }
        (dashboard_dir / "marketing_card_audit_fixture.json").write_text(
            json.dumps(fixture, ensure_ascii=False), encoding="utf-8"
        )
        subprocess.run(
            [
                "python3",
                str(PROJECT_ROOT / "build_entity_history_index.py"),
                "--dashboard-dir",
                str(dashboard_dir),
                "--output",
                str(output_json),
            ],
            check=True,
        )
        payload = load_json(output_json)
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
