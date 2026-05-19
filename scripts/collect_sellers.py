#!/usr/bin/env python3
import argparse
import os
import sys

from core.auth import bearer_headers, require_access_token
from core.http_client import create_session


DEFAULT_CATEGORY_TREE_URL = "https://api.business.kazanexpress.ru/api/seller/category/tree"


def fetch_category_tree(token, timeout=20):
    with create_session() as session:
        response = session.get(
            DEFAULT_CATEGORY_TREE_URL,
            headers=bearer_headers(token),
            timeout=timeout,
        )
        body = response.text
        if not response.ok:
            return response.status_code, None, body
        try:
            return response.status_code, response.json(), body
        except ValueError:
            return response.status_code, None, body


def find_category(node, target_id):
    if isinstance(node, list):
        for item in node:
            found = find_category(item, target_id)
            if found:
                return found
        return None

    if not isinstance(node, dict):
        return None

    if node.get("id") == target_id:
        return node

    for child in node.get("children", []):
        found = find_category(child, target_id)
        if found:
            return found
    return None


def collect_leaf_ids(node, into):
    children = node.get("children") or []
    if not children:
        into.append(node["id"])
        return
    for child in children:
        collect_leaf_ids(child, into)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch seller category tree and print leaf category IDs."
    )
    parser.add_argument("--category-id", type=int, default=10162)
    parser.add_argument(
        "--token",
        default=os.getenv("KAZANEXPRESS_TOKEN"),
        help="Seller API bearer token. Defaults to KAZANEXPRESS_TOKEN.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        token = require_access_token(args.token)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    status, data, raw_body = fetch_category_tree(token)
    if status == 401:
        print("Seller API rejected the token with HTTP 401. The JWT is expired or invalid.", file=sys.stderr)
        return 1
    if status is None:
        print(f"Network error: {raw_body}", file=sys.stderr)
        return 1
    if status != 200:
        print(f"Seller API returned HTTP {status}: {raw_body[:300]}", file=sys.stderr)
        return 1
    if data is None:
        print(f"Seller API returned non-JSON body: {raw_body[:300]}", file=sys.stderr)
        return 1

    target = find_category(data, args.category_id)
    if not target:
        print(f"Category {args.category_id} not found in the tree.", file=sys.stderr)
        return 1

    leaf_ids = []
    collect_leaf_ids(target, leaf_ids)
    print(f"Category: {target.get('title', '<unknown>')} (ID: {target['id']})")
    print(f"Leaf categories: {len(leaf_ids)}")
    for category_id in leaf_ids:
        print(category_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
