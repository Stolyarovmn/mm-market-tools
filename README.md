# MM Market Tools

Набор CLI-скриптов для работы с `mm.ru` / `kazanexpress.ru` API.

Проект собран из рабочих исследовательских скриптов и приведён к виду, удобному для человека и для любого AI/LLM-агента:

- понятные CLI-параметры;
- запуск через env-переменные или флаги;
- минимальные внешние зависимости;
- явные ограничения и known issues;
- checkpoint-режим для долгих сборов.

## Содержимое

- `get_sellers.py`
  Основной скрипт. Собирает список продавцов по всем листовым подкатегориям категории MM.
- `collect_sellers.py`
  Вспомогательный скрипт для seller API дерева категорий по bearer token.
- `compare_shops.py`
  Сравнение вашего магазина и конкурента по seller API.
- `analyze_products.py`
  Анализ остатков и продаж одного магазина по seller API.
- `analyze_official_reports.py`
  Анализ официальных seller CSV-отчётов `SELLS_REPORT` и `LEFT_OUT_REPORT`.
- `analyze_variant_families.py`
  Отдельный family-level анализ по `product_id`, `ШК`, `SKU`, чтобы смотреть карточки с вариантами не только по строкам CSV.
- `analyze_competitor_market.py`
  Отдельный модуль рыночного анализа: что продаётся в категории, у каких продавцов, по какой цене, насколько сегмент сконцентрирован вокруг лидеров и насколько категория открыта для новых карточек по proxy-индексу новизны.
- `benchmark_product_cards.py`
  Сравнение карточек ваших товаров с похожими публичными карточками из категории.
- `compare_top_seller_overlaps.py`
  Поиск пересечений между вашими товарами и товарами top-N продавцов категории.
- `analyze_product_ideas.py`
  Группировка всего вашего ассортимента по товарным идеям и сравнение групп с конкурентами.
- `build_growth_plan.py`
  Сборка итогового плана роста из уже готовых отчётов по группам и конкурентам. Теперь учитывает operational window-сигналы, чтобы не путать исторические хиты с текущим спросом.
- `snapshot_shop.py`
  Снятие датированного снапшота ассортимента магазина для анализа по временным окнам.
- `analyze_time_window.py`
  Анализ продаж, остатков и риска out-of-stock по двум снапшотам за реальный период.
- `cubejs_query.py`
  Обёртка для seller-analytics CubeJS запросов по временным окнам.
- `cubejs_period_compare.py`
  Длинные сравнения через CubeJS: trailing year, `YoY`, `3Y`, monthly series.
- `request_document_report.py`
  Создание и получение async-отчётов через seller documents API.
- `weekly_operational_report.py`
  Единый weekly pipeline: запрос официальных seller CSV, скачивание и сборка операционного отчёта.
- `smoke_test_official_pipeline.py`
  Быстрая локальная проверка, что operational pipeline на текущих raw CSV не сломан.
- `smoke_test_market_pipeline.py`
  Быстрая локальная проверка, что market dashboard bundle не сломан.
- `smoke_test_pricing_pipeline.py`
  Быстрая локальная проверка, что dynamic pricing dashboard bundle не сломан.
- `smoke_test_price_trap_report.py`
  Быстрая локальная проверка, что report `price_trap_report` не сломан.
- `smoke_test_title_seo_report.py`
  Быстрая локальная проверка, что report `title_seo_report` не сломан.
- `smoke_test_marketing_card_audit.py`
  Быстрая локальная проверка, что unified manager-facing marketing audit bundle не сломан.
- `smoke_test_media_richness_report.py`
  Быстрая локальная проверка, что media richness dashboard bundle не сломан.
- `smoke_test_description_seo_richness_report.py`
  Быстрая локальная проверка, что description SEO richness dashboard bundle не сломан.
- `smoke_test_entity_history_index.py`
  Быстрая локальная проверка, что индекс истории сущностей для detail-panel не сломан.
- `refresh_operational_dashboard.py`
  Локальная пересборка operational dashboard из уже скачанных raw CSV и metadata, без новых запросов в seller API.
- `build_zero_cogs_registry.py`
  Реестр конкретных SKU с `cogs = 0` в приоритетных blind-spot группах.
- `export_cogs_fill_template.py`
  CSV-шаблон для ручного заполнения себестоимости по SKU.
- `ingest_cogs_fill.py`
  Импортирует заполненный COGS CSV в постоянное локальное хранилище `data/local/cogs_overrides.json`.
- `rescore_market_after_cogs_fill.py`
  Разовый пересчёт market fit после заполнения COGS.
- `run_cogs_backfill_cycle.py`
  Единый persistent pipeline: import overrides -> rebuild zero COGS registry -> export new template -> rescore market.
- `validate_token_integrations.py`
  Проверка всех основных точек взаимодействия на новом token.
- `build_dashboard_index.py`
  Индексирует `data/dashboard/*.json` для браузерного интерфейса. Держит dual contract `items` + `reports`, чтобы UI и audit/test-слой не расходились по формату. Заодно пересобирает `data/local/entity_history_index.json` для detail-panel по сущностям.
- `migrate_dashboard_schema.py`
  Проставляет `schema_version` в старые dashboard bundles.
- `build_dynamic_pricing_report.py`
  Recommendation-first отчёт по безопасным ценовым предложениям на основе market/economics слоя. Теперь поднимается и в `data/dashboard/` как отдельный report kind `dynamic_pricing`.
- `build_price_trap_report.py`
  Marketing-аудит SKU, которые стоят чуть выше психологических ценовых порогов и могут терять видимость в фильтрах.
- `build_title_seo_report.py`
  SEO-аудит title: вынесены ли главный noun и важный entity/character/brand в начало названия.
- `build_marketing_card_audit.py`
  Единый manager-facing marketing audit: объединяет `dynamic_pricing`, `price_trap` и `title_seo` в один dashboard/report слой по карточкам.
- `build_media_richness_report.py`
  Audit по фото, видео и характеристикам карточек: ищет visual gaps и слабый media-layer относительно своей группы.
- `build_description_seo_richness_report.py`
  Audit по description-layer: thin content, длина описания, покрытие title-термов и отставание от медианы группы.
- `build_entity_history_index.py`
  Пересобирает локальный индекс истории сущностей для dashboard detail-panel.
