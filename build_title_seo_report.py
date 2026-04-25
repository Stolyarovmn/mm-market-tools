#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

from core.io_utils import load_json, write_json
from core.paths import REPORTS_DIR, ensure_dir, today_tag


STOPWORDS = {
    "и", "с", "со", "для", "на", "по", "из", "под", "в", "во", "к", "ко", "от", "до",
    "детский", "детская", "детские", "детское", "большой", "большая", "большие",
    "русский", "русская", "русские", "набор", "игрушка", "игрушки",
}

PRODUCT_NOUNS = [
    "пазл", "пазлы", "игра", "игры", "набор", "наборы", "кукла", "куклами",
    "кубики", "кубик", "конструктор", "конструкторы", "мозаика", "шнуровка",
    "сортер", "пирамида", "пирамидка", "домино", "вкладыши", "опыты", "пазл",
    "постер", "книга", "азбука", "буквы", "ходилка", "бродилка", "картина",
    "раскраска", "вышивка", "мыльные", "пузыри", "пазл", "пазлы", "магнитная",
    "магнитный", "магнитная", "игрушка", "наклейки", "бластер", "пистолет",
    "рюкзак", "наволочки", "наволочка", "чехол", "чехлы", "доски", "выжигания",
    "юбка", "носок", "носки", "скатерть", "накидка", "сиденье", "приборов",
]

ENTITY_PHRASES = [
    "синий трактор",
    "холодное сердце",
    "три кота",
    "мимимишки",
    "ми ми мишки",
    "фиксики",
    "лунтик",
    "барбоскины",
    "единорог",
    "корги",
    "пони",
    "котики",
    "алиса",
    "ксюша",
    "дисней",
]

GENERIC_LEAD_WORDS = {
    "детский", "детская", "детские", "детское",
    "магнитная", "магнитный", "деревянные", "деревянная", "большой", "большая",
    "новогодние", "развивающая", "развивающий", "логическая", "интерактивная",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit whether important title keywords appear early enough for search CTR/ranking."
    )
    parser.add_argument(
        "--input-json",
        default="/home/user/mm-market-tools/data/normalized/weekly_operational_report_2026-04-08.json",
    )
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--report-prefix", default=f"title_seo_report_{today_tag()}")
    parser.add_argument("--top-rows", type=int, default=150)
    return parser.parse_args()


def normalize_text(text):
    return re.sub(r"[^0-9a-zA-Zа-яА-ЯёЁ]+", " ", str(text or "")).strip().lower()


def tokenize(text):
    return [token for token in normalize_text(text).split() if token]


def first_meaningful_tokens(tokens, limit=3):
    return [token for token in tokens if token not in STOPWORDS][:limit]


def find_first_product_noun(tokens):
    for token in tokens:
        if token in PRODUCT_NOUNS:
            return token
    return None


def find_entities(normalized_title, tokens):
    found = []
    for phrase in ENTITY_PHRASES:
        if phrase in normalized_title:
            found.append(phrase)
    if found:
        return found
    # fallback: capitalizable special tokens already normalized as one word
    return [token for token in tokens if token in ENTITY_PHRASES]


def keyword_position(tokens, phrase):
    parts = phrase.split()
    if len(parts) == 1:
        try:
            return tokens.index(parts[0]) + 1
        except ValueError:
            return None
    for index in range(len(tokens) - len(parts) + 1):
        if tokens[index : index + len(parts)] == parts:
            return index + 1
    return None


