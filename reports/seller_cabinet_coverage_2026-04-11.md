# Seller Cabinet Coverage Audit

Дата: `2026-04-11`

## Цель

Понять:

- какие данные и отчёты доступны продавцу в личном кабинете Магнит Маркета;
- какие из них уже забирает проект `mm-market-tools`;
- какие данные подтверждены через API;
- где у нас есть gap между возможностями кабинета и текущим data-layer.

## Источники

Официальная документация:

- Личный кабинет продавца: `https://seller-manual.mm.ru/personal-account`
- Seller API: `https://seller-manual.mm.ru/magnit-market-seller-api`
- Отчёт по оборачиваемости и остаткам: `https://seller-manual.mm.ru/stock-and-turnover-report`
- Отчёт по реализации: `https://seller-manual.mm.ru/sales-report`
- Отчёт по оплаченным услугам: `https://seller-manual.mm.ru/paid-services-report`
- Недельная email-отчётность: `https://seller-manual.mm.ru/weekly-email-report`
- Товары с истекающим сроком годности: `https://seller-manual.mm.ru/products-expiring-shelf-life`

Live API introspection по текущему seller token:

- `GET https://api.business.kazanexpress.ru/api/seller/documents/requests?page=0&size=200`
- `GET https://seller-analytics.mm.ru/cubejs-api/v1/meta`

Локальные источники проекта:

- `core/documents_api.py`
- `core/cubejs_api.py`
- `request_document_report.py`
- `reports/analytics_sources_2026-04-08.md`

## Что доступно продавцу в личном кабинете

### 1. Аналитика

По разделу `6.3 Аналитика` и смежным разделам кабинета продавец видит:

- продажи, выручку и прибыль;
- заказы;
- средний чек;
- возвраты и причины возвратов;
- динамику по временным окнам;
- разрезы вплоть до категории / товара / SKU;
- рекламную аналитику и paid promo контуры;
- разрезы по FBS / FBO.

### 2. Отчёты

По разделу `6.4 Отчеты` в личном кабинете есть:

- отчёт по оборачиваемости и остаткам;
- отчёт по реализации;
- отчёт по оплаченным услугам;
- еженедельная email-отчётность;
- товары с истекающим сроком годности.

### 3. Товарный и операционный кабинет

По разделам кабинета и Seller API продавец также работает с:

- товарами и карточками;
- ценами;
- остатками;
- активными магазинами;
- FBS заказами и отгрузками;
- этикетками;
- отзывами;
- чатом с покупателями;
- акциями и продвижением.

## Что подтверждено через API

### Documents API

Live `documents/requests` по текущему магазину подтвердил:

- `SELLS_REPORT`
- `PAID_STORAGE_REPORT`

Это фактически доказывает, что хотя бы часть кабинета `Отчёты` доступна через seller documents API.

Дополнительно в проекте уже есть историческое подтверждение `LEFT_OUT_REPORT` как рабочего job type, но в последних `200` запросах именно этого аккаунта он не встретился.

### CubeJS analytics

Live `cubejs-api/v1/meta` подтвердил наличие доступных аналитических кубов:

- `Sales`
- `SalesReturn`
- `CategoryHierarchy`
- `PaidPromoAtcFunnel`
- `PaidPromoFunnel`
- `PaidPromoOrderFunnel`
- `PaidPromoV2Funnel`
- `PaidPromoBet`

Из этого следует:

- кабинетная аналитика реально торчит наружу через аналитическое API;
- через API доступны продажи, возвраты, категории, shop/product/sku dimensions;
- доступна и рекламная аналитика по paid promo.

### Seller API

Официальная документация Seller API подтверждает автоматизацию:

- товаров;
- цен;
- остатков;
- магазинов;
- FBS заказов;
- этикеток.

## Что уже использует проект

### Уже используем

1. `SELLS_REPORT`
   - используется в `weekly_operational_report.py`
   - используется в `analyze_official_reports.py`

2. `LEFT_OUT_REPORT`
   - используется в operational pipeline проекта
   - является одним из ключевых источников для остатков / движения / OOS-логики

