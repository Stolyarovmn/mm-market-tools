#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Smoke test for description SEO richness dashboard bundle.")
    parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_json = tmp_path / "marketing_card_audit_fixture.json"
        cache_json = tmp_path / "product_content_cache.json"
        reports_dir = tmp_path / "reports"
        dashboard_dir = tmp_path / "dashboard"
        fixture = {
            "rows": [
                {"key": "sku-1", "product_id": 101, "title": "Пазл Три кота", "group": "Пазлы", "price_band": "200-499", "units_sold": 4, "stock_value_sale": 1200},
                {"key": "sku-2", "product_id": 202, "title": "Магнитная игра Азбука", "group": "Магнитные игры и одевашки", "price_band": "200-499", "units_sold": 1, "stock_value_sale": 400},
            ]
        }
        cache = {
            "101": {"product": {"title": "Пазл Три кота", "photos": [1], "attributes": [], "characteristics": [], "description": "Пазл для детей"}},
            "202": {"product": {"title": "Магнитная игра Азбука", "photos": [1, 2], "attributes": [], "characteristics": [], "description": "Магнитная игра Азбука помогает изучать буквы, слова и собирать карточки. В наборе элементы для занятий дома, в дороге и в игре."}},
        }
        input_json.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
        cache_json.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

        cmd = [
            "python3",
            str(PROJECT_ROOT / "build_description_seo_richness_report.py"),
            "--input-json",
            str(input_json),
            "--cache-json",
            str(cache_json),
            "--cache-only",
            "--report-dir",
            str(reports_dir),
            "--dashboard-dir",
            str(dashboard_dir),
            "--report-prefix",
            "description_smoke",
        ]
        subprocess.run(cmd, check=True)
        bundle = json.loads((dashboard_dir / "description_smoke.json").read_text(encoding="utf-8"))
        assert bundle["kpis"]["total_skus"] == 2
        assert bundle["kpis"]["priority_cards_count"] >= 1
    print("SMOKE_DESCRIPTION_SEO_OK")


if __name__ == "__main__":
    main()