- `ui/`
  Статический браузерный интерфейс поверх `data/dashboard/index.json`. Начато безопасное разбиение UI-кода на ES-модули: API-слой вынесен в `ui/api.js`, state/theme/report-selection слой в `ui/state.js`, report-kind/view логика частично вынесена в `ui/dashboard_views.js`, generic UI-компоненты вынесены в `ui/components.js`.
- `web_refresh_server.py`
  Локальный web-runner для ручного запуска online/offline jobs через браузер, когда прямой доступ к MM из основной рабочей сессии ограничен.
  Среди offline jobs теперь есть и `marketing_card_audit`, так что новый manager-facing marketing слой можно пересобирать без ручного CLI.
  Action Center внутри runner теперь хранит не только watchlist и задачи, но и entity-level acknowledgements по карточкам.
- `start_dashboard_ui.sh`
  Короткий запуск основного dashboard UI на `:8000` через `web_refresh_server.py`, то есть вместе с локальным `/api` для Action Center и detail-panel.
- `start_refresh_ui.sh`
  Короткий запуск refresh runner UI на `:8040` на том же backend-контракте.
- `core/`
  Общее ядро проекта: пути, I/O helpers, HTTP/auth слой, documents API, CubeJS и парсинг official reports.
  Теперь сюда же вынесен общий content/cache слой для public product content карточек.
- `METHODOLOGY.md`
  Принципы и формулы, на которых должна строиться аналитика проекта.
- `CHANGELOG.md`
  История изменений, исправленных ошибок и важных методологических выводов. Ведётся по `Keep a Changelog` и `SemVer`: каждая итерация должна сначала попадать в `Unreleased`, а затем в versioned section.
- `ROADMAP.md`
  Актуальный план развития проекта и приоритеты по слоям.
- `requirements.txt`
  Минимальные Python-зависимости.
- `.env.example`
  Шаблон переменных окружения.

## Быстрый старт

### 1. Требования

- Python 3.10+
- доступ в интернет
- bearer token для seller API, если вы используете `collect_sellers.py`, `compare_shops.py` или `analyze_products.py`

### 2. Установка зависимостей

```bash
cd /path/to/mm-market-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Настройка переменных окружения

Вариант через shell:

```bash
export KAZANEXPRESS_TOKEN='...'
export MM_MY_SHOP_ID=98
export MM_COMPETITOR_SHOP_ID=40319
```

Или используйте значения из `.env.example` как шаблон.

## Основной workflow

### A. Собрать всех продавцов по категории MM

Пример для категории `Игрушки и игры`:

```bash
python3 get_sellers.py --category-id 10162 --page-size 50 --progress --output reports/mm_sellers_10162.json
```

Что делает скрипт:

1. Загружает дерево категорий через `https://api.kazanexpress.ru/api/category/v2/root-categories`.
2. Находит целевую категорию и все её листовые подкатегории.
3. По каждой листовой подкатегории делает поиск товаров через `https://web-api.mm.ru/v2/goods/search`.
4. Преобразует `storeCode` товара в продавца.
5. Для новых продавцов запрашивает карточку товара через `https://api.kazanexpress.ru/api/v2/product/{id}` и извлекает `seller`.
6. Если категория слишком большая и API режет `offset`, скрипт автоматически дробит выборку по цене.
7. После каждой листовой подкатегории сохраняет checkpoint прямо в output JSON.
8. Собирает по каждой листовой подкатегории ценовую сводку: `avg_price`, `median_price`, `min_price`, `max_price`, `orders_sum`.
9. Использует централизованный retry/backoff через `core/http_client.py`, чтобы не размазывать сетевую логику по скриптам.

### Почему output можно запускать повторно

`get_sellers.py` умеет возобновляться из уже существующего output-файла:

- читает `completed_leaf_category_ids`;
- не трогает уже завершённые листовые подкатегории;
- продолжает сбор с оставшихся.

Это важно для долгих прогонов и для запуска под контролем AI-агента.

### Формат результата `get_sellers.py`

JSON содержит:

- `category`
- `leaf_categories_count`
- `visited_products`
- `completed_leaf_category_ids`
- `truncated_segments`
- `leaf_category_stats`
- `sellers`

Каждый seller:

```json
{
  "id": 16685,
  "title": "Магазин детских товаров Ассорти",
  "link": "assorty",
  "products_seen": 822
}
```

### Ограничения `get_sellers.py`

- API `web-api.mm.ru/v2/goods/search` имеет жёсткие ограничения на `offset`.
- дефолтный `--sleep` теперь не нулевой, чтобы не долбить API слишком агрессивно;
- на `403/429/5xx` добавлен retry с экспоненциальной задержкой;
- Для больших подкатегорий скрипт уже умеет дробить выборку по цене.
- `truncated_segments` в output означает, что API всё ещё не дал полностью разобрать отдельные сегменты автоматически.
- Если `truncated_segments` пустой, сбор завершён полностью в рамках реализованной логики.

## Вспомогательные скрипты

### `core/auth.py` и `core/http_client.py`

Назначение:

- единая точка для `access_token`;
- единые bearer headers;
- единый HTTP session / retry / backoff / MM public headers.

Что это даёт:

- меньше дублирования в `documents`, `CubeJS`, `market` и seller-скриптах;
- меньше риска, что разные модули начнут ходить в MM с разными заголовками и разной retry-логикой;
- проще развивать проект дальше, не размазывая сетевой контракт по десятку CLI-скриптов.
- `core/auth.py` теперь также делает proactive `JWT expiration guard`:
  - expired token роняет запуск до сетевого вызова;
  - token, который вот-вот истечёт, даёт явное предупреждение;
  - полноценный auto-refresh не обещается без подтверждённого refresh-flow.

### `collect_sellers.py`

Назначение:

- получить дерево категорий seller API;
- найти категорию;
- вывести листовые category ID.

Запуск:

```bash
python3 collect_sellers.py --category-id 10162
```

Требует:

- `KAZANEXPRESS_TOKEN`

Важно:

- seller API маршрут может меняться;
- если получите `404`, значит endpoint устарел;
- если получите `401`, значит токен истёк.

### `compare_shops.py`

Назначение:

- сравнить товары вашего магазина и магазина конкурента;
- найти точные пересечения по title;
- показать товары конкурента с продажами `quantitySold > 100`, которых нет у вас.

Запуск:

```bash
python3 compare_shops.py --my-shop-id 98 --competitor-shop-id 40319 --my-pages 9 --competitor-pages 5
```

Требует:

- `KAZANEXPRESS_TOKEN`

Замечание:

- сравнение по title упрощённое;
- разные названия одного и того же товара считаться совпадением не будут.

