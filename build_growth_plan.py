#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

from core.paths import REPORTS_DIR


DEFAULT_DATE = dt.date.today().isoformat()
DEFAULT_REPORT_DIR = str(REPORTS_DIR)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_title(value):
    return " ".join((value or "").lower().split())


def price_bucket(price):
    if price < 200:
        return "<200"
    if price < 300:
        return "200-299"
    if price < 500:
        return "300-499"
    if price < 800:
        return "500-799"
    return "800+"


def sold_per_sku(group):
    if not group["sku_count"]:
        return 0.0
    return round(group["sold_sum"] / group["sku_count"], 2)


def load_operational_context(report_dir):
    candidates = [
        report_dir / "../data/dashboard/weekly_operational_report_2026-04-08.json",
        report_dir / "../data/dashboard/official_period_analysis_family_2026-04-08.json",
        report_dir / "../data/dashboard/official_period_analysis_stricter_v2_2026-04-08.json",
    ]
    for path in candidates:
        resolved = path.resolve()
        if resolved.exists():
            return load_json(resolved)
    return {}


def build_operational_title_sets(payload):
    tables = payload.get("tables") or {}
    action_rows = payload.get("actions") or {}
    return {
        "current_winners": {normalize_title(row.get("title")) for row in tables.get("current_winners") or [] if row.get("title")},
        "soft_signals": {normalize_title(row.get("title")) for row in tables.get("soft_signal_products") or [] if row.get("title")},
        "stockout_risk": {normalize_title(row.get("title")) for row in tables.get("stockout_risk") or [] if row.get("title")},
        "stale_stock": {normalize_title(row.get("title")) for row in tables.get("stale_stock") or [] if row.get("title")},
        "markdown_candidates": {normalize_title(row.get("title")) for row in action_rows.get("markdown_candidates") or [] if row.get("title")},
    }


def apply_window_signals(groups, title_sets):
    enriched = []
    for group in groups:
        row = dict(group)
        current_winner_count = 0
        soft_signal_count = 0
        stockout_risk_count = 0
        stale_count = 0
        markdown_count = 0
        for product in row["top_products"]:
            key = normalize_title(product.get("title"))
            if key in title_sets["current_winners"]:
                current_winner_count += 1
            if key in title_sets["soft_signals"]:
                soft_signal_count += 1
            if key in title_sets["stockout_risk"]:
                stockout_risk_count += 1
            if key in title_sets["stale_stock"]:
                stale_count += 1
            if key in title_sets["markdown_candidates"]:
                markdown_count += 1
        row["window_current_winner_count"] = current_winner_count
        row["window_soft_signal_count"] = soft_signal_count
        row["window_stockout_risk_count"] = stockout_risk_count
        row["window_stale_count"] = stale_count
        row["window_markdown_count"] = markdown_count
        if current_winner_count > 0 or stockout_risk_count > 0:
            row["window_status"] = "живой текущий сигнал"
        elif soft_signal_count > 0:
            row["window_status"] = "ранний текущий сигнал"
        elif stale_count > 0 or markdown_count > 0:
            row["window_status"] = "текущий риск залеживания"
        else:
            row["window_status"] = "исторический сигнал без текущего подтверждения"
        enriched.append(row)
    return enriched


def top_active_gaps(groups):
    gaps = []
    for group in groups:
        for product in group["top_products"]:
            if product["sold"] >= 100 and product.get("active", 0) <= 0:
                gaps.append(
                    {
                        "group": group["group"],
                        "title": product["title"],
                        "sold": product["sold"],
                        "price": product["price"],
                        "rating": product["rating"],
                        "window_status": group.get("window_status"),
                    }
                )
    gaps.sort(key=lambda row: row["sold"], reverse=True)
    return gaps


def group_price_distribution(groups):
    result = {}
    for group in groups:
        buckets = Counter()
        for product in group["top_products"]:
            buckets[price_bucket(product["price"])] += 1
        result[group["group"]] = dict(buckets)
    return result


