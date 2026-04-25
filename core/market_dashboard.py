#!/usr/bin/env python3
import datetime as dt

from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION


def _money(value):
    return round(float(value or 0.0), 2)


def _top_rows(rows, limit=15):
    return rows[:limit]


def build_market_dashboard(payload, metadata=None):
    metadata = metadata or {}
    summary = payload.get("summary", {})
    groups = payload.get("groups", [])
    top_sellers = payload.get("top_sellers", [])
    top_products = payload.get("top_products", [])
    price_bands = payload.get("price_bands", [])
    entry_windows = payload.get("entry_windows", [])
    idea_clusters = payload.get("idea_clusters", [])

    strongest_group = groups[0] if groups else {}
    hottest_band = price_bands[0] if price_bands else {}
    top_seller = top_sellers[0] if top_sellers else {}
    overall_profile = summary.get("overall_competition_profile")
    overall_share = summary.get("overall_leading_seller_share_pct")
    overall_hhi = summary.get("overall_dominance_hhi")
    novelty_index = summary.get("novelty_proxy_index")
    novelty_profile = summary.get("novelty_profile")
    other_group_share = summary.get("other_group_share_pct")
    target_margin_pct = summary.get("target_margin_pct")
    economics_coverage_groups_pct = summary.get("economics_coverage_groups_pct")
    economics_coverage_windows_pct = summary.get("economics_coverage_windows_pct")

    blind_spots = [
        row for row in entry_windows
        if row.get("market_margin_fit_pct") is None and (row.get("entry_window_score") or 0) >= 45
    ][:12]
    strongest_economic_groups = sorted(
        [row for row in groups if row.get("market_margin_fit_pct") is not None],
        key=lambda row: ((row.get("market_margin_fit_pct") or 0), (row.get("orders_sum") or 0)),
        reverse=True,
    )[:12]

    insights = []
    if overall_profile:
        share_text = "н/д" if overall_share is None else f"{overall_share}%"
        hhi_text = "н/д" if overall_hhi is None else str(overall_hhi)
        insights.append(
            {
                "title": "Насыщенность рынка уже можно оценивать",
                "text": f"По наблюдаемой выборке рынок выглядит так: {overall_profile}. Доля крупнейшего продавца в видимых заказах: {share_text}, HHI: {hhi_text}. Для входа в нишу комфортнее сегменты с HHI ниже 1500, а при HHI выше 2500 уже нужен сильный оффер и аккуратный вход.",
                "tone": "warn" if overall_hhi and overall_hhi >= 2500 else "good",
            }
        )
    if novelty_profile:
        novelty_text = "н/д" if novelty_index is None else str(novelty_index)
        insights.append(
            {
                "title": "Индекс новизны категории",
                "text": f"Прокси-индекс новизны сейчас {novelty_text}. Это не реальный возраст карточек, а сигнал по связке orders/reviews у лидеров: {novelty_profile}. Чем выше индекс, тем больше шанс, что в категории ещё могут быстро выстреливать новые карточки.",
                "tone": "good" if novelty_index and novelty_index >= 40 else "warn",
            }
        )
    if strongest_group:
        gap = strongest_group.get("price_gap_pct")
        gap_text = "н/д" if gap is None else f"{gap}%"
        lead_text = "н/д" if strongest_group.get("leading_seller_share_pct") is None else f"{strongest_group.get('leading_seller_share_pct')}%"
        novelty_text = "н/д" if strongest_group.get("novelty_proxy_index") is None else str(strongest_group.get("novelty_proxy_index"))
        insights.append(
            {
                "title": "Сильнейшая группа в наблюдаемом рынке",
                "text": f"{strongest_group.get('group', 'н/д')} даёт {strongest_group.get('orders_sum', 0)} orders. Ваш средний ценовой gap к этой группе: {gap_text}. Доля лидера внутри группы: {lead_text}. Прокси-индекс новизны группы: {novelty_text}.",
                "tone": "good",
            }
        )
    if hottest_band:
        insights.append(
            {
                "title": "Главный ценовой коридор рынка",
                "text": f"В выборке лидирует диапазон {hottest_band.get('price_band', 'н/д')} ₽: {hottest_band.get('orders_sum', 0)} orders, {hottest_band.get('products_seen', 0)} товаров.",
                "tone": "good",
            }
        )
    if top_seller:
        insights.append(
            {
                "title": "Верхний продавец выборки",
                "text": f"{top_seller.get('seller_title', 'н/д')} даёт {top_seller.get('orders_sum', 0)} orders, доля в наблюдаемом спросе {top_seller.get('share_of_observed_orders_pct', 0)}% и ядро в группе {top_seller.get('top_group', 'н/д')}.",
                "tone": "warn",
            }
        )
    if idea_clusters:
        insights.append(
            {
                "title": "Повторяющиеся идеи уже видны",
                "text": f"В наблюдаемой выборке нашлось {summary.get('observed_idea_clusters', 0)} повторяющихся idea clusters. Их стоит использовать как карту для расширения ассортимента, а не только смотреть на одиночные SKU.",
                "tone": "good",
            }
        )
    if entry_windows:
        best_window = entry_windows[0]
        insights.append(
            {
                "title": "Окно входа уже можно выделить",
                "text": f"Лучшее окно сейчас: {best_window.get('group', 'н/д')} / {best_window.get('price_band', 'н/д')} ₽. Score {best_window.get('entry_window_score', 'н/д')}, профиль: {best_window.get('entry_window_profile', 'н/д')}, решение: {best_window.get('entry_strategy_label', 'н/д')}. Это самый прямой кандидат на дальнейший drilldown.",
                "tone": "good" if (best_window.get("entry_window_score") or 0) >= 58 else "warn",
            }
        )
    if economics_coverage_groups_pct is not None or economics_coverage_windows_pct is not None:
        insights.append(
            {
                "title": "Экономика рынка покрыта не полностью",
                "text": f"По вашей себестоимости сейчас удаётся проверить группы на {economics_coverage_groups_pct}% и окна входа на {economics_coverage_windows_pct}%. Чем выше это покрытие, тем увереннее можно говорить не только про спрос, но и про прибыльность входа.",
                "tone": "good" if (economics_coverage_windows_pct or 0) >= 50 else "warn",
            }
        )
    if blind_spots:
        top_blind = blind_spots[0]
        insights.append(
            {
                "title": "Есть слепые зоны с живым спросом",
                "text": f"Сейчас найдено {len(blind_spots)} окон входа, где спрос уже выглядит рабочим, но по вашей себестоимости ещё нет связки. Самая важная слепая зона: {top_blind.get('group', 'н/д')} / {top_blind.get('price_band', 'н/д')} ₽, score {top_blind.get('entry_window_score', 'н/д')}. Это сигнал добирать cost-данные, а не принимать решение вслепую.",
                "tone": "warn",
            }
        )
    if strongest_economic_groups:
        strongest_economic = strongest_economic_groups[0]
        insights.append(
            {
                "title": "Есть группы, где экономика уже понятна",
                "text": f"Лучше всего по подтверждённой экономике сейчас выглядит группа {strongest_economic.get('group', 'н/д')}: market margin fit {strongest_economic.get('market_margin_fit_pct', 'н/д')}%, orders {strongest_economic.get('orders_sum', 0)}. Это полезнее для управленческих решений, чем просто смотреть на спрос без cost-контекста.",
                "tone": "good",
            }
        )
    if other_group_share is not None:
        insights.append(
            {
                "title": "Качество классификации уже можно контролировать",
                "text": f"Группа «Прочее» сейчас забирает {other_group_share}% наблюдаемого спроса. Чем ниже этот показатель, тем точнее market-карта и тем надёжнее выводы по нишам.",
                "tone": "warn" if other_group_share >= 35 else "good",
            }
        )

    entry_now_segments = [row for row in entry_windows if row.get("entry_strategy_bucket") == "enter_now"][:12]
    test_entry_segments = [row for row in entry_windows if row.get("entry_strategy_bucket") in {"test_entry", "validate_economics"}][:12]
    sourcing_or_avoid_segments = [row for row in entry_windows if row.get("entry_strategy_bucket") in {"avoid", "improve_sourcing"}][:12]
    entry_watchlist = entry_now_segments or test_entry_segments or entry_windows[:8]

    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "metadata": metadata,
        "kpis": {
            "total_skus": int(summary.get("observed_products", 0) or 0),
            "sold_skus": int(summary.get("observed_products", 0) or 0),
            "revenue_total": 0.0,
            "gross_profit_total": 0.0,
            "observed_seller_count": int(summary.get("observed_sellers", 0) or 0),
            "observed_group_count": int(summary.get("observed_groups", 0) or 0),
            "stockout_risk_count": int(summary.get("observed_sellers", 0) or 0),
            "stale_stock_count": int(summary.get("observed_groups", 0) or 0),
            "observed_price_bands": int(summary.get("observed_price_bands", 0) or 0),
            "observed_idea_clusters": int(summary.get("observed_idea_clusters", 0) or 0),
            "overall_dominance_hhi": summary.get("overall_dominance_hhi"),
            "novelty_proxy_index": summary.get("novelty_proxy_index"),
            "other_group_share_pct": summary.get("other_group_share_pct"),
            "target_margin_pct": target_margin_pct,
            "economics_coverage_groups_pct": economics_coverage_groups_pct,
            "economics_coverage_windows_pct": economics_coverage_windows_pct,
            "blind_spot_windows_count": len(blind_spots),
            "entry_ready_windows_count": summary.get("entry_ready_windows_count"),
            "test_entry_windows_count": summary.get("test_entry_windows_count"),
            "avoid_windows_count": summary.get("avoid_windows_count"),
        },
        "insights": insights,
        "actions": {
            "entry_watchlist": entry_watchlist,
            "enter_now_segments": entry_now_segments,
            "test_entry_segments": test_entry_segments,
            "sourcing_or_avoid_segments": sourcing_or_avoid_segments,
            "blind_spots": blind_spots,
        },
        "tables": {
            "top_sellers": _top_rows(top_sellers, limit=15),
            "top_products": _top_rows(top_products, limit=15),
            "groups": _top_rows(groups, limit=15),
            "entry_windows": _top_rows(entry_windows, limit=15),
            "idea_clusters": _top_rows(idea_clusters, limit=15),
            "strongest_economic_groups": _top_rows(strongest_economic_groups, limit=12),
        },
        "charts": {
            "price_bands": [
                {"key": row.get("price_band", "н/д"), "value": row.get("orders_sum", 0)}
                for row in price_bands
            ],
            "group_orders": [
                {"key": row.get("group", "н/д"), "value": row.get("orders_sum", 0)}
                for row in groups
            ],
        },
    }
