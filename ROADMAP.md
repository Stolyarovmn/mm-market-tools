# Roadmap

Дата актуализации: `2026-04-11`

## Цель проекта

Собрать модульный инструмент анализа и роста магазина на MM, который:

- даёт операционные решения по окнам времени;
- даёт стратегический слой по ассортименту, идеям и конкурентам;
- умеет работать через CLI и через браузерный UI;
- сохраняет нормализованные данные и понятные артефакты для человека и AI/LLM.

## Что уже сделано

### 1. Источники данных

- seller `documents reports`
- seller `CubeJS`
- публичный поиск по категории
- fallback через snapshots

### 2. Операционный слой

- weekly pipeline
- official reports analysis
- stricter winner / reorder logic
- family-level identity по `product_id` + `ШК` + `Seller SKU ID` + `SKU`

### 3. Стратегический слой

- анализ продавцов категории
- группировка ассортимента по товарным идеям
- growth plan
- market analysis по конкурентам
- ценовые коридоры и idea clusters в рыночном слое

### 4. Presentation слой

- `data/dashboard/*.json`
- индекс dashboard bundles
- статический браузерный UI
- светлая и тёмная тема
- отдельные режимы:
  - operational
  - market
  - long-range compare

## Текущие приоритеты

### P1. Конкурентный модуль

- добавить сравнение рынка с вашим магазином по группам и диапазонам цен
- расширить market layer от sample-view к более глубокой и устойчивой выборке
- подготовить market-specific action hints для расширения ассортимента
- дальше снижать долю `Прочее` в market-классификаторе
- отделить “реальный возраст карточек”, если удастся добыть `created_at`, от текущего proxy `novelty_proxy_index`
- развивать `entry_windows` слой:
  - `group x price_band`
  - HHI
  - novelty
  - price gap
  - приоритет окна входа
  - explicit decision `входить / тестировать / не входить / менять закупку`
  - coverage по вашей экономике, чтобы отличать хорошие окна от слепых зон

### P1. Identity и SKU-level управленческий слой

- использовать family-layer во всех спорных закупочных отчётах
- добавить отдельную диагностику:
  - где карточка жива, но отдельные ШК мёртвые
  - где карточка мертва целиком
  - где продажи размазаны по вариантам

### P1. Browser UI

- добавить фильтры по типу отчёта, группе и риску
- добавить market-specific drilldown по группам, продавцам и price bands
- развивать новый `Action Center`:
  - stateful watchlists
  - ручные задачи менеджера
  - быстрые кнопки из таблиц dashboard
  - owner/status discipline
  - saved views
  - change acknowledgements
- расширить explainability слой:
  - больше `i`-подсказок
  - понятные интерпретации KPI
  - decision-oriented визуализация ABC/XYZ
- развивать отдельный `refresh UI` для ручного online запуска jobs:
  - явное разделение `online` и `offline`
  - live status и live log
  - переходы к свежим артефактам после завершения job
  - product-like итог шага и переход в основной dashboard по свежему bundle
  - позже добавить более структурный progress model для долгих jobs
- поддерживать блок `Что изменилось` между соседними отчётами одного вида
- вынести `ui/app.js` в отдельные модули:
  - `api.js`
  - `state.js`
  - `dashboard_views.js`
  - `components.js`
- довести `dynamic_pricing` до полноценного dashboard flow:
  - отдельный report kind
  - запуск через refresh UI
  - дальше entity-level pricing drilldown и pricing history

### P1. Seller cabinet coverage

- закрыть gap между тем, что продавец реально видит в ЛК, и тем, что использует проект;
- статус на `2026-04-13`:
  - `PAID_STORAGE_REPORT` уже подключён офлайн и встроен в dashboard;
  - `SalesReturn` уже подключён офлайн и live-подтверждён в dashboard;
  - для `PAID_STORAGE_REPORT` live-слой всё ещё ждёт стабилизации documents API;