### `analyze_products.py`

Назначение:

- выделить:
  - хиты, которых нет в остатке;
  - мёртвый склад;
  - критически низкие остатки.

Запуск:

```bash
python3 analyze_products.py --shop-id 98 --pages 9
```

Требует:

- `KAZANEXPRESS_TOKEN`

Статус:

- `legacy heuristic`

Важно:

- скрипт использует накопительные продажи;
- не должен быть основным инструментом для оперативных решений по заказу и текущему спросу.

### `analyze_official_reports.py`

Назначение:

- объединить `SELLS_REPORT` и `LEFT_OUT_REPORT`;
- выделить:
  - текущие продажи за период;
  - лидеров по прибыли;
  - риск out-of-stock;
  - залежавшийся остаток;
  - ABC-классы по выручке и прибыли;
  - family-level слой по карточкам с несколькими вариантами и ШК.

Пример:

```bash
python3 analyze_official_reports.py \
  --sells-report /path/to/sells-report.csv \
  --left-out-report /path/to/left-out-report.csv
```

Можно передавать и прямые URL на CSV.

Выходные файлы:

- `reports/official_period_analysis_<YYYY-MM-DD>.json`
- `reports/official_period_analysis_<YYYY-MM-DD>.csv`
- `reports/official_period_analysis_<YYYY-MM-DD>.md`
- `data/normalized/official_period_analysis_<YYYY-MM-DD>.json`
- `data/dashboard/official_period_analysis_<YYYY-MM-DD>.json`

Что добавилось:

- `LEFT_OUT_REPORT` теперь используется не только для остатков, но и для identity слоя:
  - `Штрихкод`
  - `ID товара`
  - `Seller SKU ID`
- operational summary теперь считает и семейства товаров (`family_rows`);
- dashboard получает `family_tables`, чтобы в UI было видно:
  - какие карточки живут как семейство;
  - где много вариантов и ШК;
  - где смотреть надо не на строку, а на карточку целиком.

### `analyze_variant_families.py`

Назначение:

- отдельно разобрать seller reports на уровне семейств товара;
- сгруппировать варианты по `product_id`, а внутри карточки опираться на `ШК` / `Seller SKU ID` / `SKU`;
- показать, где проблема в конкретном варианте, а где в карточке целиком.

Запуск:

```bash
python3 analyze_variant_families.py \
  --sells-report /path/to/sells-report.csv \
  --left-out-report /path/to/left-out-report.csv
```

Выходные файлы:

- `reports/variant_family_analysis_<YYYY-MM-DD>.json`
- `reports/variant_family_analysis_<YYYY-MM-DD>.csv`
- `reports/variant_family_analysis_<YYYY-MM-DD>.md`

- `data/normalized/*` это нормализованный слой для последующей автоматической обработки;
- `data/dashboard/*` это UI-ready JSON для будущего браузерного интерфейса:
  - KPI
  - таблицы
  - ABC-распределения
  - action lists (`reorder_now`, `markdown_candidates`, `protect_winners`)

Важно:

- этот слой теперь специально строже по сигналам;
- товар с `1-2` продажами за окно не считается автоматическим "победителем";
- нулевые продажи за окно не попадают в блок "что уверенно продаётся сейчас", даже если есть сильный исторический след в других полях;
- это сделано именно для того, чтобы не рекомендовать закупку по шумным или устаревшим сигналам.

### `weekly_operational_report.py`

Назначение:

- автоматически запросить:
  - `SELLS_REPORT`
  - `LEFT_OUT_REPORT`
- скачать CSV;
- собрать единый операционный отчёт по продажам, прибыли, stock risk и stale stock.
- если `documents/create` отвечает `400 Validation failed`, попытаться переиспользовать уже готовые matching reports из `documents/requests`.

Это основной кандидат на роль будущего backend-пайплайна для браузерного интерфейса.

Пример:

```bash
python3 weekly_operational_report.py \
  --token "$KAZANEXPRESS_TOKEN" \
  --window-days 7
```

Или с явным окном:

```bash
python3 weekly_operational_report.py \
  --token "$KAZANEXPRESS_TOKEN" \
  --date-from 2026-04-02T00:00:00 \
  --date-to 2026-04-08T23:59:59
```

Выходные файлы:

- `data/raw_reports/*.csv`
- `data/normalized/weekly_operational_report_<YYYY-MM-DD>.json`
- `data/dashboard/weekly_operational_report_<YYYY-MM-DD>.json`
- `reports/weekly_operational_report_<YYYY-MM-DD>.json`
- `reports/weekly_operational_report_<YYYY-MM-DD>.csv`
- `reports/weekly_operational_report_<YYYY-MM-DD>.md`

Примечание:

- режим `reused` полезен, когда seller UI уже успел создать нужные official reports, но прямой `POST /documents/create` с bearer token не проходит;
- это делает pipeline устойчивее в реальной работе и снижает зависимость от нестабильной серверной валидации.

### `smoke_test_official_pipeline.py`

Назначение:

- быстро проверить, что парсинг official CSV, merge, summary и dashboard слой не сломаны.

Пример:

```bash
python3 smoke_test_official_pipeline.py
```

Ожидаемый результат:

- вывод `SMOKE_OK`
- непустые `rows`
- непустой `sold_skus`

### `build_dashboard_index.py`

Назначение:

- собрать единый индекс dashboard-отчётов для UI;
- отметить latest report и latest-by-kind;
- добавлять `schema_version` и change-summary относительно предыдущего отчёта того же вида;
- подготовить проект к накоплению истории weekly окон.

Пример:

```bash
python3 build_dashboard_index.py
```

Выходной файл:

- `data/dashboard/index.json`

Примечание:

- индекс сейчас специально содержит и `items`, и `reports` как alias одного и того же списка;
- это нужно, чтобы основной UI, audit-скрипты и тестовые проверки не расходились по контракту.

### `migrate_dashboard_schema.py`

Назначение:

- дописать `schema_version` в старые dashboard bundles;
- выровнять уже накопленные JSON до текущего dashboard contract.

Пример:

```bash
python3 migrate_dashboard_schema.py
```

### `ui/`

Назначение:

- дать интерактивный просмотр KPI, action lists, таблиц и ABC-распределений без отдельного frontend-фреймворка;
- читать уже готовые файлы из `data/dashboard`.

Как открыть локально:

```bash
cd /path/to/mm-market-tools
bash ./start_dashboard_ui.sh
```

После этого открыть:

