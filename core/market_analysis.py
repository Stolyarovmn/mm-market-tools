#!/usr/bin/env python3
import re
import statistics
from collections import Counter, defaultdict


GROUP_RULES = [
    ("Пазлы", ["пазл", "макси", "контурн", "половинки", "рамке", "джигсо"]),
    ("Настольные и карточные игры", ["настольн", "викторин", "мемо", "лото", "мафия", "дубл", "дуббл", "домино", "фанты", "ходилка", "бродилка", "объяснялк", "словодел", "кто я", "квест", "карточн"]),
    ("Магнитные игры и одевашки", ["магнит", "одеваш", "магнитн"]),
    ("Творчество и рукоделие", ["раскраск", "картина", "аппликац", "наклейк", "мыло", "шить", "вышив", "выжиган", "фетр", "рисуй", "гравюр", "алмазн", "творчеств"]),
    ("Опыты и наука", ["опыт", "эксперимент", "наука", "химическ", "археолог", "раскопк", "лаборатор", "физик"]),
    ("Деревянные игрушки и шнуровки", ["деревян", "шнуровк", "рыбалк", "сортер", "вкладыш", "рамка-вклад", "балансир"]),
    ("Кубики, мозаика и пирамидки", ["кубик", "мозаик", "пирамид", "стаканчик", "сортер", "башн"]),
    ("Книги и обучающие материалы", ["книга", "книжка", "азбук", "алфавит", "карточк", "логик", "головолом", "судоку", "прописи", "обуча", "буквы", "цифры"]),
    ("Игровые наборы и кухня", ["продукт", "фрукт", "овощ", "кухн", "посуда", "касс", "магазин", "плита", "еда", "тележк", "корзин"]),
    ("Мягкие игрушки и театр", ["мягк", "плюш", "театр", "перчатк", "игрушка-брелок"]),
    ("Конструкторы", ["конструктор", "лего", "lego", "блочн"]),
    ("Антистрессы и сквиши", ["антистресс", "сквиш", "фиджет", "спиннер", "pop it", "поп ит", "кейкап", "присоск", "лапка таба"]),
    ("Ролевые игрушки и бластеры", ["пистолет", "бластер", "водяной", "глок", "glock", "меч", "катана", "керамбит", "нунчак", "наручник"]),
    ("Товары для малышей", ["прорезывател", "грызунок", "погремуш", "малыш", "силиконов"]),
    ("Куклы и фигурки", ["кукл", "пупс", "фигурк", "единорог", "пони", "принцесс", "русалк"]),
    ("Транспорт и машинки", ["машин", "машинка", "автовоз", "трактор", "экскаватор", "паровоз", "поезд", "самолет", "вертолет", "автобус"]),
    ("Рюкзаки и аксессуары", ["рюкзак", "ранец", "сумк", "чехол", "накидка", "незапинайка"]),
]

STOPWORDS = {
    "для", "и", "с", "на", "в", "по", "от", "из", "под", "над", "или", "но",
    "детская", "детские", "детский", "игра", "игрушка", "игрушки", "набор", "наборы",
    "товар", "шт", "см", "мл", "подарок", "мальчиков", "девочек", "девочки", "мальчика",
    "детей", "ребенка", "ребёнка", "девочкам", "мальчикам", "варианта", "вариантов",
}

TOKEN_REPLACEMENTS = {
    "лабубу": "брелок",
    "labubu": "брелок",
    "куроми": "брелок",
    "стич": "брелок",
    "вакуку": "брелок",
    "капибара": "антистресс",
    "гусь": "антистресс",
    "попит": "поп ит",
    "popit": "поп ит",
    "пазлы": "пазл",
    "кубики": "кубик",
    "книжки": "книга",
    "одевашка": "одевашки",
    "одевашки": "одевашки",
    "магнитная": "магнит",
    "магнитные": "магнит",
    "магнитный": "магнит",
}