def extract_line_ideas(groups):
    result = []
    for group in groups:
        token_counter = Counter()
        product_counter = defaultdict(list)
        for product in group["top_products"]:
            for token in product.get("tokens", []):
                token_counter[token] += product["sold"]
                product_counter[token].append(product)
        ideas = []
        for token, sold in token_counter.most_common(6):
            examples = sorted(product_counter[token], key=lambda row: row["sold"], reverse=True)[:2]
            ideas.append(
                {
                    "token": token,
                    "sold_signal": sold,
                    "examples": [row["title"] for row in examples],
                }
            )
        result.append({"group": group["group"], "ideas": ideas[:4]})
    return result


def best_competitor_opportunities(real_report):
    findings = []
    for group in real_report:
        if not group["competitors"]:
            continue
        top_comp = sorted(
            group["competitors"],
            key=lambda row: (row["orders_sum"], row["matched_items"]),
            reverse=True,
        )[0]
        best_example = sorted(top_comp["examples"], key=lambda row: row["orders"], reverse=True)[0]
        my_best = sorted(group["my_top_products"], key=lambda row: row["sold"], reverse=True)[0]
        findings.append(
            {
                "group": group["group"],
                "competitor": top_comp["seller_title"],
                "competitor_orders_sum": top_comp["orders_sum"],
                "competitor_matched_items": top_comp["matched_items"],
                "best_example_title": best_example["title"],
                "best_example_orders": best_example["orders"],
                "best_example_price": best_example["price"],
                "my_best_title": my_best["title"],
                "my_best_orders": my_best["sold"],
                "my_best_price": my_best["price"],
            }
        )
    findings.sort(key=lambda row: row["best_example_orders"], reverse=True)
    return findings


def choose_expansion_groups(groups):
    ranked = []
    for group in groups:
        signal_bonus = group.get("window_current_winner_count", 0) * 40 + group.get("window_soft_signal_count", 0) * 20 + group.get("window_stockout_risk_count", 0) * 25
        stale_penalty = group.get("window_stale_count", 0) * 25 + group.get("window_markdown_count", 0) * 30
        growth_score = round((sold_per_sku(group) * 5) + signal_bonus - stale_penalty, 2)
        ranked.append(
            {
                "group": group["group"],
                "sku_count": group["sku_count"],
                "sold_sum": group["sold_sum"],
                "avg_price": group["avg_price"],
                "sold_per_sku": sold_per_sku(group),
                "growth_score": growth_score,
                "window_status": group.get("window_status"),
                "window_current_winner_count": group.get("window_current_winner_count", 0),
                "window_soft_signal_count": group.get("window_soft_signal_count", 0),
                "window_stockout_risk_count": group.get("window_stockout_risk_count", 0),
                "window_stale_count": group.get("window_stale_count", 0),
                "top_products": group["top_products"][:3],
            }
        )
    ranked.sort(key=lambda row: (row["growth_score"], row["sold_per_sku"], row["sold_sum"]), reverse=True)
    return ranked


