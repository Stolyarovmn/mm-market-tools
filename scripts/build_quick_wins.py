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

from core.logging_config import get_logger
log = get_logger('scripts.build_quick_wins')


# ---------------------------------------------------------------------------
# Time estimates (calibrated against real WONDERS shop cycle observations).
# Mirrors estimateMin() in ui_kits/dashboard/components.jsx — keep in sync.
# ---------------------------------------------------------------------------
ESTIMATE_MIN = {
    "reorder":             lambda count: max(2, round(count * 0.3)),
    "markdown":            lambda count: max(3, round(count * 0.6)),
    "reviews":             lambda count: count * 2,
    "questions":           lambda count: count * 3,
    "run_job":             lambda count: 6,
    "title_seo":           lambda count: max(2, count * 1),
    "price_trap":          lambda count: max(2, round(count * 0.5)),
    "watchlist":           lambda count: max(2, round(count * 0.3)),
    "high_views_low_conv": lambda count: max(5, count * 3),
    "zero_views":          lambda count: max(3, round(count * 0.5)),
    "run_fetch_stats":     lambda count: 4,
}

# Impact weight per kind: how much one unit of this kind matters.
IMPACT_WEIGHT = {
    "reorder":             4.0,
    "markdown":            3.0,
    "reviews":             5.0,
    "questions":           4.0,
    "run_job":             8.0,
    "title_seo":           2.0,
    "price_trap":          2.5,
    "watchlist":           1.5,
    "high_views_low_conv": 3.5,
    "zero_views":          2.0,
    "run_fetch_stats":     5.0,
}

LABELS = {
    "reorder":             "Утвердить reorder_now",
    "markdown":            "Согласовать markdown",
    "reviews":             "Ответить покупателям",
    "questions":           "Ответить на вопросы",
    "run_job":             "Запустить weekly_operational",
    "title_seo":           "Поправить слабые title",
    "price_trap":          "Подвинуть цены за пороги",
    "watchlist":           "Проверить watchlist",
    "high_views_low_conv": "Много просмотров — низкая конверсия",
    "zero_views":          "Нет органического трафика",
    "run_fetch_stats":     "Обновить просмотры и конверсию",
}

ACTIONS = {
    "reorder":             "Открыть список",
    "markdown":            "Открыть список",
    "reviews":             "К отзывам",
    "questions":           "К отзывам",
    "run_job":             "К runner",
    "title_seo":           "Открыть список",
    "price_trap":          "Открыть список",
    "watchlist":           "Открыть список",
    "high_views_low_conv": "Открыть список",
    "zero_views":          "Открыть список",
    "run_fetch_stats":     "К runner",
}

ROUTES = {
    "reorder":             "reorder_now",
    "markdown":            "markdown_candidates",
    "reviews":             "buyer_reviews",
    "questions":           "buyer_reviews",
    "run_job":             "refresh:weekly_operational",
    "title_seo":           "title_seo",
    "price_trap":          "price_trap",
    "watchlist":           "action-center-panel",
    "high_views_low_conv": "product-traffic-panel",
    "zero_views":          "product-traffic-panel",
    "run_fetch_stats":     "refresh:fetch_product_stats",
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


# Thresholds for traffic-based quick wins.
_VIEWS_THRESHOLD = 50        # минимум просмотров, чтобы считать «высоким» трафиком
_CONV_LOW_PCT = 1.5          # конверсия ниже этого % считается низкой


def _count_traffic_issues():
    """
    Read data/local/product_stats.json and return:
      (high_views_low_conv, zero_views, has_data)
    has_data=False means the file doesn't exist yet → suggest running the job.
    """
    stats_file = LOCAL_DATA_DIR / "product_stats.json"
    if not stats_file.exists():
        return 0, 0, False
    try:
        data = load_json(stats_file)
    except Exception:
        return 0, 0, False
    products = data.get("products") or []
    if not products:
        return 0, 0, True

    high_views_low_conv = sum(
        1 for p in products
        if (p.get("viewers") or 0) >= _VIEWS_THRESHOLD
        and p.get("conversion") is not None
        and p["conversion"] < _CONV_LOW_PCT
    )
    zero_views = sum(
        1 for p in products
        if p.get("viewers") is not None and p["viewers"] == 0
        and (p.get("qty_active") or 0) > 0   # есть активный остаток
    )
    return high_views_low_conv, zero_views, True


def build_quick_wins(session_date=None):
    session_date = session_date or today_tag()
    reorder_count, markdown_count = _count_reorder_and_markdown()
    price_trap_count, title_seo_count = _count_price_trap