def _normalize_text(value):
    return re.sub(r"\s+", " ", (value or "").lower().replace("ё", "е")).strip()


def _tokenize_title(title):
    raw = re.sub(r"[^a-zа-я0-9]+", " ", _normalize_text(title), flags=re.IGNORECASE)
    tokens = []
    for token in raw.split():
        if token.isdigit() or len(token) < 3:
            continue
        token = TOKEN_REPLACEMENTS.get(token, token)
        if token in STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def classify_group(title):
    lowered = _normalize_text(title)
    tokens = _tokenize_title(title)
    token_text = " ".join(tokens)
    token_set = set(tokens)

    if {"пистолет", "бластер", "глок", "меч", "катана", "керамбит", "нунчак", "наручник"} & token_set:
        return "Ролевые игрушки и бластеры"
    if {"продукт", "фрукт", "овощ", "кухн", "посуда", "касс", "магазин", "плита", "корзин"} & token_set:
        return "Игровые наборы и кухня"
    if "брелок" in token_set and ("мягк" in lowered or "плюш" in lowered or "лабубу" in lowered or "wakuku" in lowered):
        return "Мягкие игрушки и театр"

    best_group = "Прочее"
    best_score = 0
    for group_name, keywords in GROUP_RULES:
        score = 0
        for keyword in keywords:
            normalized_keyword = _normalize_text(keyword)
            if normalized_keyword in lowered:
                score += 3
            if normalized_keyword in token_text:
                score += 2
            if any(token.startswith(normalized_keyword[:5]) for token in tokens if len(normalized_keyword) >= 5):
                score += 1
        if score > best_score:
            best_group = group_name
            best_score = score
    return best_group


def price_band_label(price):
    price = float(price or 0.0)
    if price <= 0:
        return "0"
    if price < 200:
        return "0-199"
    if price < 500:
        return "200-499"
    if price < 800:
        return "500-799"
    if price < 1200:
        return "800-1199"
    return "1200+"


def idea_fingerprint(title, group=None):
    tokens = _tokenize_title(title)
    if not tokens:
        fallback = re.sub(r"\s+", " ", (title or "").strip().lower())
        return fallback[:80]
    group_tokens = set(_tokenize_title(group or ""))
    filtered = [token for token in tokens if token not in group_tokens]
    ranked = Counter(filtered or tokens)
    key = [token for token, _ in ranked.most_common(4)]
    return " ".join(sorted(key))


def dominance_profile(order_values):
    values = [float(value or 0.0) for value in order_values if float(value or 0.0) > 0]
    total = sum(values)
    if not values or total <= 0:
        return {
            "leading_share_pct": None,
            "hhi": None,
            "competition_profile": "недостаточно данных",
        }
    shares = [value / total for value in values]
    leading_share = max(shares) * 100
    hhi = sum((share * 100) ** 2 for share in shares)
    if hhi >= 2500:
        profile = "высокая концентрация"
    elif hhi >= 1500:
        profile = "умеренная концентрация"
    else:
        profile = "раздробленный сегмент"
    return {
        "leading_share_pct": round(leading_share, 2),
        "hhi": round(hhi, 2),
        "competition_profile": profile,
    }


def novelty_proxy(row):
    orders = float(row.get("orders") or 0.0)
    reviews = float(row.get("reviews") or 0.0)
    if orders <= 0:
        return {
            "novelty_proxy_score": 0.0,
            "novelty_proxy_profile": "недостаточно данных",
            "review_density": None,
        }
    review_density = reviews / orders if orders else None
    orders_signal = min(45.0, orders * 0.45)
    freshness_signal = max(0.0, 40.0 - reviews * 1.5)
    density_signal = max(0.0, 20.0 - ((review_density or 0.0) * 100.0))
    score = round(max(0.0, min(100.0, orders_signal + freshness_signal + density_signal)), 2)
    if score >= 65:
        profile = "категория открыта для нового входа"
    elif score >= 40:
        profile = "есть свежие сигналы"
    else:
        profile = "рынок зрелый"
    return {
        "novelty_proxy_score": score,
        "novelty_proxy_profile": profile,
        "review_density": round(review_density, 4) if review_density is not None else None,
    }


