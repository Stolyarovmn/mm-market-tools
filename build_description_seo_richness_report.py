#!/usr/bin/env python3
import argparse
import statistics
from datetime import datetime, timezone
from pathlib import Path

from core.card_content import content_metrics, get_cached_or_fetch_public_product, load_content_cache, save_content_cache
from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION
from core.http_client import create_session
from core.io_utils import load_json, write_json
from core.paths import DASHBOARD_DIR, PRODUCT_CONTENT_CACHE_PATH, REPORTS_DIR, ensure_dir, today_tag


def _latest_report_path(prefix):
    matches = sorted(REPORTS_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit description richness and thin-content signals using public MM product content and lightweight SEO heuristics."
    )
    parser.add_argument(
        "--input-json",
        default=str(_latest_report_path("marketing_card_audit") or (REPORTS_DIR / f"marketing_card_audit_{today_tag()}.json")),
    )
    parser.add_argument("--cache-json", default=str(PRODUCT_CONTENT_CACHE_PATH))
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--top-rows", type=int, default=60)
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--report-prefix", default=f"description_seo_report_{today_tag()}")
    return parser.parse_args()


def _normalize_token(token):
    return "".join(ch for ch in str(token or "").lower() if ch.isalnum() or ch in {"-", "_"})


def _meaningful_title_terms(title):
    stopwords = {
        "и", "с", "для", "на", "по", "из", "в", "во", "к", "ко", "от", "до",
        "детский", "детская", "детские", "детское", "набор", "игрушка", "игрушки",
        "большой", "большая", "развивающая", "развивающий",
    }
    tokens = [_normalize_token(part) for part in str(title or "").split()]
    return [token for token in tokens if len(token) > 2 and token not in stopwords][:8]


def _score_row(row):
    score = 100
    issues = []
    recommendations = []
    chars = int(row.get("description_chars") or 0)
    words = int(row.get("description_words") or 0)
    coverage = float(row.get("title_term_coverage_pct") or 0.0)
    gap = int(row.get("description_gap_vs_group") or 0)

    if chars < 120 or words < 18:
        score -= 45
        issues.append("thin_content")
        recommendations.append("Сильно расширить описание: что это за товар, для кого, что внутри, как использовать и чем он полезен.")
    elif chars < 240 or words < 35:
        score -= 20
        issues.append("description_short")
        recommendations.append("Углубить описание: добавить пользу, сценарии, состав/комплектацию и сильные отличия.")

    if coverage < 35:
        score -= 25
        issues.append("weak_title_term_coverage")
        recommendations.append("Переписать описание так, чтобы важные слова из title реально раскрывались в тексте.")
    elif coverage < 55:
        score -= 10
        issues.append("mid_title_term_coverage")
        recommendations.append("Усилить связь title и description: добавить тип товара, ключевой entity и сценарий использования.")

    if gap >= 180:
        score -= 12
        issues.append("description_gap_vs_group")
        recommendations.append("Описание заметно короче медианы своей группы. Это уже контентный минус относительно окружения.")

    score = max(score, 0)
    status = "strong"
    if score < 75:
        status = "needs_work"
    if score < 50:
        status = "priority_fix"
    return score, status, issues, recommendations