- `http://127.0.0.1:8000/`
- ???????????? ???????? ????????? ????? ? `ui/index.html` ? ?????? ?? ??????????? ?? ???????? `/`.

Что уже умеет UI:

- переключение между dashboard-отчётами;
- переключение светлой и тёмной темы;
- блок `Что изменилось`:
  - сравнивает текущий отчёт с предыдущим того же типа;
  - показывает главные числовые сдвиги, а не только очередной snapshot;
- `i`-подсказки по KPI, таблицам и ключевым блокам;
- tooltip-подсказки скрыты по умолчанию и открываются по наведению, фокусу или нажатию;
- показ KPI по окну;
- списки `reorder_now`, `markdown_candidates`, `protect_winners`;
- таблицы текущих победителей, profit leaders, stock risk, stale stock;
- интерпретируемый `ABC`:
  - доля SKU по A/B/C
  - доля выручки или прибыли по A/B/C
  - конкретные SKU внутри зон A/B/C по выручке и прибыли
  - краткие правила, как это применять в работе
- strict operational режимы теперь не проваливаются в пустоту:
  - если нет strict winners, UI показывает `слабые, но живые сигналы`
  - то же правило работает для family-level блока
- metadata в `official`-отчётах показываются в коротком виде:
  - вместо длинных путей и URL UI показывает короткий источник
  - полный путь или URL раскрывается через `i`
  - строки `Запрос продаж` и `Запрос остатков` скрываются, если request id реально отсутствует
- блок `Автоматические выводы по окну` теперь строится менее шаблонно:
  - отдельно про жёсткие сигналы на дозакупку
  - отдельно про мягкие сигналы
  - отдельно про затоваривание
  - отдельно про семейства товаров и multi-variant карточки
- базовые распределения по статусам.
- family-level таблицы для multi-variant карточек и `ШК`.
- action center:
  - сохранённый watchlist;
  - ручные задачи менеджера;
  - owner у задач и расширенные статусы;
  - saved views по фильтрам задач;
  - быстрые кнопки `В список` и `Задача` прямо из operational и market-таблиц;
- отдельный market-режим:
  - топ продавцы
  - топ товары рынка
  - сильнейшие группы
  - ценовые коридоры
  - idea clusters
  - доля лидера и признак концентрации сегмента
- отдельный compare-режим для `cubejs_period_compare`:
  - trailing year cards
  - `YTD` vs previous `YTD`
  - `YoY` и `3Y` compare cards

### `web_refresh_server.py`

Назначение:

- дать отдельный локальный web-интерфейс для online refresh, когда прямой доступ к MM из основной рабочей сессии ограничен;
- запускать jobs вручную из браузера;
- видеть статус, live log и историю последних запусков;
- видеть артефакты, которые job сохранил (`Saved: ...`);
- отдавать локальный action-center API для main dashboard UI;
- не сохранять `access_token` в логах и status JSON.

Как открыть локально:

```bash
cd /path/to/mm-market-tools
python3 web_refresh_server.py --host 127.0.0.1 --port 8040
```

Или короче:

```bash
bash ./start_refresh_ui.sh
```

После этого открыть:

- `http://127.0.0.1:8040/` ??? ????????? UI (`ui/index.html`)
- `http://127.0.0.1:8040/refresh.html` ??? runner/runtime-????????
- после изменения backend/frontend кода перезапускай `web_refresh_server.py`, иначе браузер останется на старом контракте.

Текущая схема работы:

1. Я вношу изменения и говорю, какой refresh нужен.
2. Открываешь `refresh.html` из подходящей сетевой сессии.
3. Запускаешь нужный `online` job.
4. Ждёшь статус `succeeded`.
5. Возвращаешься к обычной работе со мной и продолжаешь анализ.

Что уже умеет refresh UI:

- список `online` и `offline` jobs;
- форма параметров для каждого job;
- live status;
- live log;
- история последних запусков;
- сохранение логов и status-файлов в `data/job_runs/`;
- показ артефактов, которые job реально сохранил;
- локальный API для `Action Center`.
- среди offline jobs теперь есть и `dynamic_pricing`, так что repricer-рекомендации можно пересобирать без ручного CLI.

Важно:

- если `web_refresh_server.py` был уже запущен до обновления кода проекта, его нужно перезапустить, иначе браузер может видеть старый набор API endpoint’ов.
- main dashboard теперь пытается достучаться до runner не только через `127.0.0.1`, но и через текущий hostname / `localhost`, чтобы уменьшить ложные `Failed to fetch`.

### `build_dynamic_pricing_report.py`

Назначение:

- сделать первый шаг к repricer-модулю;
- не менять цену автоматически, а рекомендовать безопасный ценовой уровень;
- учитывать:
  - `avg_market_price`
  - `my_avg_cogs`
  - `target_margin_pct`
  - `market_margin_fit_pct`

Пример:

```bash
python3 build_dynamic_pricing_report.py
```

Выход:

- `reports/dynamic_pricing_<YYYY-MM-DD>.json`
- `reports/dynamic_pricing_<YYYY-MM-DD>.md`
- `data/dashboard/dynamic_pricing_<YYYY-MM-DD>.json`

Важно:

- это recommendation-first слой;
- auto-apply pricing пока сознательно не делается.
- его можно смотреть прямо в основном dashboard UI как отдельный тип отчёта.

### `build_price_trap_report.py`

Назначение:

- найти SKU, которые стоят чуть выше психологических порогов вроде `199`, `299`, `499`, `999`;
- собрать shortlist для ручного price test;
- не менять цены автоматически, а подсказать, где фильтровая видимость может страдать из-за лишних `5-15 ₽`.

Пример:

```bash
python3 build_price_trap_report.py
```

Выход:

- `reports/price_trap_report_<YYYY-MM-DD>.json`
- `reports/price_trap_report_<YYYY-MM-DD>.md`

Важно:

- это marketing-аудит, а не автоматический repricer;
- сейчас он работает по локальным normalized operational rows, то есть по вашему ассортименту и текущим ценам.

Проверка:

```bash
python3 smoke_test_price_trap_report.py
```

### `build_title_seo_report.py`

Назначение:

- проверить, вынесены ли главный тип товара и важный entity/character/brand в первые слова title;
- найти title с weak/generic lead;
- собрать shortlist карточек, где title может мешать CTR и поисковой видимости.

Пример:

```bash
python3 build_title_seo_report.py
```

Выход:

