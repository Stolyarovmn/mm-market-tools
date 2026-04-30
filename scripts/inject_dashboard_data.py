#!/usr/bin/env python3
"""Inject fresh dashboard data into docs/index.html.

Reads data/dashboard/index.json and replaces the PAYLOAD constant
in docs/index.html so GitHub Pages always serves current data.

Usage:
    python scripts/inject_dashboard_data.py
    python scripts/inject_dashboard_data.py --data path/to/index.json --template path/to/template.html
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_DATA = ROOT / "data" / "dashboard" / "index.json"
DEFAULT_TEMPLATE = ROOT / "docs" / "index.html"


def inject(data_path: Path, template_path: Path) -> None:
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    data = json.loads(data_path.read_text(encoding="utf-8"))
    html = template_path.read_text(encoding="utf-8")

    new_payload = "const PAYLOAD = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    updated, count = re.subn(
        r"const PAYLOAD = \{.*?\};",
        new_payload,
        html,
        count=1,
        flags=re.DOTALL,
    )

    if count == 0:
        raise ValueError("PAYLOAD constant not found in template — check docs/index.html structure")

    template_path.write_text(updated, encoding="utf-8")
    size_kb = len(updated) // 1024
    print(f"docs/index.html updated ({size_kb}KB) from {data_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject dashboard data into docs/index.html")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="Path to index.json")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to docs/index.html")
    args = parser.parse_args()
    inject(Path(args.data), Path(args.template))


if __name__ == "__main__":
    main()
