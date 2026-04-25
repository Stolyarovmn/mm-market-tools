#!/usr/bin/env python3
import argparse
from pathlib import Path

from core.io_utils import load_json


def parse_args():
    parser = argparse.ArgumentParser(description="Smoke-test unified marketing card audit dashboard bundle.")
    parser.add_argument(
        "--dashboard-json",
        default="/home/user/mm-market-tools/data/dashboard/marketing_card_audit_2026-04-10.json",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = load_json(Path(args.dashboard_json))
    assert payload.get("schema_version"), "missing schema_version"
    kpis = payload.get("kpis") or {}
    tables = payload.get("tables") or {}
    actions = payload.get("actions") or {}
    assert "priority_cards_count" in kpis, "missing priority_cards_count"
    assert "price_trap_cards_count" in kpis, "missing price_trap_cards_count"
    assert "seo_needs_work_count" in kpis, "missing seo_needs_work_count"
    assert "priority_cards" in tables, "missing priority_cards table"
    assert "price_traps" in tables, "missing price_traps table"
    assert "seo_fixes" in tables, "missing seo_fixes table"
    assert "fix_now" in actions, "missing fix_now action"
    assert "price_tests" in actions, "missing price_tests action"
    assert "title_fixes" in actions, "missing title_fixes action"
    print("SMOKE_MARKETING_CARD_AUDIT_OK")


if __name__ == "__main__":
    main()