- `reports/title_seo_report_<YYYY-MM-DD>.json`
- `reports/title_seo_report_<YYYY-MM-DD>.md`

Важно:

- это эвристический audit-layer, а не настоящий поисковый ранжировщик MM;
- сейчас он работает по локальным normalized operational rows вашего магазина;
- полезен как shortlist на ручную перепаковку title, а не как автоматический rewrite.

Проверка:

```bash
python3 smoke_test_title_seo_report.py
```

### `benchmark_product_cards.py`

Назначение:

- взять ваши сильные SKU;
- найти в публичном каталоге похожие карточки;
- сравнить заполненность карточек и базовые рыночные сигналы:
  - продажи;
  - рейтинг и отзывы;
  - длину описания;
  - число фото;
  - атрибуты;
  - характеристики.

Скрипт умеет работать в двух режимах:

- по живому seller token;
- по уже сохранённому CSV `reports/my_shop_top_products.csv`, если token истёк.

Запуск с token:

```bash
python3 benchmark_product_cards.py --token "$KAZANEXPRESS_TOKEN" --sample-size 5 --comparables 4
```

Запуск без token, от кэша:

```bash
python3 benchmark_product_cards.py --sample-size 5 --comparables 4
```

Выходные файлы:

- `reports/product_card_benchmark_<YYYY-MM-DD>.json`
- `reports/product_card_benchmark_<YYYY-MM-DD>.md`

Практический смысл:

- быстро понять, слабее ли ваши карточки по контенту;
- отделить проблему карточки от проблемы цены, остатков, отзывов или продвижения;
- собирать примеры для улучшения уже существующих SKU.

### `compare_top_seller_overlaps.py`

Назначение:

- взять top-N продавцов категории;
- найти пересечения или близкие товары относительно ваших SKU;
- сравнить цены, продажи и базовую полноту карточки.

Скрипт умеет:

- работать от живого seller token или от кэша `reports/my_shop_top_products.csv`;
- искать пересечения от ваших SKU наружу, а не только по полному обходу категории;
- ослаблять критерий совпадения через `--min-similarity`.

Пример:

```bash
python3 compare_top_seller_overlaps.py --sample-size 40 --top-n 10 --min-similarity 0.5
```

Выходные файлы:

- `reports/top10_overlap_report_<YYYY-MM-DD>.json`
- `reports/top10_overlap_report_<YYYY-MM-DD>.md`
- `reports/top10_overlap_report_<YYYY-MM-DD>.csv`

Интерпретация:

- пустой отчёт тоже полезен: это значит, что top-N продавцы категории в основном работают в другом ассортиментном кластере и не являются прямыми SKU-конкурентами;
- для поиска более прикладных конкурентов стоит опускаться ниже top-10 к продавцам с более похожим ассортиментом.

### `analyze_product_ideas.py`

Назначение:

- разобрать весь ваш ассортимент на группы по товарным идеям;
- выделить сильнейшие группы по числу SKU и продажам;
- сравнить эти группы:
  - с top-10 продавцов категории;
  - с выбранными ассортиментными конкурентами.

Скрипт не требует живого seller token, если уже есть `reports/my_shop_top_products.csv`.

Пример:

```bash
python3 analyze_product_ideas.py --group-representatives 4 --min-similarity 0.22
```

Выходные файлы:

- `reports/my_product_groups_<YYYY-MM-DD>.json`
- `reports/my_product_groups_<YYYY-MM-DD>.csv`
- `reports/my_product_groups_<YYYY-MM-DD>.md`
- `reports/idea_competitor_comparison_top10_<YYYY-MM-DD>.json`
- `reports/idea_competitor_comparison_top10_<YYYY-MM-DD>.md`
- `reports/idea_competitor_comparison_real_<YYYY-MM-DD>.json`
- `reports/idea_competitor_comparison_real_<YYYY-MM-DD>.md`

Практический смысл:

- понять, какие группы реально двигают магазин;
- увидеть, где top-10 вообще не являются прямыми конкурентами;
- выделить более прикладных ассортиментных конкурентов по конкретным идеям товаров.

### `build_growth_plan.py`

Назначение:

- собрать в один отчёт:
  - какие группы расширять;
  - какие ценовые диапазоны усиливать;
  - какие линейки углублять;
  - какие хиты теряются из-за отсутствия в наличии;
  - где у конкурентов идея уже имеет рыночный сигнал.

Скрипт работает только по уже сохранённым датированным отчётам и не требует сети.

Пример:

```bash
python3 build_growth_plan.py
```

Выходные файлы:

- `reports/growth_plan_<YYYY-MM-DD>.json`
- `reports/growth_plan_<YYYY-MM-DD>.md`

### `snapshot_shop.py`

Назначение:

- сохранить состояние магазина на конкретную дату;
- создать базу для анализа `7/14/30` дней;
- уйти от ошибки "старые накопительные продажи выглядят как текущие".

Пример:

```bash
python3 snapshot_shop.py --token "$KAZANEXPRESS_TOKEN"
```

Выходные файлы:

- `data/snapshots/shop_<SHOP_ID>_<YYYY-MM-DD>.json`
- `data/snapshots/shop_<SHOP_ID>_<YYYY-MM-DD>.csv`

### `analyze_time_window.py`

Назначение:

- сравнить два снапшота;
- посчитать продажи за окно времени;
- выделить:
  - текущие бестселлеры;
  - риск out-of-stock;
  - зависший ассортимент.

Пример:

```bash
python3 analyze_time_window.py \
  --start-snapshot data/snapshots/shop_98_2026-04-01.json \
  --end-snapshot data/snapshots/shop_98_2026-04-08.json
```

Выходные файлы:

- `reports/time_window_analysis_<YYYY-MM-DD>.json`
- `reports/time_window_analysis_<YYYY-MM-DD>.csv`
- `reports/time_window_analysis_<YYYY-MM-DD>.md`

### `cubejs_query.py`

Назначение:

- выполнять запросы к `seller-analytics.mm.ru/cubejs-api/v1/load`;
- получать метрики сразу в рамках временного окна;
- использовать `shop_id`, `timeDimensions`, `dateRange`, `measures`, `dimensions`.

Подходит для:

- дневной/недельной/месячной выручки;
- временных рядов;
- более академичного анализа текущей динамики.

Пример:

```bash
python3 cubejs_query.py \
  --cookie "$MM_ANALYTICS_COOKIE" \
  --shop-id 98 \
  --measures Sales.seller_revenue_without_delivery_measure \
  --date-range "last 7 days" \
  --granularity day
```