- ближайшие источники-кандидаты:
  - `SalesReturn` -> расширить live окно или накопить больше данных
  - `PAID_STORAGE_REPORT` -> повторить live run после стабилизации seller documents API
  - `PaidPromo*` CubeJS
- отдельно решить, нужен ли transactional слой по Seller API:
  - товары
  - цены
  - остатки
  - FBS workflow

### P1. Pricing / repricer

- сделать recommendation-first repricer:
  - собирать цены лидеров по группе и ценовому коридору;
  - предлагать безопасную цену в рамках `target margin`;
  - не делать auto-apply без отдельного safety layer и подтверждённого seller API flow.
- добавить marketing-аудит вокруг ценовых порогов:
  - `price trap` для SKU чуть выше психологических caps (`199`, `299`, `499`, `999`);
  - дальше соединить это с repricer, чтобы рекомендации учитывали не только маржу, но и видимость под фильтрами.
- добавить и развивать title/CTR аудит:
  - initial layer `title_seo_report` уже есть;
  - следующий шаг: связать его с карточечными entity pages и shortlist на ручной rewrite.
 - `ISSUE-013`:
   - initial unified layer `marketing_card_audit` уже есть;
   - следующий шаг: углубить его до entity pages, истории изменений по карточке и связки с Action Center.

## Следующие этапы

## Перенесённые ISSUE и backlog

Если `ISSUE` не взят в текущую итерацию, он не должен пропадать. Он обязан остаться либо здесь, либо в `CHANGELOG.md` под `Unreleased`.

### Carry-forward from auditor

- `ISSUE-001`
  - найти подтверждённый источник `created_at` товара и заменить proxy `novelty_proxy_index` на age-aware индекс дружелюбия для новичка;
  - до этого момента proxy-метрика остаётся допустимым временным слоем, но не финальным решением.
- `ISSUE-002`
  - уже закрыт proxy-слоем `sales velocity in stock days`;
  - следующий шаг: если появится более точный daily stock history, заменить proxy на более строгую модель потерь из-за OOS.
- `ISSUE-004`
  - расширять уже внедрённый `market_margin_fit`:
    - повышать coverage по группам и окнам входа;
    - отделять `нет данных` от реального `невыгодно`;
    - выводить sourcing-level рекомендации, а не только go/no-go.
- `ISSUE-005`
  - guard по `exp` уже добавлен;
  - если подтвердится стабильный refresh-flow, вынести best-effort refresh в отдельный auth-layer для future service mode.
- `ISSUE-006`
  - persistent backfill store уже добавлен;
  - следующий шаг: протянуть этот store и в `growth` / operational слой, а не только в market.
- `ISSUE-011`
  - добавить `price trap auditor` по вашим SKU;
  - сначала как audit/report layer без auto-apply;
  - потом, если данные подтвердят пользу, встроить в pricing workflow и Action Center.
- `ISSUE-012`
  - initial heuristic analyzer уже добавлен;
  - следующий шаг: углубить словарь noun/entity и связать title-аудит с `price_trap` и `dynamic_pricing` в единый marketing layer;
  - не превращать это в fake ranking model: держать как heuristic audit, а не “магический SEO score”.
- `ISSUE-013`
  - новый manager-facing unified layer уже добавлен:
    - `build_marketing_card_audit.py`
    - dashboard report kind `marketing_card_audit`
    - offline refresh job `marketing_card_audit`
  - следующий шаг:
    - развить follow-up workflow дальше:
      - причины решений;
      - change history по статусам;
      - acknowledgements и ручные review loops по сущности.
      - event-log управленческих решений по сущности;
      - затем saved views и owner/status discipline поверх Action Center.
- `ISSUE-014`
  - не взят в текущую итерацию, перенесён в backlog:
    - logistics fee auditor по границам веса/габаритов;
    - брать в работу только если подтвердится надёжный источник веса/размеров;
    - приоритет ниже текущего entity-history и follow-up workflow.