def novelty_profile(rows, top_n=10):
    ranked = sorted(rows, key=lambda row: row.get("orders", 0), reverse=True)[:top_n]
    if not ranked:
        return {
            "novelty_proxy_index": None,
            "fresh_top_product_share_pct": None,
            "novelty_profile": "недостаточно данных",
        }
    scores = [float(row.get("novelty_proxy_score") or 0.0) for row in ranked]
    fresh_count = sum(1 for row in ranked if float(row.get("novelty_proxy_score") or 0.0) >= 65.0)
    index = round(sum(scores) / len(scores), 2) if scores else None
    share = round((fresh_count / len(ranked)) * 100, 2) if ranked else None
    if index is None:
        profile = "недостаточно данных"
    elif index >= 65 or (share is not None and share >= 40):
        profile = "категория открыта для нового входа"
    elif index >= 40:
        profile = "есть окно для агрессивного входа"
    else:
        profile = "рынок зрелый"
    return {
        "novelty_proxy_index": index,
        "fresh_top_product_share_pct": share,
        "novelty_profile": profile,
    }


def entry_window_score(*, hhi, novelty_index, leader_share, seller_count, price_gap_pct):
    score = 50.0
    if hhi is not None:
        if hhi < 1500:
            score += 25
        elif hhi < 2500:
            score += 10
        else:
            score -= 15
    if novelty_index is not None:
        if novelty_index >= 65:
            score += 20
        elif novelty_index >= 40:
            score += 10
        else:
            score -= 10
    if leader_share is not None:
        if leader_share >= 60:
            score -= 20
        elif leader_share >= 40:
            score -= 8
    if seller_count <= 2:
        score -= 8
    elif seller_count >= 5:
        score += 5
    if price_gap_pct is not None:
        if price_gap_pct <= -15:
            score += 5
        elif price_gap_pct >= 20:
            score -= 5
    return round(max(0.0, min(100.0, score)), 2)


def entry_window_profile(score):
    if score >= 75:
        return "сильное окно входа"
    if score >= 58:
        return "рабочее окно входа"
    if score >= 42:
        return "вход возможен, но нужен сильный оффер"
    return "окно слабое или перегретое"


def market_margin_fit_profile(margin_fit_pct, *, target_margin_pct=35.0):
    if margin_fit_pct is None:
        return "недостаточно данных"
    if margin_fit_pct >= target_margin_pct + 10:
        return "экономика комфортная"
    if margin_fit_pct >= target_margin_pct:
        return "экономика рабочая"
    if margin_fit_pct >= max(20.0, target_margin_pct - 10):
        return "экономика напряженная"
    return "экономика не сходится"