Выходные файлы:

- `reports/cubejs_query_<YYYY-MM-DD>.json`
- `reports/cubejs_query_<YYYY-MM-DD>.csv`

Важно:

- с новым token сначала стоит прогонять `validate_token_integrations.py`;
- у CubeJS меры не всегда совместимы в одном query;
- в текущем проекте подтверждённо работает схема:
  - `Sales.seller_revenue_without_delivery_measure` отдельно
  - `Sales.orders_number` + `Sales.item_sold_number` вместе
- `Sales.seller_profit` сейчас возвращает `400` и не должен считаться стабильным источником.

### `cubejs_period_compare.py`

Назначение:

- строить long-range аналитику до `3` лет глубины;
- сравнивать:
  - trailing `365` days
  - same window previous year
  - same window `3` years ago
  - current `YTD` vs previous `YTD`
- сохранять monthly time series для UI и дальнейшего анализа.

Пример:

```bash
python3 cubejs_period_compare.py \
  --token "$KAZANEXPRESS_TOKEN" \
  --history-years 3
```

Выходные файлы:

- `reports/cubejs_period_compare_<YYYY-MM-DD>.json`
- `reports/cubejs_period_compare_<YYYY-MM-DD>.csv`
- `reports/cubejs_period_compare_<YYYY-MM-DD>.md`
- `data/normalized/cubejs_period_compare_<YYYY-MM-DD>.json`
- `data/dashboard/cubejs_period_compare_<YYYY-MM-DD>.json`

Практический смысл:

- отличать текущий год от прошлого не по ощущениям, а по временным окнам;
- видеть, есть ли реальная глубина данных для `YoY` и `3Y`;
- готовить историю для браузерных графиков.

### `validate_token_integrations.py`

Назначение:

- всегда проверять новый token по всем основным интеграциям проекта.

Что проверяет:

- `CubeJS meta`
- `CubeJS load`
- `documents/requests`
- `documents/create`

Пример:

```bash
python3 validate_token_integrations.py --token "$KAZANEXPRESS_TOKEN"
```

Выходной файл:

- `reports/token_validation_<YYYY-MM-DD>.json`

### `analyze_competitor_market.py`

Что считает дополнительно:

- `leading_seller_share_pct`
- `dominance_hhi`
- `competition_profile`
- `novelty_proxy_index`
- `fresh_top_product_share_pct`
- `other_group_share_pct`
- `market_margin_fit_pct`
- `margin_vs_target_pct`
- `entry_strategy_label`
- `entry_strategy_reason`

Как читать эти поля:

- `dominance_hhi < 1500`:
  обычно это более раздробленный сегмент, куда легче заходить новому магазину.
- `dominance_hhi 1500-2500`:
  умеренная концентрация, вход возможен, но уже нужен более сильный оффер.
- `dominance_hhi > 2500`:
  сегмент плотный, лучше заходить точечно и через сильный контент/цену/наличие.
- `novelty_proxy_index`:
  это не реальный возраст карточек, а proxy по связке `orders/reviews`. Он показывает, насколько в топе видны относительно “свежие” товары с ещё не накопленным review-weight.
- `other_group_share_pct`:
  доля спроса, попавшая в `Прочее`. Чем она ниже, тем надёжнее market-классификация.
- `entry_windows`:
  сочетания `группа + ценовой коридор`, где можно искать более прикладные окна входа, а не смотреть только на широкую группу целиком.
- `market_margin_fit_pct`:
  насколько рыночная цена в группе или окне входа вообще совместима с вашей текущей себестоимостью.
- `margin_vs_target_pct`:
  зазор до вашей целевой маржи. Отрицательное значение означает, что рынок уже давит ниже желаемой экономики.
- `entry_strategy_label`:
  готовое решение по окну входа: `входить`, `тестировать`, `наблюдать`, `не входить`, `сначала улучшить закупку`.
- `blind_spot_windows_count`:
  сколько окон уже выглядят интересными по спросу, но ещё не покрыты вашими cost-данными. Это нельзя читать как зелёный сигнал на вход, пока не подтверждена экономика.

### `build_growth_plan.py`

Что изменилось по методологии:

- historical продажи больше не читаются в отрыве от текущего operational окна;
- если доступен operational dashboard bundle, скрипт добавляет:
  - `window_status`
  - `growth_score`
  - разметку `живой текущий сигнал / ранний сигнал / риск залеживания / исторический сигнал без текущего подтверждения`

Это нужно, чтобы не советовать расширять направление только потому, что оно хорошо продавалось давно.

Назначение:

- собрать отдельный рыночный срез по категории;
- показать:
  - что продаётся;
  - у каких продавцов;
  - по какой цене;
  - в каких товарных группах рынок сильнее всего;
- показать ценовые коридоры и кластеры товарных идей в наблюдаемой выборке;
- оценить концентрацию сегмента:
  - долю лидера в группе
  - общий `dominance / HHI` сигнал
  - профиль `сегмент раздроблен / концентрированный / контролируется лидером`
- сравнить ваши средние цены по группам с наблюдаемым рынком.

Пример:

```bash
python3 analyze_competitor_market.py --pages 8 --page-size 50 --target-margin-pct 35
```

Выходные файлы:

- `reports/competitor_market_analysis_<YYYY-MM-DD>.json`
- `reports/competitor_market_analysis_<YYYY-MM-DD>.md`
- `reports/competitor_market_groups_<YYYY-MM-DD>.csv`
- `data/normalized/competitor_market_analysis_<YYYY-MM-DD>.json`
- `data/dashboard/competitor_market_analysis_<YYYY-MM-DD>.json`

Важно:

- идентификация товаров в этом модуле идёт по `product_id` и `seller_id`, а не только по title;
- title всё ещё используется для `idea_clusters`, значит это уже лучше, чем "сравнение только по названию", но не идеальная SKU-нормализация;
- модуль отвечает именно на вопрос рынка: "что продаётся и по какой цене", а не на вопрос ваших остатков.
- market report теперь поднимается в `data/dashboard`, поэтому его можно смотреть прямо в браузерном UI.
- `target-margin-pct` нужен, чтобы сразу отделять окна, где проблема в спросе, от окон, где проблема в вашей экономике.

### `build_market_margin_fit_report.py`

Назначение:

- собрать decision-oriented shortlist поверх уже готового market bundle;
- разложить подниши на:
  - `входить первым`
  - `тестировать точечно`
  - `не входить или менять закупку`
  - `слепые зоны по экономике`

