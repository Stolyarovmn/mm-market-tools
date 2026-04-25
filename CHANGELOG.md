# Changelog

Все заметные изменения в этом проекте документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
и этот проект придерживается [Семантического Версионирования](https://semver.org/lang/ru/).

## [unreleased] - 2026-04-24
### TASK-004: zero_cogs_registry SKU-level validation and CSV export
- Enhanced `build_zero_cogs_registry.py` with CSV export functionality
  - Exports zero_cogs_registry_{date_tag}.csv with complete SKU data for manual COGS override workflow
  - CSV includes TASK-004 required columns: group, product_id, sku, barcode, current_price, competitor_prices, market_count, orders_sum, notes
  - Also includes ingest_cogs_fill.py contract columns for round-trip workflow: title, seller_sku_id, sale_price, total_stock, units_sold_window, priority_score, fill_cogs, fill_source, fill_comment
  - SKU deduplication logic prevents duplicate (sku, seller_sku_id, product_id) tuples
- Created `validate_zero_cogs_registry.py` for registry validation
  - Validates JSON structure, required fields, numeric types
  - Verifies no duplicate SKU identities
  - Checks summary count consistency with items list
  - Returns PASS/FAIL status with detailed error reporting
- Created `smoke_test_zero_cogs_registry.py` for synthetic testing
  - Tests build_registry() with in-memory synthetic payloads
  - Verifies correct COGS=0 and COGS=None identification
  - Confirms no false positives (items with COGS>0)
  - Validates group coverage and summary counts
## [unreleased] - 2026-04-24
### Added
- TASK-003: build_market_margin_fit_report.py — price_band breakdown (low/mid_low/mid/high/premium/unknown), go/no-go decision logic vs target margin, price_band_summary section, acceptance_windows_by_price_band section.

## [Unreleased]

### Added

- Добавлен детальный inventory ЛК продавца с live-подтверждением по текущему кабинету:
  - `reports/seller_cabinet_inventory_2026-04-13.md`
  - внутри зафиксированы разделы ЛК, что уже забирает проект, что подтверждено через `documents/requests` и `CubeJS meta`, и где самые ценные gaps, включая накладные и себестоимость.

- Добавлена матрица ценности отчётности для роста прибыли:
  - `reports/reporting_profit_matrix_2026-04-13.md`
  - внутри зафиксировано, какие отчёты удалось получить live, какие пока только подтверждены, и какой из них даёт наибольший вклад в рост прибыли.

- Добавлен research-note по накладным и контракту seller documents create:
  - `reports/waybill_cost_and_documents_create_research_2026-04-13.md`
  - внутри зафиксировано, почему накладные становятся следующим cost-layer приоритетом и почему `documents/create` пока нельзя считать устойчивым контрактом.

- Добавлен implementation-plan по waybill cost layer:
  - `reports/waybill_cost_layer_plan_2026-04-13.md`
  - внутри зафиксированы поля batch-layer, схема связки с продажами/остатками/хранением, ToD и тесты на реализацию cost history.

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Refresh runner получил более product-like result layer:
  - отдельный блок `Результат шага` в `refresh.html`
  - краткий итог состояния run
  - preview параметров запуска
  - привязку свежих артефактов к `data/dashboard/index.json`, если артефакт является dashboard bundle
  - быстрый переход из runner в основной dashboard по свежему report bundle
- Добавлен research report по покрытию seller cabinet:
  - [`reports/seller_cabinet_coverage_2026-04-11.md`](/home/user/mm-market-tools/reports/seller_cabinet_coverage_2026-04-11.md)
  - внутри зафиксировано:
    - какие отчёты и данные есть в ЛК продавца;
    - что уже использует проект;
    - какие API реально подтверждены;
    - какие gaps самые ценные для следующей итерации.
- Добавлен первый новый seller-cabinet source layer:
  - `core/xlsx_reader.py`
  - `build_paid_storage_report.py`
  - online refresh job `paid_storage_report`
  - новый report kind `paid_storage_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки нового источника:
  - `reports/paid_storage_report_2026-04-11_smoke.json`
  - `reports/paid_storage_report_2026-04-11_smoke.md`
  - `data/dashboard/paid_storage_report_2026-04-11_smoke.json`

### Changed

- seller-cabinet coverage audit расширен до полного inventory ЛК:
  - теперь явно отражены не только отчёты и аналитика, но и финансы, накладные, закрывающие документы, товары, цены, остатки, FBS, маркетинг, отзывы и чат;
  - отдельно зафиксировано, что накладные являются потенциально самым ценным недоиспользованным источником себестоимости.

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `ui/refresh.js` теперь показывает не только лог и список файлов, но и следующий шаг после run:
  - открыть свежий артефакт;
  - перейти в основной dashboard;
  - проверить `Что Изменилось` и follow-up.
- `refresh.html` и основной dashboard переведены на same-origin ссылки `/refresh.html` и `/`, чтобы не было ложных белых страниц из-за неправильного URL.
- `web_refresh_server.py` теперь умеет fallback-маршрутизацию старых asset paths:
  - `/styles.css`
  - `/refresh.js`
  - `/app.js`
  - сопутствующие `/ui/*` модули
- token-layer в `refresh.html` усилен:
  - единый session-only токен
  - `Сохранить и проверить`
  - проверка JWT перед сохранением
  - статус валидности и причина ошибки в UI
- detail-panel теперь пытается восстанавливать пустые поля из накопленной истории сущности, а не только из текущего snapshot.
- основные bar-chart блоки получили прикладные `(i)` с пояснением, как читать график и для чего он нужен.
- в `Центре действий` добавлен явный lifecycle-блок, который честно объясняет: статусы пока меняются вручную, auto-close и retry-логики ещё нет.
- detail-panel получил нижнюю навигацию по соседним сущностям, чтобы не мотать экран обратно наверх после чтения истории.
- нижняя навигация detail-panel сделана липкой, чтобы кнопки соседних SKU не исчезали при длинном скролле.
- toolbar `Центра действий` теперь кратко объясняет реальный рабочий flow этого блока.
- refresh runner получил верхнюю sticky-панель запуска:
  - быстрый статус активного run
  - размер очереди
  - групповые кнопки `online / offline / всё`
  - последовательный запуск с паузой между job
- jobs на refresh page разделены на online/offline группы и получили `(i)` в заголовках.
- действия на refresh page тоже получили `(i)`:
  - токеновые действия
  - групповые запускатели очереди
  - запуск одиночного job
  - открытие run и артефактов
- селектор отчётов в основном дашборде теперь сам подтягивает новые bundle из `data/dashboard/index.json` без ручного reload страницы.
- Сделан быстрый owner-feedback polish pass по main UI:
  - `Карточка и история` вместо `Карточка И История`
  - верхняя сводка и KPI теперь имеют явные заголовки
  - display-title старается показывать `SKU · название`
  - `reused` переведён в понятный режим `загружено из архива`
  - `Watchlist` и `Saved views` переведены в пользовательские термины
  - плавающая кнопка `↑` заменила статичное `Наверх`
  - info-bubbles теперь можно открывать кликом, а длинные подсказки получили прокрутку
- `PAID_STORAGE_REPORT` подключён как manager-facing экран:
  - reuse последнего completed seller document вместо догадок про create-contract;
  - XLSX читается без `pandas/openpyxl`;
  - в основном UI появились отдельные KPI, actions, tables, charts и insights для платного слоя.
- по UI добраны пояснения термина `gap`:
  - в `(i)` теперь явно объясняется, что это отставание или разница относительно рынка/группы;
  - англоязычные формулировки `visual gap` / `gaps` заменены на более понятные пользовательские тексты.

### Planned

- `ISSUE-001`: заменить proxy `novelty_proxy_index` на age-aware newcomer-friendliness index, если будет найден подтверждённый источник `created_at`.
- `ISSUE-006`: протянуть persistent COGS override store из market layer в operational/growth отчёты.
- `ISSUE-007`: сделать action-driven dashboard redesign:
  - усилить верхний action-first слой;
  - вынести `app.js` в модули;
  - добавить richer visual trends без перегруза интерфейса.
- `ISSUE-008`: добавить recommendation-first repricer / dynamic pricing layer без unsafe auto-apply.
- `ISSUE-011`: добавить `price trap auditor` для SKU чуть выше психологических ценовых порогов.
- `ISSUE-012`: добавить `title SEO priority analyzer`, который проверяет, вынесены ли главные ключевые слова в первые 3 слова title.
- `ISSUE-014`: logistics fee auditor по границам веса/габаритов, если подтвердится надёжный источник размеров и веса.
- `ISSUE-016`: media richness auditor по фото/видео и visual gaps против конкурентов.
- `ISSUE-017`: dimension-fee optimizer, если подтвердится реальный источник размеров/веса и связь с тарифом MM.
- `ISSUE-018`: description SEO richness auditor по длине и “thin content”.
- Уточнить market-классификатор для общих товарных title, чтобы уменьшить шумные попадания в широкие группы.
- Зафиксировать и поддерживать audit loop policy: перед каждой автономной итерацией читать и `issues.md`, и `disagreements*.md`, а несогласия оформлять отдельным протоколом.
- Развить `web_refresh_server.py` до более удобного runner UI с более явным progress model для долгих jobs и ссылками на свежие артефакты.
- Протянуть новый `Action Center` от базового watchlist/task store к manager workflow: saved views, acknowledgements, ручные причины решений.
- После получения свежего access token прогнать live `sales_return_report`.
- Затем повторить live `paid_storage_report`, когда seller documents API перестанет отвечать `503`.
- Если live `SalesReturn` упрётся в реальный CubeJS contract mismatch, не зацикливаться:
  - сохранить `sales_return_report` как готовый offline/source layer;
  - править live query уже по фактическому meta/load ответу;
  - затем брать `PaidPromo*` как следующий seller-cabinet gap.

## [0.2.20] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен общий content/cache слой:
  - `core/card_content.py`
  - `data/local/product_content_cache.json` как постоянный cache-контур под public product content
- Добавлен initial layer для `ISSUE-016`:
  - `build_media_richness_report.py`
  - `smoke_test_media_richness_report.py`
  - online refresh job `media_richness_audit`
- Добавлен initial layer для `ISSUE-018`:
  - `build_description_seo_richness_report.py`
  - `smoke_test_description_seo_richness_report.py`
  - online refresh job `description_seo_richness_audit`
- Добавлен отдельный research note по `ISSUE-017`:
  - `reports/dimension_fee_optimizer_research_2026-04-10.md`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `ISSUE-017` переведён в честный `research + plan` статус:
  - без подтверждённого источника `weight/dimensions` optimizer не внедряется.
- Dashboard index теперь понимает ещё два report kind:
  - `media_richness_report`
  - `description_seo_report`
- Main UI подготовлен под новые content-audit отчёты:
  - отдельные KPI
  - отдельные actions
  - отдельные tables/charts
  - отдельные metadata-варианты для `content_audit`
- `build_marketing_card_audit.py` теперь умеет подхватывать и media/description слои, если соответствующие JSON уже собраны.

### Verified

- `python3 -m py_compile` проходит для новых builders/core-модулей
- `node --check` проходит для:
  - `ui/app.js`
  - `ui/dashboard_views.js`
- smoke tests:
  - `SMOKE_MEDIA_RICHNESS_OK`
  - `SMOKE_DESCRIPTION_SEO_OK`

## [0.2.17] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Action Center получил event-log слой:
  - `events` внутри `action_center.json`
  - журнал ручных действий по сущности в detail-panel
- В detail-panel добавлен отдельный блок:
  - `История управленческих решений`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- Основной dashboard теперь должен запускаться через `start_dashboard_ui.sh`, который поднимает `web_refresh_server.py` на `:8000`, а не через голый `http.server`.
- `ui/api.js` теперь сначала пробует same-origin API, поэтому `В список` и `Задача` работают и на основном dashboard, если он поднят через новый launch contract.
- Кнопка `Детали` теперь прокручивает к panel и даёт визуальный pulse-highlight.
- Укреплены правила вёрстки для длинных названий, источников и значений metadata, чтобы UI меньше ломался от длинных строк.

### Fixed

- Исправлен главный runtime-разрыв, из-за которого основной UI был без `/api` и Action Center отвечал `Failed to fetch`.
- Исправлен UX-дефект, когда `Детали` выглядело как “ничего не произошло”, хотя detail-panel обновлялась ниже по странице.

### Verified

- `http://127.0.0.1:8000/api/action-center` и `http://127.0.0.1:8040/api/action-center` отдают одинаковый живой store.
- `node --check` и `py_compile` проходят после перевода dashboard на общий server contract.

## [0.2.18] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Action Center получил manager-workflow слой:
  - `owner` у задач
  - расширенные статусы `open / in_progress / blocked / done`
  - `saved_views` в store
- В main UI добавлены:
  - toolbar для Action Center
  - фильтр задач
  - сохранение view
  - быстрые переходы по saved views

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `ISSUE-015` продвинут от history-snapshot к управленческому workflow:
  - теперь есть не только события по сущности, но и зачаток диспетчеризации задач;
  - detail-panel и Action Center начинают сходиться в единую manager loop.
- `web_refresh_server.py` теперь умеет:
  - `/api/action-center/action/update`
  - `/api/action-center/view`

### Verified

- live POST на `/api/action-center/action/update` проходит;
- live POST на `/api/action-center/view` проходит;
- `node --check` и `py_compile` проходят после добавления owner/status/saved view слоя.

## [0.2.19] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- В main UI добавлен отдельный manager-facing блок:
  - `Очереди Follow-up`
- Внутри него появились:
  - очередь по статусам
  - очередь по owner
  - очередь по saved views

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `ISSUE-007` продвинут ещё на один шаг:
  - Action Center теперь читается не только как store, но и как диспетчер follow-up цикла.
- `ISSUE-015` practically extended:
  - ручная история решений теперь подаётся не только на entity-level, но и в агрегированном manager view.

### Verified

- `node --check` проходит после добавления нового queue-layer в `ui/app.js`.

## [0.2.14] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен unified manager-facing marketing layer:
  - `build_marketing_card_audit.py`
  - `reports/marketing_card_audit_2026-04-10.json`
  - `reports/marketing_card_audit_2026-04-10.md`
  - `data/dashboard/marketing_card_audit_2026-04-10.json`
- Добавлен `smoke_test_marketing_card_audit.py`
- В refresh runner добавлен offline job:
  - `marketing_card_audit`
- В dashboard index и UI добавлен новый report kind:
  - `marketing_card_audit`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `ISSUE-013` переведён из gap в рабочий initial layer:
  - price trap и title SEO больше не висят только в CLI/markdown;
  - они собраны в единый manager-facing экран вместе с pricing context.
- Main UI теперь умеет рендерить marketing audit как отдельный экран с:
  - KPI
  - action-first cards
  - очередями `исправить сейчас / тест цены / переписать title`
  - таблицами по карточкам
  - charts по типам проблем
- `web_refresh_server.py` после перезапуска отдаёт новый job `marketing_card_audit` через `/api/jobs`.

### Fixed

- Исправлен merge-bug первой версии marketing audit, где слой брал случайный срез rows и терял часть `price_trap` сигналов.
- Исправлена entity-типизация в main UI: SKU-строки marketing-аудита больше не сохраняются в Action Center как `market_segment` только из-за наличия `group`.

### Verified

- `build_marketing_card_audit.py` выпустил:
  - `reports/marketing_card_audit_2026-04-10.json`
  - `reports/marketing_card_audit_2026-04-10.md`
  - `data/dashboard/marketing_card_audit_2026-04-10.json`
- `smoke_test_marketing_card_audit.py` → `SMOKE_MARKETING_CARD_AUDIT_OK`
- `build_dashboard_index.py` видит новый report kind `marketing_card_audit`
- refresh runner после перезапуска отдаёт job `marketing_card_audit` через `/api/jobs`

## [0.2.15] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен entity-history слой для dashboard drilldown:
  - `core/entity_history.py`
  - `build_entity_history_index.py`
  - `data/local/entity_history_index.json`
- Добавлен `smoke_test_entity_history_index.py`
- В main UI добавлена detail-panel:
  - `Карточка И История`
  - история появления сущности в `marketing_card_audit`
  - текущий ручной follow-up статус из `Action Center`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `build_dashboard_index.py` теперь автоматически пересобирает и `data/local/entity_history_index.json`.
- В main UI строки отчётов получили кнопку `Детали`, которая открывает history/follow-up drilldown по сущности.
- `ISSUE-014` перенесён в backlog проекта и не потеряется между итерациями.

### Verified

- `build_dashboard_index.py` успешно выпустил:
  - `data/dashboard/index.json`
  - `data/local/entity_history_index.json`
- `node --check` проходит для main UI после добавления detail-panel

## [0.2.16] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Action Center расширен entity-level acknowledgements:
  - backend: `/api/action-center/acknowledge`
  - store: `acknowledgements` внутри `action_center.json`
- В detail-panel по сущности добавлена кнопка:
  - `Подтвердить разбор`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- Detail-panel теперь показывает не только watchlist/tasks, но и acknowledgement по сущности:
  - когда карточка была разобрана;
  - какой комментарий сохранён.
- Action Center status-card теперь показывает число подтверждённых сущностей.

### Verified

- live POST на `/api/action-center/acknowledge` проходит и сохраняет acknowledgement в `action_center.json`
- `node --check` и `py_compile` проходят после добавления acknowledgement flow

## [0.2.12] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен маркетинговый аудит `price trap`:
  - `build_price_trap_report.py`
  - `reports/price_trap_report_2026-04-10.json`
  - `reports/price_trap_report_2026-04-10.md`
- Добавлен `smoke_test_price_trap_report.py`
- В refresh runner добавлен offline job:
  - `price_trap_audit`
- Добавлен follow-up audit:
  - `reports/consistency_audit_2026-04-10b.md`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `README.md` теперь описывает:
  - `build_price_trap_report.py`
  - `smoke_test_price_trap_report.py`
- `ROADMAP.md` теперь явно несёт carry-forward для:
  - `ISSUE-011`
  - `ISSUE-012`

### Verified

- `build_price_trap_report.py` на реальных normalized rows нашёл `33` SKU рядом с психологическими порогами
- `smoke_test_price_trap_report.py` → `SMOKE_PRICE_TRAP_OK`
- refresh runner после перезапуска отдаёт job `price_trap_audit` через `/api/jobs`

## [0.2.13] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен initial layer для `ISSUE-012`:
  - `build_title_seo_report.py`
  - `reports/title_seo_report_2026-04-10.json`
  - `reports/title_seo_report_2026-04-10.md`
- Добавлен `smoke_test_title_seo_report.py`
- В refresh runner добавлен offline job:
  - `title_seo_audit`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `README.md` теперь описывает:
  - `build_title_seo_report.py`
  - `smoke_test_title_seo_report.py`
- `ISSUE-012` больше не просто backlog-идея: есть первая рабочая эвристическая реализация.

### Verified

- `build_title_seo_report.py` успешно собрал SEO-аудит по `150` normalized rows
- `smoke_test_title_seo_report.py` → `SMOKE_TITLE_SEO_OK`
- refresh runner после перезапуска отдаёт job `title_seo_audit` через `/api/jobs`

## [0.2.11] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- `build_dynamic_pricing_report.py` теперь выпускает не только markdown/json в `reports/`, но и отдельный dashboard bundle:
  - `data/dashboard/dynamic_pricing_<date>.json`
- Добавлен новый dashboard report kind:
  - `dynamic_pricing`
- Добавлен offline refresh job:
  - `dynamic_pricing`
- Добавлен `smoke_test_pricing_pipeline.py`
- Начат следующий слой UI modularization:
  - `ui/dashboard_views.js`
  - `ui/components.js`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `build_dashboard_index.py` и `core/dashboard_index.py` теперь держат совместимый dual contract:
  - `items`
  - `reports`
- Main UI теперь умеет рендерить `dynamic_pricing` как отдельный экран с:
  - KPI
  - action cards
  - таблицами
  - charts
  - pricing insights
- `ui/app.js` больше не хранит внутри себя всю report-kind логику для:
  - `cubejs_period_compare`
  - operational insights
  - pricing insights
- Навигационные ссылки на refresh UI теперь тоже используют текущий hostname, а не только жёсткий `127.0.0.1`.

### Fixed

- Устранён schema drift, где часть tooling ожидала `reports`, а основной UI использовал только `items`.
- Устранён product gap, где repricer существовал только как markdown/json артефакт и не был виден в dashboard UI.

### Verified

- `py_compile` для:
  - `build_dynamic_pricing_report.py`
  - `core/dashboard_index.py`
  - `core/refresh_jobs.py`
- `node --check` для:
  - `ui/app.js`
  - `ui/dashboard_views.js`
  - `ui/api.js`
  - `ui/state.js`
- `build_dynamic_pricing_report.py` успешно выпустил:
  - `reports/dynamic_pricing_2026-04-10.json`
  - `reports/dynamic_pricing_2026-04-10.md`
  - `data/dashboard/dynamic_pricing_2026-04-10.json`
- `build_dashboard_index.py` видит новый report kind `dynamic_pricing` и dual contract `items/reports`.

## [0.2.8] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- В main dashboard UI добавлен action-driven верхний слой:
  - `Приоритеты Сейчас`
  - отдельные action-first cards для:
    - operational
    - market
    - long-range compare
- Добавлены audit-артефакты:
  - `reports/function_ui_coverage_2026-04-10.md`
  - `reports/test_plan_2026-04-10.md`
  - `reports/consistency_audit_2026-04-10.md`
  - `reports/cli_help_sweep_2026-04-10.json`
- В `disagreements_2026-04-09.md` добавлен formal alignment block по `nightly_research_report.md`.

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `README.md` теперь явно предупреждает: после обновления `web_refresh_server.py` уже запущенный runner нужно перезапускать.
- `ROADMAP.md` теперь отдельно фиксирует:
  - modularization backlog для `ui/app.js`
  - recommendation-first repricer roadmap
- `CHANGELOG.md -> Planned` теперь содержит `ISSUE-007` и `ISSUE-008`, чтобы новые auditor issues не пропадали мимо project backlog.

### Verified

- `31/31` CLI entrypoints проходят `--help`
- live runner API tests подтверждены:
  - `/api/jobs`
  - `/api/runs`
  - `/api/action-center`
  - `/api/artifact`
- action-center POST flow подтверждён:
  - watchlist add
  - action add
  - toggle action status

## [0.2.9] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Начато безопасное modularization UI:
  - добавлен `ui/api.js`
  - `app.js` переведён на отдельный API-layer
- Добавлен recommendation-first repricer report:
  - `build_dynamic_pricing_report.py`
  - `reports/dynamic_pricing_2026-04-10.json`
  - `reports/dynamic_pricing_2026-04-10.md`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- Main dashboard больше не опирается жёстко только на `127.0.0.1:8040` для Action Center:
  - добавлен fallback по текущему hostname и `localhost`
- Ошибка `Failed to fetch` для Action Center заменена на более прикладное сообщение:
  - проверить runner на `:8040`
  - при необходимости перезапустить после обновления кода

### Fixed

- Уменьшен шанс ложного `Failed to fetch` в браузере при рабочем runner, запущенном не под тем hostname, что захардкожен в UI.
- Устранено дублирование ручных action items по одному и тому же `entity_key/context/title`, пока задача ещё открыта.

## [0.2.10] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Продолжено modularization UI:
  - добавлен `ui/state.js`
  - theme/report-selection state больше не живут целиком внутри `app.js`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `refresh.html` и `index.html` переведены на `type=\"module\"`
- `refresh.js` теперь использует общий state-layer для темы
- в основном dashboard добавлено сохранение последнего выбранного отчёта в `localStorage`

### Fixed

- Вручную очищены старые лишние записи в `data/local/action_center.json`, чтобы убрать шум после ранних тестов.

## [0.2.7] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен versioned dashboard schema layer:
  - `core/dashboard_schema.py`
  - `migrate_dashboard_schema.py`
- Добавлен stateful action-center store:
  - `core/action_store.py`
  - `data/local/action_center.json`
- В main UI добавлены:
  - блок `Что изменилось`
  - `Action Center`
  - кнопки `В список` и `Задача` на строках operational/market таблиц
- В refresh runner добавлены:
  - сбор артефактов из `Saved: ...`
  - download endpoint `/api/artifact`
  - action-center API endpoints

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `core/auth.py` теперь делает proactive JWT expiration guard до сетевых вызовов:
  - expired token -> hard fail
  - near-expiry token -> explicit warning
- `core/dashboard_index.py` теперь:
  - несёт `schema_version`
  - считает change summary относительно предыдущего отчёта того же вида
- `web_refresh_server.py` теперь работает не только как job runner, но и как local state API для dashboard UI.
- `build_dashboard_index.py` усилен явным `sys.path` bootstrap, чтобы не брать не тот `core` слой при запуске по абсолютному пути.

### Fixed

- Исправлен product gap, где dashboard был только read-only витриной без stateful ручного слоя.
- Исправлен product gap, где refresh runner не показывал, какие файлы реально выпустил job.
- Закрыт `ISSUE-005` в согласованном компромиссном виде: guard-only, без выдуманного auto-refresh.
- Закрыт `ISSUE-002` в proxy-реализации через `sales velocity in stock days` и `estimated lost units`.

### Verified

- `py_compile` для новых Python-модулей и обновлённых builders/server layers
- `node --check` для `ui/app.js` и `ui/refresh.js`
- `SMOKE_OK` для official pipeline
- `SMOKE_MARKET_OK` для market pipeline
- synthetic JWT checks:
  - expired -> fail
  - expiring soon -> warning
  - healthy -> pass

## [0.2.6] - 2026-04-10

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен registry ручных refresh jobs:
  - `core/refresh_jobs.py`
- Добавлен локальный web-runner:
  - `web_refresh_server.py`
- Добавлен отдельный refresh UI:
  - `ui/refresh.html`
  - `ui/refresh.js`
- Добавлено хранение status/log по job run:
  - `data/job_runs/`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- Проект теперь поддерживает split workflow:
  - offline analysis в основном контуре работы
  - online refresh вручную через браузер в отдельной сетевой сессии
- В README добавлен отдельный сценарий для ручного запуска MM refresh jobs.

### Verified

- Runner поддерживает jobs для:
  - token validation
  - weekly operational refresh
  - market scan
  - sellers scan
  - dashboard rebuild
  - cogs backfill cycle

## [0.2.5] - 2026-04-09

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлено постоянное локальное хранилище ручных override’ов по себестоимости:
  - `data/local/cogs_overrides.json`
- Добавлен импорт заполненного COGS CSV в persistent store:
  - `ingest_cogs_fill.py`
- Добавлен единый persistent backfill cycle:
  - `run_cogs_backfill_cycle.py`
  - `reports/cogs_backfill_cycle_<date>.md`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `analyze_competitor_market.py` теперь объединяет:
  - official report economics
  - persistent COGS override store
- `build_zero_cogs_registry.py` теперь не возвращает SKU, уже закрытые через persistent override store.
- `rescore_market_after_cogs_fill.py` теперь умеет объединять official economics, persistent overrides и текущий fill CSV.

### Fixed

- Устранён разрыв между одноразовым ручным fill-тестом и регулярным pipeline: заполненная себестоимость больше не теряется между итерациями.
- Исправлен metadata contract у rescored market dashboard bundle: `market_scope` снова сохраняется и проходит smoke test.

### Verified

- `run_cogs_backfill_cycle.py` успешно отрабатывает end-to-end и выпускает:
  - `zero_cogs_registry`
  - `cogs_fill_template`
  - `market_rescored_after_cogs`
  - `data/dashboard/market_rescored_after_cogs_<date>.json`
- `smoke_test_market_pipeline.py` проходит на `market_rescored_after_cogs_2026-04-09b.json`.

## [0.2.4] - 2026-04-09

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен сценарий пересчёта рынка после заполнения себестоимости:
  - `rescore_market_after_cogs_fill.py`
  - `reports/market_rescored_after_cogs_<date>.json`
  - `reports/market_rescored_after_cogs_<date>.md`
  - `data/dashboard/market_rescored_after_cogs_<date>.json`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `core/market_economics.py` вынесен в reusable слой, чтобы market fit можно было считать и в основном scan, и после ручного fill COGS.
- `core/dashboard_index.py` теперь распознаёт `market_rescored_after_cogs_*` как market report variant.

### Verified

- На synthetic fill-тесте пересчёт дал ожидаемый сдвиг:
  - `economics_coverage_windows_pct`: `53.33 -> 60.0`
  - `entry_ready_windows_count`: `0 -> 1`
  - `Антистрессы и сквиши / 0-199`: `validate_economics -> enter_now`

## [0.2.3] - 2026-04-09

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен SKU-level реестр нулевой себестоимости:
  - `build_zero_cogs_registry.py`
  - `reports/zero_cogs_registry_<date>.json`
  - `reports/zero_cogs_registry_<date>.md`
- Добавлен CSV-шаблон для ручного заполнения себестоимости:
  - `export_cogs_fill_template.py`
  - `reports/cogs_fill_template_<date>.csv`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- Cost coverage loop теперь доходит до конкретных SKU, а не останавливается на уровне групп и окон входа.

### Learned

- В шести главных blind-spot группах проблема сейчас не в отсутствии market scan и не в слабом классификаторе, а в том, что в official rows по этим группам `cogs > 0` отсутствует совсем.
- На текущем срезе `zero_cogs_sku_total = 306`, поэтому следующий bottleneck проекта уже управленческий: дозаполнение себестоимости, а не поиск новых market endpoint’ов.

## [0.2.2] - 2026-04-09

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен отдельный backlog-отчёт по добору cost coverage:
  - `build_cost_coverage_backlog.py`
  - `reports/cost_coverage_backlog_<date>.json`
  - `reports/cost_coverage_backlog_<date>.md`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- `build_market_margin_fit_report.py` теперь разделяет blind spots по типу:
  - `missing_cogs`
  - `no_assortment_reference`
- В `market_margin_fit` появились более прикладные рекомендации:
  - где сначала дозаполнить себестоимость
  - где проблема именно в закупке

### Learned

- На текущем market run слепые зоны почти полностью оказались не “без ассортимента”, а “с ассортиментом, но без cost-покрытия”.
- Это значит, что следующий операционный bottleneck уже не market scan, а заполнение себестоимости по своим SKU в сильных группах.

## [0.2.1] - 2026-04-09

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- В market dashboard добавлен отдельный blind-spot слой:
  - `blind_spot_windows_count`
  - `actions.blind_spots`
  - `tables.strongest_economic_groups`
- В market UI добавлен KPI `Слепые зоны`, чтобы было видно, где спрос уже выглядит рабочим, а cost-покрытия ещё нет.

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- Market insights теперь явно разделяют:
  - где экономика уже понятна
  - где слепые зоны ещё нельзя читать как go/no-go
- `market_margin_fit_*.md/json` теперь пересобирается от актуального normalized market bundle, чтобы shortlist решений не отставал от dashboard.

### Fixed

- Убран ещё один misleading слой в market raw bundle: добавлены явные KPI `observed_seller_count` и `observed_group_count` вместо чтения этих значений через legacy-alias поля.

## [0.2.0] - 2026-04-09

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Добавлен единый auth-слой:
  - `core/auth.py`
- Добавлен единый HTTP-слой:
  - `core/http_client.py`
- В market layer добавлен proxy `индекс новизны`:
  - `novelty_proxy_index`
  - `fresh_top_product_share_pct`
  - `novelty_profile`
- В market dashboard добавлены новые KPI:
  - `overall_dominance_hhi`
  - `novelty_proxy_index`
  - `other_group_share_pct`
  - `economics_coverage_groups_pct`
  - `economics_coverage_windows_pct`
  - `target_margin_pct`
- Добавлен `market_margin_fit` слой по группам и окнам входа:
  - `market_margin_fit_pct`
  - `margin_vs_target_pct`
  - `market_margin_fit_profile`
- Добавлен decision-layer по поднишам:
  - `entry_strategy_bucket`
  - `entry_strategy_label`
  - `entry_strategy_reason`
- Добавлен отдельный отчёт:
  - `build_market_margin_fit_report.py`
  - `reports/market_margin_fit_<date>.json`
  - `reports/market_margin_fit_<date>.md`

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- Каждая новая итерация проекта сначала попадает в `Unreleased`, а затем переносится в отдельную versioned section вида `[MAJOR.MINOR.PATCH] - YYYY-MM-DD`.
- PATCH-итерации используются для исправлений и совместимых улучшений.
- MINOR-итерации используются для нового совместимого функционала и новых модулей.
- MAJOR-итерации используются только при несовместимом изменении dashboard contract, CLI behavior или business rules.
- Отдельно фиксируются изменения:
  - dashboard contract
  - business rules
  - data-source behavior
- Активные сетевые модули (`documents`, `CubeJS`, `market`, `get_sellers`) переведены на централизованный HTTP/auth слой вместо локального дублирования заголовков и retry-логики.
- `market_analysis` заметно расширен:
  - лучшее разбиение по группам
  - более устойчивые `idea_cluster`
  - интерпретация концентрации по порогам HHI `<1500 / 1500-2500 / >2500`
- Market UI теперь показывает не только спрос, но и:
  - HHI концентрации
  - proxy-индекс новизны
  - долю `Прочее`
- `build_growth_plan.py` теперь учитывает operational window-сигналы, чтобы не путать исторические продажи с текущим живым спросом.
- В market layer добавлен drilldown `entry_windows` по сочетанию:
  - группа
  - ценовой коридор
  - HHI
  - novelty
  - entry score
- Market layer начал считать `market_margin_fit` по группам и окнам входа там, где хватает official данных по себестоимости.
- Market UI теперь показывает shortlist решений по трём управленческим режимам:
  - входить первым
  - тестировать точечно
  - не входить или менять закупку
- `analyze_competitor_market.py` теперь принимает `--target-margin-pct`, чтобы рыночные решения читались относительно целевой маржи магазина.
- `build_growth_plan.py` теперь учитывает operational window-сигналы, чтобы не путать исторические продажи с текущим живым спросом.
- UI report selector теперь сгруппирован по видам отчётов и показывает варианты понятнее, чтобы меньше путаться между похожими official bundles.

### Fixed

- Существенно уменьшена доля `Прочее` в тестовом market-run за счёт расширенного классификатора товарных групп.
- Исправлены шумные misclassification-кейсы вроде:
  - `пистолет-брелок`
  - `игрушечные продукты`
  - части `брелков / ролевых наборов`
- Убрано дублирование MM public headers и bearer headers в ключевых активных модулях.
- Большая часть legacy / research-скриптов переведена на единый `core/http_client.py` и `core/auth.py`.
- Убрана часть UX-перегруза в селекторе отчётов: вместо плоского длинного списка UI теперь группирует отчёты по режимам.

## [0.1.0] - 2026-04-08

### Added

- Добавлен второй seller-cabinet analytics layer:
  - `build_sales_return_report.py`
  - online refresh job `sales_return_report`
  - новый report kind `sales_return_report` в dashboard index и browser UI
- Добавлен офлайн smoke dataset для проверки слоя возвратов:
  - `reports/sales_return_report_2026-04-13_smoke.json`
  - `reports/sales_return_report_2026-04-13_smoke.md`
  - `data/normalized/sales_return_report_2026-04-13_smoke.csv`
  - `data/dashboard/sales_return_report_2026-04-13_smoke.json`

- Собран модульный toolkit вокруг проекта `mm-market-tools`, а не просто набор разрозненных скриптов.
- Добавлены слои:
  - `core/`
  - `data/raw`
  - `data/normalized`
  - `data/dashboard`
- Добавлен browser UI в `ui/` со светлой и тёмной темой.
- Добавлены report kinds:
  - `weekly_operational`
  - `official_period_analysis`
  - `cubejs_period_compare`
  - `competitor_market_analysis`
- Добавлен family / multi-variant слой по:
  - `product_id`
  - `ШК`
  - `Seller SKU ID`
  - `SKU`
- Добавлен market layer:
  - ценовые коридоры
  - idea clusters
  - сильнейшие группы
  - top sellers / top products
- Добавлен сигнал концентрации рынка:
  - `leading_seller_share_pct`
  - `dominance_hhi`
  - `competition_profile`
- Добавлены ABC examples:
  - конкретные SKU внутри `A/B/C` по выручке
  - конкретные SKU внутри `A/B/C` по прибыли
- В `get_sellers.py` добавлена сводка по листовым подкатегориям:
  - `orders_sum`
  - `avg_price`
  - `median_price`
  - `min_price`
  - `max_price`
- Добавлен `CHANGELOG.md` как отдельный continuity-артефакт проекта.

### Changed

- live `sales_return_report` успешно выпущен через CubeJS после фикса query-forma под реальный `SalesReturn` contract;
- подтверждено, что рабочая query-forma для entity-layer использует:
  - measure `SalesReturn.returned_quantity_measure`
  - dimensions `SalesReturn.cause`, `SalesReturn.sku_id`, `SalesReturn.product_id`
  - time dimension `SalesReturn.returned_at`
- live данные в текущем окне пока очень скудные, поэтому следующий шаг не про интеграцию, а про насыщение слоя данными.

- Операционная аналитика переведена с накопительных продаж на анализ по окнам времени.
- В приоритете источников теперь:
  1. `CubeJS`
  2. `documents reports`
  3. `snapshots`
  4. historical seller/public data
- UI теперь адаптируется под тип отчёта, а не пытается одинаково рендерить все payload’ы.
- `official_*` bundles выравниваются через `refresh_operational_dashboard.py`, чтобы не терять новые UI-ready поля после рефакторингов.
- `get_sellers.py` теперь по умолчанию использует ненулевой `--sleep`.

### Fixed

- Убраны ложные winners, возникавшие от `1-2` продаж.
- Убраны ложные reorder recommendations по товарам без достаточного текущего сигнала.
- Исправлен UI-регресс, при котором `i`-подсказки торчали прямо в layout.
- Исправлены пустые `official` metadata:
  - окно периода
  - request ids
  - режим `reused`
- Убраны misleading long-range KPI вида:
  - `SKU всего = 0`
  - `Валовая прибыль = 0`
  - `Риск OOS = 0`
  для `cubejs_period_compare`
- Исправлен market UI, где раньше встречались строки `Без названия`.
- Исправлен индекс dashboard bundles:
  - актуальная структура верхнего уровня в `index.json` это `items`
- Исправлены технические регрессы market-модуля:
  - пропавший import `statistics`
  - shadowing локальной `summarize_market`
- В `get_sellers.py` добавлен retry/backoff на `403/429/5xx`, чтобы снизить риск rate limiting.

### Security

- Убрано опасное поведение с чрезмерно агрессивным обходом seller/public endpoints без задержки по умолчанию.

### Learned

- Накопительные продажи нельзя использовать как основной сигнал для закупки.
- Title-only сравнение слишком слабое для управленческих решений.
- По карточкам с несколькими вариантами нельзя принимать решения на уровне одной строки CSV.
- `documents/create` может стабильно давать `400 Validation failed`, поэтому fallback через `documents/requests` — это штатный, а не временный путь.
- `CubeJS` полезен для long-range и time-series анализа, но не все measures совместимы в одном запросе.
- Индекс доминирования полезен как сигнал насыщенности, но не как автоматический запрет на вход в сегмент.
- Большой блок `Прочее` в market layer означает не только “рынок странный”, но и то, что классификатор групп ещё надо улучшать.

### Do Not Repeat

- Не возвращать `sleep=0.0` как default для массового обхода каталога.
- Не показывать в UI только агрегаты без списка конкретных SKU там, где менеджеру нужно принимать решение.
- Не рендерить полные локальные пути и длинные URL как основное значение metadata.
- Не смешивать strategic и operational сигналы в один отчёт без маркировки.
- Не трактовать отсутствие historical reference window в CubeJS как реальное падение продаж.

## [unreleased] - 2026-04-25
### TASK-005: competitor_market group × price_band cross-tabulation and HHI by band
- Extended `analyze_competitor_market.py` with market concentration and coverage gap analysis
  - **New Core Module**: `core/market_crosstab.py` with six functions for advanced market analysis:
    - `calculate_hhi_by_band()`: HHI calculation by price band (0-10000 scale, high/moderate/fragmented profiles)
    - `build_group_price_band_crosstab()`: Group × Price band cross-tabulation (market vs shop SKU counts)
    - `identify_coverage_gaps()`: Coverage gap detection (shop-only, market-only, shared scenarios)
    - `calculate_entry_window_with_novelty_factoring()`: Novelty-adjusted entry window scoring
    - `apply_configurable_price_bands()`: Custom price band boundaries support
    - `add_coverage_gap_to_entry_windows()`: Coverage gap integration into entry window prioritization

  - **New CSV Outputs**:
    - `competitor_market_crosstab_{date_tag}.csv`: Group × Price band matrix with HHI by band
    - `hhi_by_price_band_{date_tag}.csv`: HHI with concentration profile classification
    - `competitor_market_coverage_gaps_{date_tag}.csv`: Coverage gaps with gap_score and market metrics

  - **Enhanced Entry Window Scoring**:
    - Novelty adjustment: +15 (fresh ≥65), +8 (moderate 40-65), or 0 (mature <40)
    - Priority score: (coverage_gap × 0.40) + (market_volume × 0.35) + (economics × 0.25)
    - New fields: `entry_window_score_adjusted`, `novelty_adjustment_factor`, `entry_priority_score`

  - **Configurable Price Bands**:
    - Default: [0-50, 50-200, 200-500, 500+]
    - Custom via CLI: `--price-band-boundaries 50 150 300 700`

  - **Smoke Tests**: `smoke_test_competitor_market_extended.py` validates all criteria (5/5 test cases pass)