3. `CubeJS / Sales`
   - используется через `cubejs_query.py`
   - используется через `cubejs_period_compare.py`
   - даёт long-range compare, revenue, profit, orders, units

4. Публичные рыночные данные
   - category search
   - product pages
   - seller samples

### Частично используем / используем косвенно

1. Возвраты
   - частично через `SELLS_REPORT` и `returns`
   - частично через `SalesReturn` косвенно, но не развёрнуты в отдельный manager-facing слой

2. Карточки / товары / конкуренты
   - используем в market/product benchmark слое
   - не используем seller cabinet API для массового управления товарами

### Не используем, хотя это видно в кабинете или API

1. `PAID_STORAGE_REPORT`
   - отчёт по оплаченным услугам / платному хранению
   - в проекте не интегрирован

2. Paid promo analytics
   - `PaidPromo*` кубы видны в CubeJS meta
   - в проекте нет рекламного ROAS/DRR/CPA слоя

3. Причины возвратов как отдельный слой
   - `SalesReturn` виден в API
   - manager-facing отчёт по причинам возврата не реализован

4. Еженедельная email-отчётность
   - в проекте не интегрирована
   - отдельный API endpoint не подтверждён

5. Товары с истекающим сроком годности
   - в проекте не интегрированы
   - отдельный API endpoint не подтверждён

6. Отзывы
   - в проекте не интегрированы
   - seller API coverage не подтверждает этот слой

7. Чат с покупателями
   - в проекте не интегрирован
   - seller API coverage не подтверждает этот слой

8. Управление товарами / ценами / остатками через seller cabinet API
   - seller API это умеет по документации
   - текущий проект пока делает упор на аналитику, а не на transactional sync layer

## Матрица покрытия

### Полностью покрыто сейчас

- продажи и выручка по official reports
- остатки / движение / OOS operational слой
- long-range sales analytics через CubeJS
- market / pricing / content manager-facing аналитика

### Покрыто частично

- возвраты
- карточечный management loop
- ассортиментный слой

### Не покрыто

- paid services / paid storage economics
- paid promo analytics
- отзывы
- чат
- expiring shelf life
- seller-side transactional управление товарами / ценами / остатками через официальный seller API

## Что можно выдернуть через API

### Подтверждено

- official reports через `documents`
- sales / returns / promo analytics через `CubeJS`
- товары / цены / остатки / FBS операции через Seller API documentation

### Не подтверждено на сегодня

- weekly email report через API
- expiring shelf life через API
- отзывы через API
- чат с покупателем через API

## Главный вывод

Проект уже хорошо закрывает:

- operational аналитику;
- sales analytics;
- market / pricing / content decision layer.

Но проект пока **не использует весь объём данных и функций seller cabinet**.

Самые большие реальные gaps сейчас:

1. `PAID_STORAGE_REPORT` / paid services economics
2. paid promo analytics из `PaidPromo*` кубов
3. `SalesReturn` как отдельный слой причин возвратов
4. transactional Seller API для товаров / цен / остатков / FBS

## Рекомендуемый следующий порядок

1. Добавить `PAID_STORAGE_REPORT` как новый report kind и manager-facing экран затрат.
2. Добавить `SalesReturn` слой:
   - причины возвратов;
   - SKU / category hotspots;
   - риск повторных возвратов.
3. Добавить paid promo dashboard из `PaidPromo*` CubeJS:
   - показы
   - клики
   - расходы
   - заказы
   - выручка
   - DRR / CPA / CPO
4. Отдельно решить, нужен ли transactional seller API слой:
   - цены
   - остатки
   - карточки
   - FBS workflow.

## Замечание по refresh token

В проекте пока нет подтверждённого и реализованного refresh-flow для seller access token.

На сегодня подтверждено:

- access token живёт ограниченное время;
- проект умеет проверять TTL и предупреждать о near-expiry;
- automatic refresh пока не реализован и не должен считаться надёжным без подтверждённого endpoint contract.