def entry_window_strategy(
    *,
    score,
    hhi,
    novelty_index,
    leader_share,
    market_margin_fit_pct,
    target_margin_pct=35.0,
):
    if market_margin_fit_pct is None:
        if score >= 58 and (hhi or 0) < 2500 and (novelty_index or 0) >= 40:
            return {
                "entry_strategy_bucket": "validate_economics",
                "entry_strategy_label": "проверить экономику и тестировать",
                "entry_strategy_reason": "структура спроса выглядит рабочей, но по вашей себестоимости пока не хватает данных",
            }
        if (hhi or 0) >= 2500 and (novelty_index or 0) < 40:
            return {
                "entry_strategy_bucket": "avoid",
                "entry_strategy_label": "не входить без доп. данных",
                "entry_strategy_reason": "сегмент уже плотный, а экономика ещё не подтверждена",
            }
        return {
            "entry_strategy_bucket": "watch",
            "entry_strategy_label": "наблюдать и добирать данные",
            "entry_strategy_reason": "окно ещё нельзя уверенно оценить без связи с вашей себестоимостью",
        }

    if market_margin_fit_pct < max(20.0, target_margin_pct - 15):
        return {
            "entry_strategy_bucket": "improve_sourcing",
            "entry_strategy_label": "не входить без новой закупки",
            "entry_strategy_reason": "рыночная цена слишком близка к вашей себестоимости и не оставляет здоровой маржи",
        }

    if (hhi or 0) >= 3200 and (novelty_index or 0) < 40 and (leader_share or 0) >= 55:
        return {
            "entry_strategy_bucket": "avoid",
            "entry_strategy_label": "не входить: сегмент перегрет",
            "entry_strategy_reason": "в сегменте высокая концентрация, лидер уже закрепился, а свежий вход слабый",
        }

    if score >= 72 and market_margin_fit_pct >= target_margin_pct and (hhi or 0) < 2500:
        return {
            "entry_strategy_bucket": "enter_now",
            "entry_strategy_label": "входить первым",
            "entry_strategy_reason": "и структура рынка, и ваша потенциальная экономика выглядят рабочими уже сейчас",
        }

    if score >= 58 and market_margin_fit_pct >= max(25.0, target_margin_pct - 10):
        return {
            "entry_strategy_bucket": "test_entry",
            "entry_strategy_label": "тестировать вход",
            "entry_strategy_reason": "ниша не идеальна, но уже допускает аккуратный тестовый вход с сильным оффером",
        }

    if market_margin_fit_pct < target_margin_pct:
        return {
            "entry_strategy_bucket": "improve_sourcing",
            "entry_strategy_label": "сначала улучшить закупку",
            "entry_strategy_reason": "спрос может быть интересным, но ваша текущая экономика пока слабее целевой маржи",
        }

    return {
        "entry_strategy_bucket": "watch",
        "entry_strategy_label": "наблюдать",
        "entry_strategy_reason": "окно не закрыто, но пока не выглядит приоритетом первого эшелона",
    }


def _seller_title(seller_lookup, seller_id, fallback):
    seller_meta = seller_lookup.get(seller_id) or {}
    return seller_meta.get("title") or fallback or f"seller_{seller_id}"


