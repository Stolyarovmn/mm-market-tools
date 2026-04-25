# Function to UI Coverage Audit

Дата: `2026-04-10`

## Цель

Проверить:

- все ли функции проекта уже отражены в UI там, где это действительно нужно;
- какие функции правильно оставить CLI-only;
- нет ли дублирования между main dashboard UI и refresh runner UI;
- где документация и фактический UX уже расходятся.

## Принцип разделения

Не каждая CLI-функция обязана появляться в UI.

Правильное деление такое:

- `UI-worthy`
  - периодические действия менеджера;
  - refresh jobs;
  - просмотр KPI, action-lists, history, market windows;
  - ручные watchlists и задачи.
- `CLI-first`
  - исследовательские и ad hoc анализы;
  - миграции/ремонтные утилиты;
  - smoke tests;
  - bulk pipelines, где UI не добавляет пользы.

## Уже покрыто в UI

### Main dashboard UI

- просмотр `weekly_operational`
- просмотр `official_period_analysis`
- просмотр `cubejs_period_compare`
- просмотр `competitor_market_analysis`
- просмотр `dynamic_pricing`
- переключение отчётов
- тёмная/светлая тема
- action-driven cards
- `Что изменилось`
- `Action Center`
- переход на refresh UI

### Refresh runner UI

- `validate_token`
- `weekly_operational`
- `market_scan`
- `dynamic_pricing`
- `sellers_scan`
- `dashboard_rebuild`
- `cogs_backfill_cycle`
- статус
- live log
- история запусков
- ссылки на артефакты

## CLI-only и это нормально

### Research / diagnostics

- `benchmark_product_cards.py`
- `compare_top_seller_overlaps.py`
- `analyze_product_ideas.py`
- `build_growth_plan.py`
- `build_market_margin_fit_report.py`
- `build_cost_coverage_backlog.py`
- `build_zero_cogs_registry.py`
- `export_cogs_fill_template.py`
- `rescore_market_after_cogs_fill.py`
- `analyze_variant_families.py`
- `analyze_time_window.py`
- `snapshot_shop.py`

Причина:

- это исследовательские или operator-heavy сценарии;
- им нужен файл-ориентированный workflow;
- UI для них сейчас дал бы больше шума, чем ценности.

### Maintenance / internal tools

- `migrate_dashboard_schema.py`
- `refresh_operational_dashboard.py`
- `smoke_test_official_pipeline.py`
- `smoke_test_market_pipeline.py`

Причина:

- это внутренние сервисные инструменты;
- не нужны менеджеру в ежедневном UI.

## Частично покрыто, но ещё не доведено

### 1. `weekly_operational_report.py`

Покрытие есть:

- job есть в refresh UI;
- результат читается в main UI.

Чего не хватает:

- после запуска runner не переводит пользователя автоматически на свежий dashboard bundle;
- нет shortcut “открыть свежий weekly report”.

### 2. `analyze_competitor_market.py`

Покрытие есть:

- market scan можно запустить через refresh UI;
- результат читается в market dashboard.

Чего не хватает:

- нет drilldown до entity pages:
  - seller page
  - niche page
  - group page
- нет saved filters.

### 3. `build_dynamic_pricing_report.py`

Покрытие есть:

- dynamic pricing report можно пересобрать через refresh UI;
- результат читается в main dashboard как отдельный тип отчёта.

Чего не хватает:

- пока нет entity-level price page;
- нет истории ценовых рекомендаций по одной и той же поднише;
- нет подтверждения ручного применения рекомендации.

### 4. `get_sellers.py`

Покрытие есть:

- sellers scan доступен в refresh UI.

Чего не хватает:

- нет отдельного result viewer для seller list;
- нет простого перехода к `mm_sellers_*.json`.

## Что пока не нужно тащить в UI

- `collect_sellers.py`
- `compare_shops.py`
- `analyze_products.py`
- `request_document_report.py`
- `cubejs_query.py`

Причина:

- либо legacy / low-level;
- либо слишком технические для менеджерского интерфейса;
- либо покрыты более high-level flow.

## Дублирование и пересечения

### Здоровое дублирование

- `weekly_operational` и `official_period_analysis`
  - допустимо, потому что это разные варианты одного operational слоя;
  - UI теперь различает их по variant и metadata.

- `main dashboard UI` и `refresh runner UI`
  - тоже допустимо:
  - один экран для анализа;
  - второй для online refresh jobs.

### Нездоровое или потенциально вредное дублирование

- часть смыслов всё ещё повторяется между:
  - action cards,
  - automatic insights,
  - action lists.

Это не критично, но следующий шаг:

- ещё жёстче развести роли:
  - action cards = что делать сейчас;
  - insights = почему это важно;
  - tables = где именно лежат сущности.

## Вывод

UI уже покрывает почти все менеджерские сценарии, которые действительно должны быть вынесены в браузер.

Главный gap сейчас не “ещё больше CLI перенести в UI”, а:

- делать UI глубже по workflow;
- добавлять entity pages;
- добавлять post-refresh navigation;
- сокращать cognitive load;
- не тащить в UI maintenance и research утилиты, которым там не место.