def classify_title(row):
    title = row.get("title") or ""
    tokens = tokenize(title)
    if not tokens:
        return None
    normalized_title = normalize_text(title)
    lead_tokens = first_meaningful_tokens(tokens, 3)
    main_noun = find_first_product_noun(tokens)
    entities = find_entities(normalized_title, tokens)
    main_noun_pos = keyword_position(tokens, main_noun) if main_noun else None
    entity_positions = {entity: keyword_position(tokens, entity) for entity in entities}
    entity_early = [entity for entity, pos in entity_positions.items() if pos and pos <= 3]
    issues = []
    recommendations = []
    score = 100

    if main_noun and (main_noun_pos is None or main_noun_pos > 3):
        score -= 40
        issues.append("main_noun_late")
        recommendations.append("Перенести главный тип товара в первые 3 слова.")
    elif not main_noun:
        score -= 30
        issues.append("main_noun_unknown")
        recommendations.append("Уточнить главный тип товара явным существительным в начале title.")

    if entities and not entity_early:
        score -= 25
        issues.append("entity_late")
        recommendations.append("Поднять персонажа/бренд ближе к началу title.")

    if lead_tokens and all(token in GENERIC_LEAD_WORDS for token in lead_tokens[: min(2, len(lead_tokens))]):
        score -= 15
        issues.append("generic_lead")
        recommendations.append("Убрать слишком общие прилагательные из начала и начать с товара или сильного entity.")

    if len(tokens) > 14:
        score -= 10
        issues.append("title_too_long")
        recommendations.append("Сжать title: убрать дубли и слабые хвосты.")

    score = max(score, 0)
    status = "strong"
    if score < 75:
        status = "needs_work"
    if score < 50:
        status = "priority_fix"

    return {
        "key": row.get("key"),
        "product_id": row.get("product_id"),
        "title": title,
        "title_tokens": tokens,
        "lead_tokens": lead_tokens,
        "main_noun": main_noun,
        "main_noun_position": main_noun_pos,
        "entities": entities,
        "entity_positions": entity_positions,
        "seo_score": score,
        "seo_status": status,
        "issues": issues,
        "recommendations": recommendations,
        "units_sold": row.get("units_sold", 0),
        "gross_profit": row.get("gross_profit", 0.0),
        "stock_value_sale": row.get("stock_value_sale", 0.0),
        "current_winner": bool(row.get("current_winner")),
        "stale_stock": bool(row.get("stale_stock")),
    }


def build_markdown(rows, source_path):
    lines = [
        "# Title SEO Report",
        "",
        f"- source: `{source_path}`",
        f"- audited rows: `{len(rows)}`",
        "",
        "## Priority fixes",
        "",
    ]
    priority = [row for row in rows if row["seo_status"] == "priority_fix"]
    if not priority:
        lines.append("- Критичных title не найдено.")
        return "\n".join(lines)
    for row in priority[:25]:
        recs = "; ".join(row["recommendations"]) or "нет"
        lines.extend(
            [
                f"### {row['title']}",
                "",
                f"- score: `{row['seo_score']}`",
                f"- lead tokens: `{', '.join(row['lead_tokens']) or 'н/д'}`",
                f"- main noun: `{row['main_noun'] or 'н/д'}` at `{row['main_noun_position'] or 'н/д'}`",
                f"- entities: `{', '.join(row['entities']) or 'н/д'}`",
                f"- issues: `{', '.join(row['issues']) or 'н/д'}`",
                f"- recommendation: `{recs}`",
                "",
            ]
        )
    return "\n".join(lines)


def main():
    args = parse_args()
    payload = load_json(Path(args.input_json))
    report_dir = ensure_dir(Path(args.report_dir))
    rows = []
    source_rows = payload.get("rows") or []
    for row in source_rows[: args.top_rows]:
        classified = classify_title(row)
        if classified:
            rows.append(classified)
    rows.sort(
        key=lambda row: (
            {"priority_fix": 0, "needs_work": 1, "strong": 2}.get(row["seo_status"], 3),
            row["seo_score"],
            -(row["units_sold"] or 0),
            -(row["stock_value_sale"] or 0),
        )
    )
    summary = {
        "audited_rows": len(rows),
        "priority_fix_count": sum(1 for row in rows if row["seo_status"] == "priority_fix"),
        "needs_work_count": sum(1 for row in rows if row["seo_status"] == "needs_work"),
        "strong_count": sum(1 for row in rows if row["seo_status"] == "strong"),
        "main_noun_late_count": sum(1 for row in rows if "main_noun_late" in row["issues"]),
        "entity_late_count": sum(1 for row in rows if "entity_late" in row["issues"]),
        "generic_lead_count": sum(1 for row in rows if "generic_lead" in row["issues"]),
        "title_too_long_count": sum(1 for row in rows if "title_too_long" in row["issues"]),
    }
    result = {
        "generated_from": args.input_json,
        "summary": summary,
        "rows": rows,
    }
    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    write_json(json_path, result)
    md_path.write_text(build_markdown(rows, args.input_json), encoding="utf-8")
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
