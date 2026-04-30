#!/usr/bin/env python3
"""
CubeJS meta inspector and query probe for seller-analytics.mm.ru.

Modes (pick one):
  --meta            List all cubes with their dimensions and measures
  --test-query JSON Run an arbitrary query and show result or exact error
  --probe-product   Auto-test all product/sku dimensions and report what works

Token is read from --token flag or $KAZANEXPRESS_TOKEN env var.
Report is always saved to reports/cubejs_meta_<YYYY-MM-DD>.json.
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

from core.cubejs_api import fetch_cubejs_meta, flatten_results, run_cubejs_query

BASE_META_URL = "https://seller-analytics.mm.ru/cubejs-api/v1/meta"
BASE_LOAD_URL = "https://seller-analytics.mm.ru/cubejs-api/v1/load"
REPORT_DIR = Path("reports")

PRODUCT_KEYWORDS = ("product", "sku", "item", "goods")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--token", default=os.getenv("KAZANEXPRESS_TOKEN"))
    p.add_argument("--cookie", default=os.getenv("MM_ANALYTICS_COOKIE"))
    p.add_argument("--shop-id", default=os.getenv("MM_MY_SHOP_ID", "98"))

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--meta", action="store_true")
    mode.add_argument("--test-query", metavar="JSON")
    mode.add_argument("--probe-product", action="store_true")

    return p.parse_args()


# ── helpers ──────────────────────────────────────────────────────────────────

def _auth(args):
    if not args.token and not args.cookie:
        print("ERROR: provide --token or set $KAZANEXPRESS_TOKEN", file=sys.stderr)
        sys.exit(1)
    return {"token": args.token, "cookie": args.cookie}


def _save(data, suffix=""):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.date.today().isoformat()
    name = f"cubejs_meta_{date}{suffix}.json"
    path = REPORT_DIR / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {path}")
    return path


def _run_query(query, auth):
    try:
        payload = run_cubejs_query(query, token=auth["token"], cookie=auth["cookie"])
        rows = flatten_results(payload)
        return {"ok": True, "rows": len(rows), "sample": rows[:2], "raw": payload}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── modes ─────────────────────────────────────────────────────────────────────

def mode_meta(args, auth):
    print("Fetching /meta …")
    try:
        meta = fetch_cubejs_meta(token=auth["token"], cookie=auth["cookie"])
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    cubes = meta.get("cubes", [])
    print(f"Total cubes: {len(cubes)}\n")

    rows = []
    for cube in cubes:
        name = cube.get("name", "")
        dims = [d["name"] for d in cube.get("dimensions", [])]
        measures = [m["name"] for m in cube.get("measures", [])]
        print(f"{'─'*60}")
        print(f"CUBE: {name}")
        print(f"  dimensions ({len(dims)}): {', '.join(dims) or '—'}")
        print(f"  measures   ({len(measures)}): {', '.join(measures[:8])}{'…' if len(measures) > 8 else ''}")
        rows.append({"cube": name, "dimensions": dims, "measures": measures})

    _save({"cubes": rows})


def mode_test_query(args, auth):
    try:
        query = json.loads(args.test_query)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON — {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Running query: {json.dumps(query, ensure_ascii=False)[:200]}")
    result = _run_query(query, auth)

    if result["ok"]:
        print(f"OK — {result['rows']} rows")
        print(f"Sample: {result['sample']}")
    else:
        print(f"ERROR: {result['error']}")

    _save(result, suffix="_test_query")


def mode_probe_product(args, auth):
    print("Fetching /meta to discover product/sku dimensions …")
    try:
        meta = fetch_cubejs_meta(token=auth["token"], cookie=auth["cookie"])
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # Collect all product-related dimensions grouped by cube
    candidates = []
    for cube in meta.get("cubes", []):
        cube_name = cube.get("name", "")
        for dim in cube.get("dimensions", []):
            dim_name = dim.get("name", "")
            local = dim_name.split(".")[-1].lower()
            if any(k in local for k in PRODUCT_KEYWORDS):
                candidates.append((cube_name, dim_name))

    if not candidates:
        print("No product/sku dimensions found in meta.")
        _save({"probed": [], "note": "no candidates"})
        return

    print(f"Found {len(candidates)} candidate dimensions — probing each …\n")

    date_to = datetime.date.today().isoformat()
    date_from = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

    results = []
    for cube_name, dim in candidates:
        # Pick a safe measure from the same cube if available, else skip gracefully
        cube_meta = next((c for c in meta.get("cubes", []) if c["name"] == cube_name), {})
        cube_measures = [m["name"] for m in cube_meta.get("measures", [])]
        if not cube_measures:
            results.append({"dim": dim, "ok": False, "error": "no measures in cube"})
            continue

        query = {
            "measures": [cube_measures[0]],
            "dimensions": [dim],
            "timeDimensions": [{"dimension": f"{cube_name}.created_at", "dateRange": [date_from, date_to]}]
            if f"{cube_name}.created_at" in [d["name"] for d in cube_meta.get("dimensions", [])]
            else [],
            "filters": [{"member": f"{cube_name}.shop_id", "operator": "equals", "values": [str(args.shop_id)]}]
            if f"{cube_name}.shop_id" in [d["name"] for d in cube_meta.get("dimensions", [])]
            else [],
            "limit": 5,
        }

        res = _run_query(query, auth)
        status = "OK" if res["ok"] else "ERR"
        detail = f"{res['rows']} rows" if res["ok"] else res["error"][:120]
        print(f"  [{status}] {dim}: {detail}")
        results.append({"dim": dim, "ok": res["ok"], "detail": detail, "query": query})

    working = [r for r in results if r["ok"]]
    print(f"\nWorking dimensions: {len(working)}/{len(results)}")

    _save({"probed": results, "working": [r["dim"] for r in working], "date_range": [date_from, date_to]})


# ── entry ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    auth = _auth(args)

    if args.meta:
        mode_meta(args, auth)
    elif args.test_query:
        mode_test_query(args, auth)
    elif args.probe_product:
        mode_probe_product(args, auth)


if __name__ == "__main__":
    main()