Пример:

```bash
python3 build_market_margin_fit_report.py \
  --input-json data/normalized/competitor_market_analysis_2026-04-09g.json
```

Выходные файлы:

- `reports/market_margin_fit_<YYYY-MM-DD>.json`
- `reports/market_margin_fit_<YYYY-MM-DD>.md`

### `build_cost_coverage_backlog.py`

Назначение:

- собрать backlog по группам и окнам входа, где рынок уже выглядит живым, но ваша экономика ещё слепа;
- отделить:
  - `missing_cogs` — ассортимент в группе у вас уже есть, но нет cost-покрытия;
  - `no_assortment_reference` — нет даже опорного ассортимента для честной оценки экономики.

Пример:

```bash
python3 build_cost_coverage_backlog.py \
  --input-json data/normalized/competitor_market_analysis_2026-04-09g.json
```

Выходные файлы:

- `reports/cost_coverage_backlog_<YYYY-MM-DD>.json`
- `reports/cost_coverage_backlog_<YYYY-MM-DD>.md`

Практический смысл:

- это не отчёт “что продавать”, а список, где сначала нужно дозаполнить себестоимость;
- если группа попала сюда с высоким `priority`, не надо принимать go/no-go решение по ней вслепую.

### `build_zero_cogs_registry.py`

Назначение:

- взять приоритетные blind-spot группы и разложить их на конкретные SKU с нулевой себестоимостью;
- показать, где именно в official rows `cogs = 0`, чтобы это можно было чинить предметно;
- не включать SKU, которые уже закрыты через persistent override store.

Выходные файлы:

- `reports/zero_cogs_registry_<YYYY-MM-DD>.json`
- `reports/zero_cogs_registry_<YYYY-MM-DD>.md`

### `export_cogs_fill_template.py`

Назначение:

- выгрузить CSV-шаблон для ручного заполнения себестоимости по SKU из `zero_cogs_registry`.

Выходной файл:

- `reports/cogs_fill_template_<YYYY-MM-DD>.csv`

### `ingest_cogs_fill.py`

Назначение:

- взять заполненный CSV-шаблон;
- импортировать заполненные `fill_cogs` в локальное постоянное хранилище;
- сохранить ручную добивку себестоимости между итерациями.

Выходной файл:

- `data/local/cogs_overrides.json`

### Практический workflow по себестоимости

1. Собрать market scan.
2. Построить `market_margin_fit`.
3. Построить `cost_coverage_backlog`.
4. Построить `zero_cogs_registry`.
5. Заполнить `cogs_fill_template`.
6. Импортировать заполненный CSV в persistent store.
7. Повторно пересчитать market/economics отчёты.

Пример:

```bash
python3 ingest_cogs_fill.py --fill-csv /path/to/filled_cogs.csv
```

### `rescore_market_after_cogs_fill.py`

Назначение:

- взять существующий market bundle;
- подмешать заполненные `fill_cogs` из CSV;
- автоматически пересчитать:
  - `market_margin_fit`
  - `entry_strategy`
  - coverage экономики

Выходные файлы:

- `reports/market_rescored_after_cogs_<YYYY-MM-DD>.json`
- `reports/market_rescored_after_cogs_<YYYY-MM-DD>.md`
- `data/normalized/market_rescored_after_cogs_<YYYY-MM-DD>.json`
- `data/dashboard/market_rescored_after_cogs_<YYYY-MM-DD>.json`

Практический смысл:

- это уже не diagnostic-only шаг;
- после заполнения себестоимости можно сразу увидеть, какие окна переходят из `validate_economics` в `enter_now` или `test_entry`.

### `run_cogs_backfill_cycle.py`

Назначение:

- объединить постоянный COGS store и текущий fill CSV;
- пересобрать `zero_cogs_registry` и новый `cogs_fill_template`;
- сразу выпустить новый `market_rescored_after_cogs` bundle.

Выходные файлы:

- `reports/cogs_backfill_cycle_<YYYY-MM-DD>.md`
- `reports/zero_cogs_registry_<YYYY-MM-DD>.json`
- `reports/zero_cogs_registry_<YYYY-MM-DD>.md`
- `reports/cogs_fill_template_<YYYY-MM-DD>.csv`
- `reports/market_rescored_after_cogs_<YYYY-MM-DD>.json`
- `reports/market_rescored_after_cogs_<YYYY-MM-DD>.md`
- `data/dashboard/market_rescored_after_cogs_<YYYY-MM-DD>.json`

Пример:

```bash
python3 run_cogs_backfill_cycle.py --fill-csv /path/to/filled_cogs.csv
```

Практический смысл:

- это основной регулярный loop по blind spots;
- после него market layer уже смотрит не только на official report, но и на локально накопленные override’ы по себестоимости.

### `smoke_test_market_pipeline.py`

Назначение:

- быстро проверить, что market dashboard bundle содержит:
  - `kpis`
  - `tables`
  - `charts`
  - `market_scope`

Пример:

```bash
python3 smoke_test_market_pipeline.py
```

Ожидаемый результат:

- вывод `SMOKE_MARKET_OK`

### `smoke_test_pricing_pipeline.py`

Назначение:

- быстро проверить, что dynamic pricing dashboard bundle содержит:
  - `metadata.pricing`
  - `kpis`
  - `actions`
  - `tables.priced_windows`
  - `charts.pricing_labels`

Пример:

```bash
python3 smoke_test_pricing_pipeline.py
```

Ожидаемый результат:

- вывод `SMOKE_PRICING_OK`

### `refresh_operational_dashboard.py`

Назначение:

- пересобрать `weekly` или `official` dashboard bundle из уже существующих raw CSV;
- подтянуть в dashboard новые поля или UI-ready структуры после рефакторинга без повторного запроса отчётов.
- это также способ выровнять старые `official_*` bundle'ы с metadata от `weekly`, чтобы в UI появились:
  - окно периода
  - `documents.*_request_id`
  - режим `reused`
  - единый family/UI слой

Пример:

```bash
python3 refresh_operational_dashboard.py \
  --sells-report data/raw_reports/sells-report.csv \
  --left-out-report data/raw_reports/left-out-report.csv \
  --metadata-from data/dashboard/weekly_operational_report_2026-04-08.json \
  --normalized-output data/normalized/weekly_operational_report_2026-04-08.json \
  --dashboard-output data/dashboard/weekly_operational_report_2026-04-08.json
```

### `request_document_report.py`

Назначение:

