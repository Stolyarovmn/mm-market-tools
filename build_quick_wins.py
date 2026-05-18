#!/usr/bin/env python3
"""Build Quick Wins JSON for the dashboard top-strip.

Reads from the latest operational, marketing-audit, reviews, action-store
and job-runs data; emits data/dashboard/quick_wins_<YYYY-MM-DD>.json.
"""
import argparse
import json
from pathlib import Path

from core.action_store import load_action_store
from core.io_utils import load_json, write_json
from core.paths import DASHBOARD_DIR, JOB_RUNS_DIR, LOCAL_DATA_DIR, ensure_dir, today_tag


# ---------------------------------------------------------------------------
# Time estimates (calibrated against real WONDERS shop cycle observations).
# Mirrors estimateMin() in ui_kits/dashboard/components.jsx — keep in sync.
# ---------------------------------------------------------------------------
ESTIMATE_MIN = {
    "reorder":    lambda count: max(2, round(count * 0.3)),
    "markdown":   lambda count: max(3, round(count * 0.6)),
    "reviews":    lambda count: count * 2,
    "questions":  lambda count: count * 3,
    "run_job":    lambda count: 6,
    "title_seo":  lambda count: max(2, count * 1),
    "price_trap": lambda count: max(2, round(count * 0.5)),
    "watchlist":  lambda count: max(2, round(count * 0.3)),
}

# Impact weight per kind: how much one unit of this kind matters.
IMPACT_WEIGHT = {
    "reorder":    4.0,
    "markdown":   3.0,
    "reviews":    5.0,
    "questions":  4.0,
    "run_job":    8.0,
    "title_seo":  2.0,
    "price_trap": 2.5,
    "watchlist":  1.5,
}

LABELS = {
    "reorder":    "Утвердить reorder_now",
    "markdown":   "Согласовать markdown",
    "reviews":    "Ответить покупателям",
    "questions":  "Ответить на вопросы",
    "run_job":    "Запустить weekly_operational",
    "title_seo":  "Поправить слабые title",
    "price_trap": "Подвинуть цены за пороги",
    "watchlist":  "Проверить watchlist",
}

ACTIONS = {
    "reorder":    "Открыть список",
    "markdown":   "Открыть список",
    "reviews":    "К отзывам",
    "questions":  "К отзывам",
    "run_job":    "К runner",
    "title_seo":  "Открыть список",
    "price_trap": "Открыть список",
    "watchlist":  "Открыть список",
}

ROUTES = {
    "reorder":    "reorder_now",
    "markdown":   "markdown_candidates",
    "reviews":    "buyer_reviews",
    "questions":  "buyer_reviews",
    "run_job":    "refresh:weekly",
    "title_seo":  "title_seo",
    "price_trap": "price_trap",
    "watchlist":  "action-center-panel",
}


def _estimate_min(kind, count):
    fn = ESTIMATE_MIN.get(kind)
    return fn(count) if fn else 5


def _score(kind, count):
    mins = _estimate_min(kind, count)
    if mins <= 0:
        return 0.0
    return (IMPACT_WEIGHT.get(kind, 1.0) * count) / mins


