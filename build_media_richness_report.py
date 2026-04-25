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
        description="Audit media richness of your product cards using public MM product content and lightweight competitor-relative heuristics."
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
    parser.add_argument("--report-prefix", default=f"media_richness_report_{today_tag()}")
    return parser.parse_args()


def _bucket_photo_count(photo_count):
    if photo_count <= 2:
        return "0-2"
    if photo_count <= 4:
        return "3-4"
    if photo_count <= 7:
        return "5-7"
    return "8+"


def _score_row(row):
    score = 100
    issues = []
    recommendations = []
    photo_count = int(row.get("photo_count") or 0)
    spec_count = int(row.get("spec_count") or 0)
    photo_gap = int(row.get("photo_gap_vs_group") or 0)
    spec_gap = int(row.get("spec_gap_vs_group") or 0)
    video_count = int(row.get("video_count") or 0)

    if photo_count < 3:
        score -= 40
        issues.append("too_few_photos")
        recommendations.append("Добрать хотя бы 5-7 фото: обложка, 2-3 ракурса, детали, масштаб, упаковка.")
    elif photo_count < 5:
        score -= 20
        issues.append("photo_stack_thin")
        recommendations.append("Расширить фото-стек до 5+ кадров, чтобы не проигрывать конкурентам в витрине.")

    if spec_count < 4:
        score -= 25
        issues.append("specs_thin")
        recommendations.append("Заполнить больше атрибутов и характеристик, чтобы карточка не выглядела пустой.")
    elif spec_count < 7:
        score -= 10
        issues.append("specs_mid")
        recommendations.append("Дожать характеристики до плотного уровня, особенно важные фильтруемые атрибуты.")

    if photo_gap >= 2:
        score -= 15
        issues.append("photo_gap_vs_group")
        recommendations.append("По фото карточка уступает медиане своей группы. Это хороший кандидат на визуальное усиление.")
    if spec_gap >= 3:
        score -= 10
        issues.append("spec_gap_vs_group")
        recommendations.append("По характеристикам карточка уступает группе. Стоит добить структуру контента.")
    if video_count <= 0 and photo_count >= 5:
        recommendations.append("Видео необязательно, но для сложных/демонстрационных товаров может дать дополнительный CTR.")

    score = max(score, 0)
    status = "strong"
    if score < 75:
        status = "needs_work"
    if score < 50:
        status = "priority_fix"
    return score, status, issues, recommendations


def build_rows(source_rows, cache, cache_only=False):
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
                device_id="mm-market-tools-media-audit",
            )
            if not public_product:
                continue
            metrics = content_metrics(public_product)
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
                    "photo_count": metrics["photo_count"],
                    "attribute_count": metrics["attribute_count"],
                    "characteristic_count": metrics["characteristic_count"],
                    "spec_count": metrics["spec_count"],
                    "video_count": metrics["video_count"],
                    "content_source": "cache" if cached else "live",
                }
            )
    finally:
        session.close()

    group_photo_medians = {}
    group_spec_medians = {}
    for group in sorted({row["group"] for row in rows}):
        group_rows = [row for row in rows if row["group"] == group]
        group_photo_medians[group] = statistics.median([row["photo_count"] for row in group_rows]) if group_rows else 0
        group_spec_medians[group] = statistics.median([row["spec_count"] for row in group_rows]) if group_rows else 0

    for row in rows:
        row["group_median_photo_count"] = group_photo_medians.get(row["group"], 0)
        row["group_median_spec_count"] = group_spec_medians.get(row["group"], 0)
        row["photo_gap_vs_group"] = max(0, int(round(row["group_median_photo_count"] - row["photo_count"])))
        row["spec_gap_vs_group"] = max(0, int(round(row["group_median_spec_count"] - row["spec_count"])))
        row["photo_bucket"] = _bucket_photo_count(row["photo_count"])
        score, status, issues, recommendations = _score_row(row)
        row["media_score"] = score
        row["media_status"] = status
        row["issues"] = issues
        row["recommendations"] = recommendations
    rows.sort(
        key=lambda row: (
            {"priority_fix": 0, "needs_work": 1, "strong": 2}.get(row["media_status"], 3),
            row["media_score"],
            -(row.get("units_sold") or 0),
            -(row.get("stock_value_sale") or 0),
        )
    )
    return rows