def build_rows(source_rows, cache, *, cache_only=False):
    rows = []
    session = create_session()
    try:
        for source in source_rows:
            product_id = source.get("product_id")
            if not product_id:
                continue
            public_product, cached = get_cached_or_fetch_public_product(
                session,
                product_id,
                cache,
                cache_only=cache_only,
                device_id="mm-market-tools-description-audit",
            )
            if not public_product:
                continue
            metrics = content_metrics(public_product)
            title_terms = _meaningful_title_terms(source.get("title") or metrics.get("title"))
            description_text = (metrics.get("description_text") or "").lower()
            hits = sum(1 for term in title_terms if term and term in description_text)
            coverage_pct = round((hits / len(title_terms)) * 100.0, 1) if title_terms else 0.0
            rows.append(
                {
                    "key": source.get("key"),
                    "product_id": product_id,
                    "barcode": source.get("barcode"),
                    "title": source.get("title") or metrics.get("title"),
                    "group": source.get("group") or "Прочее",
                    "price_band": source.get("price_band"),
                    "sale_price": source.get("sale_price"),
                    "units_sold": source.get("units_sold", 0),
                    "stock_value_sale": source.get("stock_value_sale", 0.0),
                    "total_stock": source.get("total_stock", 0),
                    "current_winner": bool(source.get("current_winner")),
                    "stale_stock": bool(source.get("stale_stock")),
                    "description_chars": metrics["description_chars"],
                    "description_words": metrics["description_words"],
                    "title_term_coverage_pct": coverage_pct,
                    "matched_title_terms": hits,
                    "title_terms_count": len(title_terms),
                    "content_source": "cache" if cached else "live",
                }
            )
    finally:
        session.close()

    group_medians = {}
    for group in sorted({row["group"] for row in rows}):
        group_rows = [row for row in rows if row["group"] == group]
        group_medians[group] = statistics.median([row["description_chars"] for row in group_rows]) if group_rows else 0

    for row in rows:
        row["group_median_description_chars"] = group_medians.get(row["group"], 0)
        row["description_gap_vs_group"] = max(0, int(round(row["group_median_description_chars"] - row["description_chars"])))
        score, status, issues, recommendations = _score_row(row)
        row["description_score"] = score
        row["description_status"] = status
        row["issues"] = issues
        row["recommendations"] = recommendations

    rows.sort(
        key=lambda row: (
            {"priority_fix": 0, "needs_work": 1, "strong": 2}.get(row["description_status"], 3),
            row["description_score"],
            -(row.get("units_sold") or 0),
            -(row.get("stock_value_sale") or 0),
        )
    )
    return rows


def build_markdown(rows, args):
    lines = [
        "# Description SEO Richness Report",
        "",
        f"- source: `{args.input_json}`",
        f"- cache: `{args.cache_json}`",
        f"- audited rows: `{len(rows)}`",
        "",
        "## Priority description fixes",
        "",
    ]
    priority = [row for row in rows if row["description_status"] == "priority_fix"]
    if not priority:
        lines.append("- Критичных description-gap карточек не найдено.")
        return "\n".join(lines)
    for row in priority[:25]:
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- description score: `{row['description_score']}`",
                f"- chars / words: `{row['description_chars']} / {row['description_words']}`",
                f"- title-term coverage: `{row['title_term_coverage_pct']}%`",
                f"- group median chars: `{row['group_median_description_chars']}`",
                f"- issues: `{', '.join(row['issues']) or 'н/д'}`",
                f"- recommendations: `{'; '.join(row['recommendations']) or 'н/д'}`",
                "",
            ]
        )
    return "\n".join(lines)