- создавать async job в seller documents API;
- ждать завершения;
- получать готовый CSV-отчёт по ссылке.

Подтверждённые job types:

- `LEFT_OUT_REPORT`
- `SELLS_REPORT`

Пример `SELLS_REPORT`:

```bash
python3 request_document_report.py \
  --job-type SELLS_REPORT \
  --date-from 2026-04-02T00:00:00 \
  --date-to 2026-04-08T23:59:59 \
  --group \
  --download
```

Выходные файлы:

- `reports/document_report_<YYYY-MM-DD>.json`
- скачанный CSV, если задан `--download`

## Рекомендации для AI/LLM-агента

Если агенту нужно использовать этот проект без дополнительного контекста, безопасный порядок такой:

1. Прочитать этот `README.md`.
2. Проверить наличие `KAZANEXPRESS_TOKEN`, если планируется seller API.
3. Для сбора продавцов использовать в первую очередь `get_sellers.py`.
4. Не полагаться на старые публичные `api/v2/search` маршруты, они больше не являются рабочей основой.
5. Всегда сохранять output в отдельный JSON и переиспользовать его как checkpoint.
6. Если сбор выглядит неполным, проверить поле `truncated_segments`.

### Рекомендуемые команды для агента

Собрать продавцов по категории:

```bash
python3 ./get_sellers.py --category-id 10162 --page-size 50 --progress --output reports/mm_sellers_10162.json
```

Сравнить магазины:

```bash
python3 ./compare_shops.py --my-shop-id 98 --competitor-shop-id 40319
```

Проанализировать остатки:

```bash
python3 ./analyze_products.py --shop-id 98
```

Сравнить карточки товаров:

```bash
python3 ./benchmark_product_cards.py --sample-size 5 --comparables 4
```

Сравнить пересечения с top-N продавцов:

```bash
python3 ./compare_top_seller_overlaps.py --sample-size 40 --top-n 10 --min-similarity 0.5
```

Сгруппировать ассортимент и сравнить группы:

```bash
python3 ./analyze_product_ideas.py --group-representatives 4 --min-similarity 0.22
```

Собрать итоговый план роста:

```bash
python3 ./build_growth_plan.py
```

Посмотреть family-level слой по `ШК` и вариантам:

```bash
python3 ./analyze_variant_families.py \
  --sells-report /path/to/sells-report.csv \
  --left-out-report /path/to/left-out-report.csv
```

Снять снапшот магазина:

```bash
python3 ./snapshot_shop.py --token "$KAZANEXPRESS_TOKEN"
```

Посчитать реальный спрос за окно:

```bash
python3 ./analyze_time_window.py \
  --start-snapshot data/snapshots/shop_98_2026-04-01.json \
  --end-snapshot data/snapshots/shop_98_2026-04-08.json
```

Сделать CubeJS-запрос по окну времени:

```bash
python3 ./cubejs_query.py \
  --cookie "$MM_ANALYTICS_COOKIE" \
  --shop-id 98 \
  --measures Sales.seller_revenue_without_delivery_measure \
  --date-range "last 7 days" \
  --granularity day
```

Запросить seller CSV-отчёт:

```bash
python3 ./request_document_report.py \
  --job-type SELLS_REPORT \
  --date-from 2026-04-02T00:00:00 \
  --date-to 2026-04-08T23:59:59 \
  --group \
  --download
```

Проанализировать официальные seller CSV:

```bash
python3 ./analyze_official_reports.py \
  --sells-report /path/to/sells-report.csv \
  --left-out-report /path/to/left-out-report.csv
```

Собрать weekly операционный отчёт целиком:

```bash
python3 ./weekly_operational_report.py \
  --token "$KAZANEXPRESS_TOKEN" \
  --window-days 7
```

Получить листовые подкатегории:

```bash
python3 ./collect_sellers.py --category-id 10162
```

Проверить новый token по ключевым endpoint'ам:

```bash
python3 ./validate_token_integrations.py --token "$KAZANEXPRESS_TOKEN"
```

Пересобрать индекс dashboard-отчётов:

```bash
python3 ./build_dashboard_index.py
```

## Known Issues

- `collect_sellers.py` зависит от seller API дерева категорий, которое может быть нестабильным.
- `compare_shops.py` и `analyze_products.py` зависят от seller API и валидного токена.
- `benchmark_product_cards.py` работает лучше всего на массовых SKU; по нишевым товарам публичный поиск может давать мало по-настоящему похожих аналогов.
- `compare_top_seller_overlaps.py` может возвращать пустой результат по top-10 продавцов, если лидеры категории сидят в других товарных поднишах.
- `analyze_product_ideas.py` группирует товары по эвристическим правилам на основе title, поэтому часть SKU может попадать в широкую группу `Прочее`.
- `analyze_competitor_market.py` использует `idea_clusters` и ценовые коридоры как эвристику наблюдаемой выборки, а не как точное SKU-сопоставление.
- `build_growth_plan.py` строит стратегические выводы по уже готовым отчётам и не заменяет анализ текущего спроса по окнам времени.
- `cubejs_query.py` может требовать cookie браузерной сессии, а не только bearer token.
- `request_document_report.py` опирается на подтверждённые job types, но список доступных job types может быть шире и меняться.
- `analyze_official_reports.py` даёт более правильный операционный слой, чем `analyze_products.py`, если доступны официальные CSV seller reports.
- `weekly_operational_report.py` зависит от работающего seller documents API и валидного токена.
- `get_sellers.py` использует комбинацию `web-api.mm.ru` и старого product API `api.kazanexpress.ru`, потому что это сейчас рабочая связка для seller resolution.
- API может менять схемы ответа без предупреждения.

## Архитектура

Слой проекта теперь лучше понимать так:

- `core/`
  Переиспользуемая логика и модули.
- `ROADMAP.md`
  Актуальные этапы, приоритеты и ограничения проекта.
- `connectors`
  seller API, documents API, CubeJS, public market API.
- `analytics`
  группировка идей, official period analysis, growth plan.
- `presentation`
  markdown/csv/json артефакты.

Это сделано специально, чтобы было легче:

- менять отдельные модули;
- добавлять новые источники данных;
- перейти позже к браузерному интерфейсу.

## Что уже проверено

- `get_sellers.py` успешно собрал продавцов по категории `10162`.
- `analyze_products.py` и `compare_shops.py` приведены к безопасному CLI-виду без захардкоженных секретов.
- `collect_sellers.py` оставлен как отдельный helper для seller API дерева категорий.
