# Исследование системы и аналогов 2026-04-10

## Контекст

Цель этого исследования:

- понять, чего не хватает `mm-market-tools` как системе анализа и роста магазина;
- сравнить проект с системами, которые уже помогают продавцам на маркетплейсах;
- отдельно посмотреть на решения вокруг Магнит Маркета / бывшего KazanExpress;
- определить, что нужно перенять, а что не нужно копировать.

## Что было изучено

### Официальный контур Магнит Маркета

- [Личный кабинет продавца: маркетинг и продвижение](https://seller-manual.mm.ru/personal-account)
- [Условия работы: оборачиваемость и платное хранение](https://seller-manual.mm.ru/terms)
- [Seller landing](https://seller.mm.ru/)

### Сервисы под Магнит Маркет

- [MarketDB](https://marketdb.pro/)
- [DaData MM](https://mm.dadata.io/)
- [SoykaSoft Magnit Market](https://soykasoft.ru/features/sistema-analitiki-magnitmarket/)
- [SellerFox Magnit Market](https://sellerden.ru/sellerfox/analitika-magnit-market/)

### Системы со зрелыми best practices в seller analytics

- [sellerboard alerts](https://sellerboard.com/en/alerts)
- [sellerboard inventory](https://sellerboard.com/en/inventory)
- [Marketplace Analytics](https://www.marketplaceanalytics.io/)
- [CompeteRadar](https://competeradar.com/)

## Что уже умеют зрелые системы

### 1. Не только отчёты, а action center

У зрелых систем аналитика не заканчивается графиком.

Что видно у аналогов:

- `sellerboard` делает alert dashboard, где сигналы можно приоритизировать, фильтровать и помечать как обработанные.
- `sellerboard inventory` строит reorder planning не только по продажам, но и по lead time, сезонности и предпочтениям по ликвидности.
- `Marketplace Analytics` делает per-product view с окнами `7D/30D/90D`, stock/risk monitoring и track coverage.

Вывод для нас:

- нам не хватает полноценного `action center`, а не просто списков в dashboard;
- нужен слой `assigned / resolved / snoozed / note`, иначе сигналы остаются одноразовым чтением.

### 2. Системы выигрывают не количеством виджетов, а качеством сигнала

Лучшие продукты подчёркивают:

- мало шума;
- больше конкретных сигналов;
- понятная интерпретация;
- фокус на рабочем наборе SKU, а не на всём каталоге сразу.

Это видно у [Marketplace Analytics](https://www.marketplaceanalytics.io/): они прямо противопоставляют себя «перегруженным dashboard».

Вывод для нас:

- это подтверждает правильность нашего курса на `strict`, `soft signals`, `blind spots`, `entry windows`;
- но UI всё ещё местами перегружен блоками и недостаточно превращает цифры в очередность действий.

### 3. У сильных систем есть отдельный слой alerts

Что важно у [sellerboard alerts](https://sellerboard.com/en/alerts):

- listing changes;
- stock shortage alerts;
- fee changes;
- configurable notifications;
- resolution workflow.

Вывод для нас:

- в `mm-market-tools` нет нормального alerting-слоя;
- есть аналитика, но почти нет событийной модели;
- это одна из самых больших функциональных дыр проекта.

### 4. У MM-специализированных сервисов сильная сторона — внешняя аналитика рынка

Что видно у [MarketDB](https://marketdb.pro/) и [DaData MM](https://mm.dadata.io/):

- аналитика категорий;
- аналитика продавцов;
- история позиций;
- похожие товары конкурентов;
- поиск ниш;
- ежедневное наблюдение рынка;
- browser extension прямо поверх каталога.

Вывод для нас:

- наш market-layer уже идёт в правильную сторону;
- но мы пока слабее в:
  - истории позиций карточек;
  - browser augmentation поверх каталога;
  - постоянном внешнем мониторинге изменений конкурентов;
  - карточке конкурента как отдельной сущности.

### 5. У более «финансовых» систем сильнее управленческий слой

Это видно у [SoykaSoft](https://soykasoft.ru/features/sistema-analitiki-magnitmarket/):

- чистая прибыль;
- возвраты;
- сезонность;
- ABC;
- остатки и оборачиваемость;
- конверсия карточек;
- планирование закупок;
- единое окно по нескольким площадкам.

Вывод для нас:

- наш operational и economics слой уже сильный концептуально;
- но он пока уступает по:
  - план-факт логике;
  - сценарному планированию закупок;
  - multi-market consolidation;
  - постоянному управленческому учёту.

## Что у нас уже сильнее, чем у части аналогов

### 1. Прозрачность методологии

У большинства коммерческих сервисов продающая подача сильнее инженерной.

У нас плюс в том, что:

- есть `METHODOLOGY.md`;
- явно разделены strategic / operational слои;
- есть `CHANGELOG`, `ROADMAP`, memory и audit loop;
- спорные метрики обсуждаются и фиксируются отдельно.

Это серьёзное преимущество для AI-assisted системы.

### 2. Модульность данных

У нас уже есть:

- `data/raw`
- `data/normalized`
- `data/dashboard`
- `data/local`

И это ближе к внутренней data-platform логике, чем к “скриптам на коленке”.

### 3. Честное отношение к ограничениям

Мы уже правильно не притворяемся, что:

- `novelty_proxy_index` это реальный возраст карточек;
- cumulative sales = current demand;
- отсутствие cost данных = плохая экономика.

Это важнее, чем выглядит: многие системы продают красивую уверенность там, где данных не хватает.

## Чего у нас не хватает

### Критично

1. `Action center`
2. `Alerting`
3. `Saved views / presets`
4. `Entity pages`
   Сейчас много агрегатов, но мало устойчивых сущностей:
   - страница SKU
   - страница семейства
   - страница конкурента
   - страница подниши
5. `Historical monitoring loop`
   Сейчас history уже начинается, но ещё нет зрелого слоя:
   - snapshot cadence
   - trend diffing
   - anomaly detection
6. `Task/state layer`
   Нужны статусы сигналов:
   - new
   - in review
   - resolved
   - ignored with reason

### Важно, но не срочно

1. `Role-oriented views`
   Сейчас dashboard один и тот же для владельца, аналитика и менеджера.
2. `Annotation layer`
   Нужны заметки “почему приняли решение”, особенно для pricing и закупки.
3. `Card quality scoring`
   Сейчас карточки анализируются разово, но нет постоянного quality score по фото / атрибутам / отзывам / цене.
4. `Competitor watchlists`
   Пока есть сканы рынка, но нет постоянного списка “кого смотреть каждый день”.
5. `Sourcing planner`
   Мы уже вышли на `market margin fit`, следующий логичный слой — не просто no-go, а “какой cogs нужен, чтобы зайти в окно”.

## Что у нас лишнее или рискованно

### 1. Слишком много report variants одного семейства

Сейчас в dashboard есть несколько `official_*` и несколько `market_*`.

Это нормально на этапе R&D, но для продукта риск:

- пользователь путается;
- один и тот же смысл размазан по нескольким bundle;
- индекс становится тяжёлым.

Нужно:

- ввести канонические report types;
- старые варианты уводить в `legacy`;
- держать для UI только product-ready варианты.

### 2. Часть логики ещё слишком file-centric

Система уже почти platform-like, но workflows ещё местами держатся на “возьми этот json, потом тот csv”.

Нужно сильнее двигаться к:

- named datasets;
- registry latest artifacts;
- job outputs with explicit links.

## Что нужно изменить в архитектуре

### 1. Ввести job registry как first-class layer

Мы уже начали это через `web_refresh_server.py`.

Следующий шаг:

- сделать canonical outputs per job;
- записывать ссылки на артефакты;
- показывать их в UI после завершения.

### 2. Ввести versioned dashboard schema

Это уже давно просится.

Иначе:

- старые bundle ломают UI;
- приходится угадывать report kind по имени файла;
- smoke tests ловят слишком поздно.

### 3. Разделить UI на три продукта

Сейчас один экран пытается быть всем сразу.

Лучше:

- `Control Room` — ежедневные сигналы и действия
- `Market Research` — рынок, конкуренты, ниши
- `History & Planning` — long-range, сезонность, закупка

### 4. Сделать stateful watchlists

Нужны отдельные списки:

- SKU watchlist
- family watchlist
- competitor watchlist
- niche watchlist

## UI review: что хорошо сейчас

### Хорошо

- есть тёмная тема;
- есть explainability через `i`;
- есть разделение `operational / market / compare`;
- ABC стал полезнее после добавления конкретных SKU;
- есть browser-first способ читать уже готовые bundles;
- появился refresh UI для ручного запуска jobs.

## UI review: что плохо сейчас

### Плохо

1. Один экран слишком длинный
2. Недостаточно sticky navigation
3. Нет нормального разделения по ролям
4. Нет явного `what changed since last refresh`
5. Нет action state
6. Нет deep links в конкретные сущности
7. Нет obvious artifact links after refresh jobs
8. Недостаточно visual hierarchy между:
   - KPI
   - signal
   - action
   - evidence

## Что нужно перенять в UI

### Из зрелых систем стоит перенять

1. `Alert center`
2. `Per-entity pages`
3. `7D / 30D / 90D` toggles на ключевых сущностях
4. `Saved views`
5. `Watchlists`
6. `Action resolution`
7. `Historical change cards`
8. `Post-refresh artifact links`

## Что не стоит копировать

1. Маркетинговый шум и обещания точности без источников
2. Перегруженные таблицы ради “больше данных”
3. Сырые score-модели без объяснения
4. Подмену неизвестных данных красивыми proxy без маркировки

## Конкретный gap-analysis по MM Market Tools

### Следующий обязательный слой

1. `JWT guard`
2. `True sales velocity without OOS days`
3. `Action center`
4. `Artifact-aware refresh runner`
5. `Versioned dashboard schema`
6. `Watchlists`
7. `Entity pages`
8. `Alerts`

### Что можно отложить

1. Multi-market consolidation
2. Полноценный auto-refresh token manager
3. Browser extension поверх каталога
4. Enterprise-style repricing engine

## Главный вывод

`mm-market-tools` уже перерос стадию “набора скриптов” и движется в сторону внутренней operating system для продавца на MM.

Сильные стороны проекта:

- честная методология;
- модульность;
- разделение strategic / operational;
- сильный economics слой;
- уже заметно более инженерный подход, чем у многих «витринных» сервисов.

Главная слабость сейчас не в аналитических формулах, а в productization:

- signals есть;
- decisions уже появляются;
- но workflow по ним ещё недостаточно stateful, persistent и role-oriented.

Если коротко:

- как `analysis engine` проект уже интересный;
- как `daily operator product` ему ещё нужен полноценный action layer.