def build_dashboard_payload(rows, args):
    summary = {
        "audited_cards_count": len(rows),
        "priority_fix_count": sum(1 for row in rows if row["description_status"] == "priority_fix"),
        "needs_work_count": sum(1 for row in rows if row["description_status"] == "needs_work"),
        "strong_count": sum(1 for row in rows if row["description_status"] == "strong"),
        "thin_content_count": sum(1 for row in rows if "thin_content" in row["issues"]),
        "gap_vs_group_count": sum(1 for row in rows if "description_gap_vs_group" in row["issues"]),
    }
    actions = {
        "fix_now": [row for row in rows if row["description_status"] == "priority_fix"][:12],
        "thin_content": [row for row in rows if "thin_content" in row["issues"]][:12],
        "strong_examples": [row for row in rows if row["description_status"] == "strong"][:12],
    }
    charts = {
        "description_status_counts": [
            {"key": "Priority fix", "count": summary["priority_fix_count"]},
            {"key": "Needs work", "count": summary["needs_work_count"]},
            {"key": "Strong", "count": summary["strong_count"]},
        ],
        "description_length_counts": [
            {"key": "0-119", "count": sum(1 for row in rows if row["description_chars"] < 120)},
            {"key": "120-239", "count": sum(1 for row in rows if 120 <= row["description_chars"] < 240)},
            {"key": "240-499", "count": sum(1 for row in rows if 240 <= row["description_chars"] < 500)},
            {"key": "500+", "count": sum(1 for row in rows if row["description_chars"] >= 500)},
        ],
        "title_term_coverage_counts": [
            {"key": "0-34%", "count": sum(1 for row in rows if row["title_term_coverage_pct"] < 35)},
            {"key": "35-54%", "count": sum(1 for row in rows if 35 <= row["title_term_coverage_pct"] < 55)},
            {"key": "55-74%", "count": sum(1 for row in rows if 55 <= row["title_term_coverage_pct"] < 75)},
            {"key": "75%+", "count": sum(1 for row in rows if row["title_term_coverage_pct"] >= 75)},
        ],
    }
    insights = []
    if summary["thin_content_count"] > 0:
        insights.append({
            "title": "Есть карточки с реально тонким описанием",
            "text": f"Найдено {summary['thin_content_count']} карточек, где описание уже слишком короткое, чтобы нормально раскрывать товар и его пользу.",
            "tone": "warn",
        })
    if summary["gap_vs_group_count"] > 0:
        insights.append({
            "title": "Часть карточек отстаёт от своей группы по плотности текста",
            "text": f"В {summary['gap_vs_group_count']} карточках описание слабее медианы своей группы по объёму. Это полезный ориентир для prioritization контентной работы.",
            "tone": "warn",
        })
    if summary["strong_count"] > 0:
        insights.append({
            "title": "Уже есть карточки, на которые можно равняться",
            "text": f"Внутри выборки есть {summary['strong_count']} карточек с сильным description-layer. Их стоит использовать как внутренние эталоны, а не придумывать контент с нуля.",
            "tone": "good",
        })
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "window": {},
            "documents": {},
            "content_audit": {
                "mode": "description seo richness heuristic",
                "input_json": args.input_json,
                "cache_json": args.cache_json,
                "cache_only": bool(args.cache_only),
            },
        },
        "kpis": {
            "total_skus": summary["audited_cards_count"],
            "sold_skus": sum(1 for row in rows if (row.get("units_sold") or 0) > 0),
            "revenue_total": 0.0,
            "gross_profit_total": 0.0,
            "stockout_risk_count": 0,
            "stale_stock_count": sum(1 for row in rows if row.get("stale_stock")),
            "priority_cards_count": summary["priority_fix_count"],
            "description_needs_work_count": summary["needs_work_count"],
            "thin_content_count": summary["thin_content_count"],
            "description_gap_count": summary["gap_vs_group_count"],
        },
        "actions": actions,
        "tables": {
            "priority_descriptions": rows[:25],
            "thin_content": actions["thin_content"],
            "strong_examples": actions["strong_examples"],
        },
        "charts": charts,
        "insights": insights,
    }


def main():
    args = parse_args()
    payload = load_json(Path(args.input_json))
    source_rows = (payload.get("rows") or [])[: args.top_rows]
    cache = load_content_cache(args.cache_json)
    rows = build_rows(source_rows, cache, cache_only=args.cache_only)
    save_content_cache(args.cache_json, cache)

    report_dir = ensure_dir(Path(args.report_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))
    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    dashboard_path = dashboard_dir / f"{args.report_prefix}.json"

    result = {
        "generated_from": args.input_json,
        "cache_json": args.cache_json,
        "cache_only": bool(args.cache_only),
        "summary": {
            "audited_cards": len(rows),
            "priority_fix_count": sum(1 for row in rows if row["description_status"] == "priority_fix"),
            "needs_work_count": sum(1 for row in rows if row["description_status"] == "needs_work"),
            "strong_count": sum(1 for row in rows if row["description_status"] == "strong"),
        },
        "rows": rows,
    }
    write_json(json_path, result)
    md_path.write_text(build_markdown(rows, args), encoding="utf-8")
    write_json(dashboard_path, build_dashboard_payload(rows, args))
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {dashboard_path}")


if __name__ == "__main__":
    main()