def _latest_dashboard_file(prefix):
    matches = sorted(
        DASHBOARD_DIR.glob(f"{prefix}*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def _count_reorder_and_markdown():
    path = _latest_dashboard_file("weekly_operational_report_")
    if not path:
        return 0, 0
    try:
        data = load_json(path)
    except Exception:
        return 0, 0
    kpis = data.get("kpis") or {}
    tables = data.get("tables") or {}
    # Count from tables when available (more accurate than kpis).
    all_rows = []
    for key in ("soft_signal_products", "current_winners", "stale_products"):
        all_rows.extend(tables.get(key) or [])
    if all_rows:
        reorder = sum(1 for r in all_rows if r.get("reorder_candidate"))
        markdown = sum(1 for r in all_rows if r.get("stale_stock"))
    else:
        reorder = int(kpis.get("stockout_risk_count") or 0)
        markdown = int(kpis.get("stale_stock_count") or 0)
    return reorder, markdown


def _count_price_trap_and_title_seo():
    path = _latest_dashboard_file("marketing_card_audit_")
    if not path:
        return 0, 0
    try:
        data = load_json(path)
    except Exception:
        return 0, 0
    kpis = data.get("kpis") or {}
    price_trap = int(kpis.get("price_trap_cards_count") or 0)
    title_seo = int(kpis.get("seo_needs_work_count") or 0)
    return price_trap, title_seo


def _count_reviews_and_questions():
    reviews_file = LOCAL_DATA_DIR.parent / "reviews" / "reviews.json"
    if not reviews_file.exists():
        return 0, 0
    try:
        data = load_json(reviews_file)
    except Exception:
        return 0, 0
    items = data.get("items") or []
    reviews = sum(1 for r in items if r.get("kind") == "review" and r.get("status") not in ("sent", "unsupported"))
    questions = sum(1 for r in items if r.get("kind") == "question" and r.get("status") not in ("sent", "unsupported"))
    return reviews, questions


def _watchlist_size():
    try:
        store = load_action_store()
    except Exception:
        return 0
    return len(store.get("watchlists") or [])


def _weekly_ran_today():
    """Return True if a weekly_operational job completed successfully today."""
    today = today_tag()
    job_runs_dir = Path(JOB_RUNS_DIR) if not isinstance(JOB_RUNS_DIR, Path) else JOB_RUNS_DIR
    if not job_runs_dir.exists():
        return False
    for status_file in job_runs_dir.glob("*/status.json"):
        try:
            status = json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status.get("job_key") == "weekly_operational" and status.get("state") == "done":
            started = (status.get("started_at") or "")[:10]
            if started == today:
                return True
    return False


def build_quick_wins(session_date=None):
    session_date = session_date or today_tag()
    reorder_count, markdown_count = _count_reorder_and_markdown()
    price_trap_count, title_seo_count = _count_price_trap_and_title_seo()
    reviews_count, questions_count = _count_reviews_and_questions()
    watchlist_count = _watchlist_size()
    weekly_ran = _weekly_ran_today()

    candidates = []
    if reorder_count > 0:
        candidates.append({"id": "reorder", "kind": "reorder", "count": reorder_count})
    if markdown_count > 0:
        candidates.append({"id": "markdown", "kind": "markdown", "count": markdown_count})
    if reviews_count > 0:
        candidates.append({"id": "reviews", "kind": "reviews", "count": reviews_count})
    if questions_count > 0:
        candidates.append({"id": "questions", "kind": "questions", "count": questions_count})
    if price_trap_count > 0:
        candidates.append({"id": "price_trap", "kind": "price_trap", "count": price_trap_count})
    if title_seo_count > 0:
        candidates.append({"id": "title_seo", "kind": "title_seo", "count": title_seo_count})
    if watchlist_count > 0:
        candidates.append({"id": "watchlist", "kind": "watchlist", "count": watchlist_count})
    if not weekly_ran:
        candidates.append({"id": "weekly", "kind": "run_job", "count": 1})

    # Sort by impact ÷ estimated minutes, descending.
    candidates.sort(key=lambda c: _score(c["kind"], c["count"]), reverse=True)

    items = []
    for priority, c in enumerate(candidates, start=1):
        kind = c["kind"]
        count = c["count"]
        items.append({
            "id": c["id"],
            "kind": kind,
            "count": count,
            "label": LABELS.get(kind, kind),
            "action": ACTIONS.get(kind, "Открыть"),
            "route": ROUTES.get(kind, kind),
            "priority": priority,
        })

    return {
        "schema_version": "v1",
        "session_date": session_date,
        "items": items,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Build Quick Wins JSON for the dashboard.")
    parser.add_argument("--date", default=None, help="Session date YYYY-MM-DD (default: today)")
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    return parser.parse_args()


def main():
    args = parse_args()
    ensure_dir(DASHBOARD_DIR)
    session_date = args.date or today_tag()
    payload = build_quick_wins(session_date=session_date)
    out = DASHBOARD_DIR / f"quick_wins_{session_date}.json"
    write_json(out, payload)
    count = len(payload["items"])
    print(f"Saved: {out}  ({count} items)")


if __name__ == "__main__":
    main()