- `ISSUE-016`
  - media richness auditor:
    - сначала без тяжёлого CV;
    - базовый слой: количество фото/видео, visual gaps против конкурентов;
    - CV только если будет оправдан по сигналу, а не ради сложности.
  - статус:
    - initial heuristic layer реализован;
    - следующий шаг: competitor-relative visual benchmark не только против медианы группы, но и против похожих карточек.
- `ISSUE-017`
  - dimension-fee optimizer:
    - фактически тот же осторожный backlog, что и `ISSUE-014`;
    - не брать в реализацию без подтверждённого источника размеров/веса и привязки к тарифным границам MM.
  - статус:
    - создан research note;
    - кодовая реализация отложена до появления source-of-truth по `weight/dimensions`.
- `ISSUE-018`
  - description SEO richness:
    - проверить длину описания, thin content и базовую насыщенность ключами;
    - держать как heuristic audit, не как fake ranking model.
  - статус:
    - initial heuristic layer реализован;
    - следующий шаг: competitor-relative comparison против похожих карточек, а не только медианы группы.

### Собственные предложения Codex

- добавить `market_margin_fit` слой:
  - `group`
  - `price_band`
  - market median
  - your cogs / target margin
  - go / no-go по экономике;
- добавить в market UI более глубокий drilldown по shortlist-решениям:
  - список подниш, куда стоит заходить
  - список подниш, которые стоит тестировать
  - список подниш, где надо менять закупку, а не ассортимент;
- поверх `blind spots` построить operational loop:
  - backlog по заполнению себестоимости;
  - контроль, какие группы уже закрыты по cost coverage;
  - автоматическая переоценка `validate_economics` после добора cost-данных;
  - отдельный SKU-level registry по `cogs = 0`;
  - CSV-шаблон для ручного заполнения себестоимости и последующего re-score;
  - persistent override store для заполненной себестоимости;
  - следующий шаг после этого: научить не только market, но и operational/growth pipeline использовать этот store без ручной проклейки;
- добавить второй проход классификации рынка для общих title вроде `игрушечная машина`, `набор продуктов`, `брелок`, чтобы снижать шумные попадания в широкие группы;
- дотянуть `core/http_client.py` и `core/auth.py` в оставшиеся неактивные или legacy-скрипты, чтобы вообще убрать расхождение сетевого контракта;
- начать версионировать dashboard schema, потому что `data/dashboard/*.json` уже фактически стало публичным внутренним контрактом.
- продолжать поддерживать `schema_version` и миграции старых bundle’ов при несовместимых изменениях.
- держать `index.json` в совместимом dual contract:
  - `items` для основного UI
  - `reports` как alias для audit/test-слоя

### P2. История и сезонность

- копить history bundles по неделям и месяцам
- добавить history-aware compare в UI
- подготовить базу для `XYZ` и seasonal анализа

### P2. Нормализованный data layer

- формализовать `data/raw`, `data/normalized`, `data/dashboard`
- описать schema/contracts для dashboard payloads
- добавить fixtures/sample data для smoke tests
- держать в актуальном состоянии `CHANGELOG.md`, чтобы не повторять уже исправленные ошибки и спорные решения
- каждую итерацию оформлять через `Keep a Changelog` + `SemVer`, а не свободными заметками
- продолжать вынос сетевой логики в `core/http_client.py` и `core/auth.py`, чтобы активные модули пользовались единым контрактом

### P2. Метрики торговли

- расширить ABC к family-level
- подготовить `XYZ-ready` слой
- добавить price ladder / price corridor по вашим группам
- добавить stale stock severity score
- углубить `growth_plan.py`, чтобы он опирался не только на historical demand, но и на operational window-awareness

### P3. Interactive product

- backend/API слой для UI
- scheduled refresh отчётов
- сохранение сессий анализа
- action lists с ручными заметками менеджера

## Что не трогать без причины

- `weekly_operational_report.py` fallback через `documents/requests`
- strict logic, убирающую ложные winners по `1-2` продажам
- разделение на strategic и operational слои

## Что считать legacy

- `analyze_products.py`
- title-only части старых сравнений, если они используются для закупки, а не для rough scouting
