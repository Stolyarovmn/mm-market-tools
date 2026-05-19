#!/usr/bin/env python3
import argparse
import datetime as dt
from pathlib import Path

from core.io_utils import write_json
from core.market_economics import load_cogs_override_rows, load_fill_cogs_rows
from core.paths import COGS_OVERRIDES_PATH, ensure_dir


DEFAULT_DATE = dt.date.today().isoformat()


def parse_args():
    parser = argparse.ArgumentParser(description="Import filled COGS CSV rows into persistent local override storage.")
    parser.add_argument("--fill-csv", required=True)
    parser.add_argument("--store-json", default=str(COGS_OVERRIDES_PATH))
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    return parser.parse_args()


def _identity_key(row):
    return (
        str(row.get("sku") or "").strip(),
        str(row.get("seller_sku_id") or "").strip(),
        str(row.get("product_id") or "").strip(),
        str(row.get("title") or "").strip().lower(),
    )


def merge_rows(existing_rows, new_rows):
    merged = {}
    for row in existing_rows:
        merged[_identity_key(row)] = dict(row)
    updated = 0
    created = 0
    for row in new_rows:
        key = _identity_key(row)
        normalized = {
            "group": row.get("group"),
            "title": row.get("title"),
            "sku": row.get("sku"),
            "seller_sku_id": row.get("seller_sku_id"),
            "product_id": row.get("product_id"),
            "sale_price": row.get("sale_price"),
            "cogs": row.get("cogs"),
            "gross_margin_pct": row.get("gross_margin_pct"),
            "source": row.get("source") or "fill_template",
            "comment": row.get("comment") or "",
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        if key in merged:
            updated += 1
        else:
            created += 1
        merged[key] = normalized
    rows = list(merged.values())
    rows.sort(key=lambda row: (row.get("group") or "", row.get("title") or "", row.get("sku") or ""))
    return rows, created, updated


def main():
    args = parse_args()
    store_path = Path(args.store_json)
    ensure_dir(store_path.parent)
    existing_rows = load_cogs_override_rows(store_path)
    fill_rows = load_fill_cogs_rows(args.fill_csv)
    merged_rows, created, updated = merge_rows(existing_rows, fill_rows)
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "date_tag": args.date_tag,
        "source_fill_csv": args.fill_csv,
        "summary": {
            "items_total": len(merged_rows),
            "fill_rows_imported": len(fill_rows),
            "created_rows": created,
            "updated_rows": updated,
        },
        "items": merged_rows,
    }
    write_json(store_path, payload)
    print(f"Saved: {store_path}")
    print(f"Imported rows: {len(fill_rows)}")
    print(f"Created rows: {created}")
    print(f"Updated rows: {updated}")


if __name__ == "__main__":
    main()
