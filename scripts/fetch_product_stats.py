#!/usr/bin/env python3
"""
Fetch per-product stats (viewers, clicks, conversion, roi) from the seller cabinet.

Saves to data/local/product_stats.json — used downstream by:
  - build_quick_wins.py   (traffic / conversion quick-wins)
  - build_daily_action_plan.py

Usage:
  python scripts/fetch_product_stats.py --token TOKEN [--shop-id 98]
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.http_client import create_session
from core.io_utils import write_json
from core.paths import PROJECT_ROOT
from core.product_stats_api import fetch_all_product_stats

from core.logging_config import get_logger
log = get_logger('scripts.fetch_product_stats')

OUTPUT_PATH = PROJECT_ROOT / "data" / "local" / "product_stats.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--shop-id", type=int, default=98)
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--max-pages", type=int, default=50)
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with create_session() as session:
        products = fetch_all_product_stats(
            session, args.token, args.shop_id,
            max_pages=args.max_pages,
        )

    payload = {
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "shop_id": args.shop_id,
        "count": len(products),
        "products": products,
    }
    write_json(out_path, payload)
    log.info("Saved %d products → %s", len(products), out_path)

    # Quick summary
    with_viewers = [p for p in products if p["viewers"] is not None]
    zero_viewers = [p for p in with_viewers if p["viewers"] == 0]
    low_conv = [p for p in with_viewers
                if p["viewers"] and p["conversion"] is not None and p["conversion"] < 1.0]
    print(f"✓ {len(products)} products saved")
    print(f"  {len(with_viewers)} have viewers data "
          f"({len(zero_viewers)} zero, {len(low_conv)} low conversion <1%)")
    print(f"  → {out_path}")


if __name__ == "__main__":
    main()
