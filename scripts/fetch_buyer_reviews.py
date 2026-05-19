#!/usr/bin/env python3
"""
Fetch buyer reviews and questions from Seller API and save to local JSON.

Usage:
  python3 fetch_buyer_reviews.py --token <access_token> [--status WITHOUT_ANSWER]
  python3 fetch_buyer_reviews.py --token <access_token> --offline   # use saved file

Output:
  data/reviews/reviews.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.http_client import create_session
from core.io_utils import write_json
from core.paths import PROJECT_ROOT
from core.reviews_api import fetch_all_questions, fetch_all_reviews

REVIEWS_DIR = PROJECT_ROOT / "data" / "reviews"
REVIEWS_FILE = REVIEWS_DIR / "reviews.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_saved():
    if not REVIEWS_FILE.exists():
        return None
    return json.loads(REVIEWS_FILE.read_text(encoding="utf-8"))


def save_reviews(items, status_filter):
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": now_iso(),
        "status_filter": status_filter,
        "count": len(items),
        "items": items,
    }
    write_json(REVIEWS_FILE, payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description="Fetch buyer reviews and questions from Seller API.")
    parser.add_argument("--token", required=False, help="Seller API access token")
    parser.add_argument("--status", default="WITHOUT_ANSWER",
                        choices=["WITHOUT_ANSWER", "WITH_ANSWER", "ALL"],
                        help="Review status filter (default: WITHOUT_ANSWER)")
    parser.add_argument("--offline", action="store_true",
                        help="Skip API call, load from saved file")
    parser.add_argument("--max-pages", type=int, default=10,
                        help="Max pages to fetch per endpoint (default: 10)")
    args = parser.parse_args()

    if args.offline:
        saved = load_saved()
        if not saved:
            print("Нет сохранённого файла. Запусти без --offline чтобы скачать данные.", file=sys.stderr)
            sys.exit(1)
        print(f"Loaded from saved file: {saved['count']} items, fetched {saved['fetched_at']}")
        return

    if not args.token:
        print("Требуется --token. Используй --offline чтобы загрузить из файла.", file=sys.stderr)
        sys.exit(1)

    session = create_session()
    items = []

    print("Fetching reviews...")
    status_arg = None if args.status == "ALL" else args.status
    try:
        reviews = fetch_all_reviews(session, args.token, status=status_arg, max_pages=args.max_pages)
        print(f"  Reviews: {len(reviews)}")
        items.extend(reviews)
    except Exception as e:
        print(f"  Reviews fetch failed: {e}", file=sys.stderr)

    print("Fetching questions...")
    try:
        questions = fetch_all_questions(session, args.token,
                                        answered=(args.status == "WITH_ANSWER"),
                                        max_pages=args.max_pages)
        print(f"  Questions: {len(questions)}")
        items.extend(questions)
    except Exception as e:
        print(f"  Questions fetch failed: {e}", file=sys.stderr)

    payload = save_reviews(items, args.status)
    print(f"Saved {payload['count']} items → {REVIEWS_FILE}")
    print(f"Saved: {REVIEWS_FILE}")


if __name__ == "__main__":
    main()