def write_markdown(path, summary, gaps, line_ideas, competitor_findings, top10_report, real_report, my_summary, date_tag):
    lines = [
        f"# План роста {date_tag}",
        "",
        "План построен на основе группировки ассортимента по товарным идеям и сравнений с top-10 продавцов и реальными ассортиментными конкурентами.",
        "",
        "## Что расширять",
        "",
    ]
    for row in summary[:6]:
        lines.append(
            f"- {row['group']}: `{row['sku_count']}` SKU, `{row['sold_sum']}` продаж, `{row['sold_per_sku']}` продаж на SKU, growth score `{row['growth_score']}`, статус окна `{row['window_status']}`, средняя цена `{row['avg_price']} ₽`"
        )
    lines.extend(["", "## Какие ценовые ниши недозакрыты", ""])
    lines.append(
        f"- Общий сигнал по магазину: топ-20 хитов у вас в основном до `500 ₽` ({my_summary['top20_lowprice_le_500']} из 20), средняя цена хита `{my_summary['top20_avg_price']} ₽`."
    )
    lines.append("- Значит самый надёжный диапазон для расширения: `199-499 ₽`.")
    lines.append("- Второй диапазон: `500-799 ₽` только для уже подтверждённых идей, где есть продажи и отзывы.")
    lines.append("- Диапазон `800+ ₽` стоит расширять точечно, а не широко.")
    lines.extend(["", "## Какие линейки углублять", ""])
    for group in line_ideas[:6]:
        ideas = ", ".join([idea["token"] for idea in group["ideas"][:4] if idea["token"]])
        if ideas:
            lines.append(f"- {group['group']}: {ideas}")
    lines.extend(["", "## Где есть потери из-за наличия", ""])
    for row in gaps[:10]:
        lines.append(
            f"- {row['group']}: {row['title']} | sold `{row['sold']}` | price `{row['price']} ₽` | rating `{row['rating']}` | window `{row.get('window_status', 'н/д')}`"
        )
    lines.extend(["", "## Где идея у конкурентов уже продаётся лучше", ""])
    for row in competitor_findings[:8]:
        lines.append(
            f"- {row['group']}: у `{row['competitor']}` пример `{row['best_example_title']}` продаётся на `{row['best_example_orders']}`, у вас лидер идеи `{row['my_best_title']}` на `{row['my_best_orders']}`"
        )
    lines.extend(["", "## Вывод по top-10", ""])
    top10_dense = [row for row in top10_report if row["competitors"]]
    lines.append(
        f"- Из `{len(top10_report)}` групп заметные совпадения с top-10 нашлись только в `{len(top10_dense)}` группах. Top-10 остаются фоном рынка, а не вашими главными прямыми конкурентами."
    )
    lines.extend(["", "## Приоритет действий", ""])
    lines.append("1. Вернуть в наличие хиты с уже доказанным спросом.")
    lines.append("2. Расширять группы `Настольные и карточные игры`, `Пазлы`, `Творчество и рукоделие`, `Магнитные игры и одевашки`, `Деревянные игрушки и шнуровки`.")
    lines.append("3. Держать основной фокус в цене `199-499 ₽`.")
    lines.append("4. Углублять линейки с повторяющимися мотивами: Disney-пазлы, одевашки, викторины, мыло/творчество, шнуровки, опыты.")
    lines.append("5. Отдельно добрать идеи, где реальные конкуренты уже показали сильный спрос: археология/раскопки, spa-наборы и наборы для творчества, недорогие магнитные истории.")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Build a growth plan from existing MM market analysis reports.")
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--date-tag", default=DEFAULT_DATE)
    return parser.parse_args()


def main():
    args = parse_args()
    report_dir = Path(args.report_dir)
    groups = load_json(report_dir / f"my_product_groups_{args.date_tag}.json")
    top10_report = load_json(report_dir / f"idea_competitor_comparison_top10_{args.date_tag}.json")
    real_report = load_json(report_dir / f"idea_competitor_comparison_real_{args.date_tag}.json")
    my_summary = load_json(report_dir / "my_shop_summary.json")
    operational_context = load_operational_context(report_dir)
    title_sets = build_operational_title_sets(operational_context)
    groups = apply_window_signals(groups, title_sets)

    summary = choose_expansion_groups(groups)
    gaps = top_active_gaps(groups)
    line_ideas = extract_line_ideas(groups)
    competitor_findings = best_competitor_opportunities(real_report)

    json_path = report_dir / f"growth_plan_{args.date_tag}.json"
    md_path = report_dir / f"growth_plan_{args.date_tag}.md"
    payload = {
        "expansion_groups": summary,
        "availability_gaps": gaps,
        "line_ideas": line_ideas,
        "competitor_findings": competitor_findings,
        "operational_context_used": bool(operational_context),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(md_path, summary, gaps, line_ideas, competitor_findings, top10_report, real_report, my_summary, args.date_tag)
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