def summarize_market(items, seller_lookup, my_group_prices):
    sellers = defaultdict(list)
    groups = defaultdict(list)
    price_bands = defaultdict(list)
    idea_clusters = defaultdict(list)
    for item in items:
        sellers[item["seller_id"]].append(item)
        groups[item["group"]].append(item)
        price_bands[item["price_band"]].append(item)
        idea_clusters[item["idea_cluster"]].append(item)

    top_sellers = []
    for seller_id, rows in sellers.items():
        seller_meta = seller_lookup.get(seller_id) or {}
        prices = [row["price"] for row in rows if row["price"] > 0]
        group_orders = Counter()
        for row in rows:
            group_orders[row["group"]] += row["orders"]
        top_group = group_orders.most_common(1)[0][0] if group_orders else "Прочее"
        seller_novelty = novelty_profile(rows, top_n=8)
        top_sellers.append(
            {
                "seller_id": seller_id,
                "seller_title": seller_meta.get("title") or rows[0].get("seller_title") or f"seller_{seller_id}",
                "seller_slug": seller_meta.get("link"),
                "products_seen": len(rows),
                "orders_sum": sum(row["orders"] for row in rows),
                "avg_price": round(sum(prices) / len(prices), 2) if prices else 0.0,
                "median_price": round(statistics.median(prices), 2) if prices else 0.0,
                "top_group": top_group,
                "share_of_observed_orders_pct": 0.0,
                "novelty_proxy_index": seller_novelty["novelty_proxy_index"],
                "fresh_top_product_share_pct": seller_novelty["fresh_top_product_share_pct"],
                "novelty_profile": seller_novelty["novelty_profile"],
                "top_products": sorted(rows, key=lambda row: row["orders"], reverse=True)[:5],
            }
        )
    top_sellers.sort(key=lambda row: (row["orders_sum"], row["products_seen"]), reverse=True)
    total_orders = sum(row["orders_sum"] for row in top_sellers)
    for row in top_sellers:
        row["share_of_observed_orders_pct"] = round((row["orders_sum"] / total_orders) * 100, 2) if total_orders else 0.0

    group_rows = []
    for group_name, rows in groups.items():
        prices = [row["price"] for row in rows if row["price"] > 0]
        seller_count = len({row["seller_id"] for row in rows})
        top_products = sorted(rows, key=lambda row: row["orders"], reverse=True)[:10]
        by_seller = defaultdict(int)
        for row in rows:
            by_seller[row["seller_id"]] += row["orders"]
        dominance = dominance_profile(by_seller.values())
        novelty = novelty_profile(rows, top_n=10)
        top_group_sellers = []
        for seller_id, orders_sum in sorted(by_seller.items(), key=lambda entry: entry[1], reverse=True)[:5]:
            top_group_sellers.append(
                {
                    "seller_id": seller_id,
                    "seller_title": _seller_title(seller_lookup, seller_id, None),
                    "orders_sum": orders_sum,
                }
            )
        my_prices = my_group_prices.get(group_name) or {}
        market_avg = round(sum(prices) / len(prices), 2) if prices else 0.0
        group_rows.append(
            {
                "group": group_name,
                "products_seen": len(rows),
                "seller_count": seller_count,
                "orders_sum": sum(row["orders"] for row in rows),
                "avg_price": market_avg,
                "median_price": round(statistics.median(prices), 2) if prices else 0.0,
                "my_avg_price": my_prices.get("my_avg_price"),
                "my_median_price": my_prices.get("my_median_price"),
                "my_sku_count": my_prices.get("my_sku_count", 0),
                "price_gap_pct": round(((my_prices.get("my_avg_price") - market_avg) / market_avg) * 100, 2)
                if prices and my_prices.get("my_avg_price") is not None and market_avg
                else None,
                "leading_seller_share_pct": dominance["leading_share_pct"],
                "dominance_hhi": dominance["hhi"],
                "competition_profile": dominance["competition_profile"],
                "novelty_proxy_index": novelty["novelty_proxy_index"],
                "fresh_top_product_share_pct": novelty["fresh_top_product_share_pct"],
                "novelty_profile": novelty["novelty_profile"],
                "top_sellers": top_group_sellers,
                "top_products": top_products,
            }
        )
    group_rows.sort(key=lambda row: row["orders_sum"], reverse=True)

    overall_dominance = dominance_profile(row["orders_sum"] for row in top_sellers)
    overall_novelty = novelty_profile(items, top_n=20)

    band_rows = []
    for band, rows in sorted(price_bands.items()):
        band_rows.append(
            {
                "price_band": band,
                "products_seen": len(rows),
                "seller_count": len({row["seller_id"] for row in rows}),
                "orders_sum": sum(row["orders"] for row in rows),
                "avg_price": round(sum(row["price"] for row in rows) / len(rows), 2) if rows else 0.0,
            }
        )
    band_rows.sort(key=lambda row: row["orders_sum"], reverse=True)

    entry_window_rows = []
    grouped_by_window = defaultdict(list)
    for item in items:
        grouped_by_window[(item["group"], item["price_band"])].append(item)
    for (group_name, price_band), rows in grouped_by_window.items():
        if len(rows) < 2:
            continue
        prices = [row["price"] for row in rows if row["price"] > 0]
        by_seller = defaultdict(int)
        for row in rows:
            by_seller[row["seller_id"]] += row["orders"]
        dominance = dominance_profile(by_seller.values())
        novelty = novelty_profile(rows, top_n=6)
        my_prices = my_group_prices.get(group_name) or {}
        market_avg = round(sum(prices) / len(prices), 2) if prices else 0.0
        price_gap_pct = round(((my_prices.get("my_avg_price") - market_avg) / market_avg) * 100, 2) if prices and my_prices.get("my_avg_price") is not None and market_avg else None
        score = entry_window_score(
            hhi=dominance["hhi"],
            novelty_index=novelty["novelty_proxy_index"],
            leader_share=dominance["leading_share_pct"],
            seller_count=len(by_seller),
            price_gap_pct=price_gap_pct,
        )
        entry_window_rows.append(
            {
                "group": group_name,
                "price_band": price_band,
                "products_seen": len(rows),
                "seller_count": len(by_seller),
                "orders_sum": sum(row["orders"] for row in rows),
                "avg_price": market_avg,
                "my_avg_price": my_prices.get("my_avg_price"),
                "price_gap_pct": price_gap_pct,
                "leading_seller_share_pct": dominance["leading_share_pct"],
                "dominance_hhi": dominance["hhi"],
                "competition_profile": dominance["competition_profile"],
                "novelty_proxy_index": novelty["novelty_proxy_index"],
                "novelty_profile": novelty["novelty_profile"],
                "entry_window_score": score,
                "entry_window_profile": entry_window_profile(score),
                "top_products": sorted(rows, key=lambda row: row["orders"], reverse=True)[:5],
            }
        )
    entry_window_rows.sort(key=lambda row: (row["entry_window_score"], row["orders_sum"]), reverse=True)

    cluster_rows = []
    for cluster, rows in idea_clusters.items():
        if len(rows) < 2:
            continue
        prices = [row["price"] for row in rows if row["price"] > 0]
        novelty = novelty_profile(rows, top_n=5)
        cluster_rows.append(
            {
                "idea_cluster": cluster,
                "group": rows[0]["group"],
                "products_seen": len(rows),
                "seller_count": len({row["seller_id"] for row in rows}),
                "orders_sum": sum(row["orders"] for row in rows),
                "avg_price": round(sum(prices) / len(prices), 2) if prices else 0.0,
                "novelty_proxy_index": novelty["novelty_proxy_index"],
                "novelty_profile": novelty["novelty_profile"],
                "top_products": sorted(rows, key=lambda row: row["orders"], reverse=True)[:5],
            }
        )
    cluster_rows.sort(key=lambda row: (row["orders_sum"], row["products_seen"]), reverse=True)

    other_group_share_pct = None
    observed_orders_sum = sum(row["orders_sum"] for row in group_rows)
    other_group = next((row for row in group_rows if row["group"] == "Прочее"), None)
    if other_group and observed_orders_sum:
        other_group_share_pct = round((other_group["orders_sum"] / observed_orders_sum) * 100, 2)

    return {
        "summary": {
            "observed_products": len(items),
            "observed_sellers": len(sellers),
            "observed_groups": len(groups),
            "observed_price_bands": len(price_bands),
            "observed_idea_clusters": len(cluster_rows),
            "overall_leading_seller_share_pct": overall_dominance["leading_share_pct"],
            "overall_dominance_hhi": overall_dominance["hhi"],
            "overall_competition_profile": overall_dominance["competition_profile"],
            "novelty_proxy_index": overall_novelty["novelty_proxy_index"],
            "fresh_top_product_share_pct": overall_novelty["fresh_top_product_share_pct"],
            "novelty_profile": overall_novelty["novelty_profile"],
            "other_group_share_pct": other_group_share_pct,
        },
        "top_sellers": top_sellers[:20],
        "top_products": sorted(items, key=lambda row: row["orders"], reverse=True)[:30],
        "groups": group_rows,
        "price_bands": band_rows,
        "entry_windows": entry_window_rows[:30],
        "idea_clusters": cluster_rows[:30],
    }