def build_markdown(rows, args):
    lines = [
        "# Media Richness Report",
        "",
        f"- source: `{args.input_json}`",
        f"- cache: `{args.cache_json}`",
        f"- audited rows: `{len(rows)}`",
        "",
        "## Priority media fixes",
        "",
    ]
    priority = [row for row in rows if row["media_status"] == "priority_fix"]
    if not priority:
        lines.append("- Критичных media-gap карточек не найдено.")
        return "\n".join(lines)
    for row in priority[:25]:
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- media score: `{row['media_score']}`",
                f"- фото: `{row['photo_count']}` (медиана группы `{row['group_median_photo_count']}`)",
                f"- характеристики+атрибуты: `{row['spec_count']}` (медиана группы `{row['group_median_spec_count']}`)",
                f"- видео: `{row['video_count']}`",
                f"- issues: `{', '.join(row['issues']) or 'н/д'}`",
                f"- recommendations: `{'; '.join(row['recommendations']) or 'н/д'}`",
                "",
            ]
        )
    return "\n".join(lines)


def build_dashboard_payload(rows, args):
    summary = {
        "audited_cards_count": len(rows),
        "priority_fix_count": sum(1 for row in rows if row["media_status"] == "priority_fix"),
        "needs_work_count": sum(1 for row in rows if row["media_status"] == "needs_work"),
        "strong_count": sum(1 for row in rows if row["media_status"] == "strong"),
        "photo_gap_count": sum(1 for row in rows if "photo_gap_vs_group" in row["issues"]),
        "spec_gap_count": sum(1 for row in rows if "spec_gap_vs_group" in row["issues"]),
        "with_video_count": sum(1 for row in rows if (row.get("video_count") or 0) > 0),
    }
    actions = {
        "fix_now": [row for row in rows if row["media_status"] == "priority_fix"][:12],
        "visual_gaps": [row for row in rows if row["photo_gap_vs_group"] >= 2 or row["spec_gap_vs_group"] >= 3][:12],
        "strong_examples": [row for row in rows if row["media_status"] == "strong"][:12],
    }
    charts = {
        "media_status_counts": [
            {"key": "Priority fix", "count": summary["priority_fix_count"]},
            {"key": "Needs work", "count": summary["needs_work_count"]},
            {"key": "Strong", "count": summary["strong_count"]},
        ],
        "photo_bucket_counts": [
            {"key": bucket, "count": sum(1 for row in rows if row["photo_bucket"] == bucket)}
            for bucket in ["0-2", "3-4", "5-7", "8+"]
        ],
        "spec_bucket_counts": [
            {"key": "0-3", "count": sum(1 for row in rows if row["spec_count"] <= 3)},
            {"key": "4-6", "count": sum(1 for row in rows if 4 <= row["spec_count"] <= 6)},
            {"key": "7-10", "count": sum(1 for row in rows if 7 <= row["spec_count"] <= 10)},
            {"key": "11+", "count": sum(1 for row in rows if row["spec_count"] >= 11)},
        ],
    }
    insights = []
    if summary["priority_fix_count"] > 0:
        insights.append({
            "title": "Есть карточки с явным визуальным дефицитом",
            "text": f"Найдено {summary['priority_fix_count']} карточек, где фото-стек и/или набор характеристик уже заметно слабее рабочих ориентиров. Это быстрый фронт работ без смены ассортимента.",
            "tone": "warn",
        })
    if summary["photo_gap_count"] > 0:
        insights.append({
            "title": "Часть карточек проигрывает даже медиане своей группы",
            "text": f"В {summary['photo_gap_count']} карточках фото-стек отстаёт от медианы группы. Это полезнее, чем смотреть только на абсолютное число фото.",
            "tone": "warn",
        })
    if summary["with_video_count"] > 0:
        insights.append({
            "title": "Видео есть не везде и не должно быть самоцелью",
            "text": f"Видео найдено у {summary['with_video_count']} карточек. Для большинства toy-SKU важнее сперва добить фото и характеристики, а уже потом думать о видео.",
            "tone": "good",
        })
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "window": {},
            "documents": {},
            "content_audit": {
                "mode": "media richness heuristic",
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
            "media_needs_work_count": summary["needs_work_count"],
            "photo_gap_count": summary["photo_gap_count"],
            "spec_gap_count": summary["spec_gap_count"],
            "with_video_count": summary["with_video_count"],
        },
        "actions": actions,
        "tables": {
            "priority_media": rows[:25],
            "visual_gaps": actions["visual_gaps"],
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
            "priority_fix_count": sum(1 for row in rows if row["media_status"] == "priority_fix"),
            "needs_work_count": sum(1 for row in rows if row["media_status"] == "needs_work"),
            "strong_count": sum(1 for row in rows if row["media_status"] == "strong"),
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
