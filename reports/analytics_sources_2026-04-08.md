# Новые источники аналитики

Дата: 2026-04-08

На основе изученных запросов появились два более сильных источника данных, чем просто накопительный `quantitySold`.

## 1. CubeJS analytics

Endpoint:

- `https://seller-analytics.mm.ru/cubejs-api/v1/load`

Пример запроса показывает:

- можно задавать `measures`;
- можно задавать `timeDimensions`;
- можно задавать `dateRange`;
- можно фильтровать по `Sales.shop_id`;
- можно работать в `Europe/Moscow`.

Пример меры из реального запроса:

- `Sales.seller_revenue_without_delivery_measure`

Что это значит practically:

- источник уже умеет считать метрики в рамках временного окна;
- это лучше, чем опираться только на общий накопительный счётчик;
- отсюда можно строить дневные, недельные и месячные отчёты.

## 2. Documents reports

Endpoints:

- `GET /api/seller/documents/requests`
- `POST /api/seller/documents/create`

Подтверждённые job types из реальных данных:

- `LEFT_OUT_REPORT`
- `SELLS_REPORT`

Что видно по `SELLS_REPORT`:

- поддерживает `dateFrom`
- поддерживает `dateTo`
- поддерживает `group`
- поддерживает `returns`
- поддерживает `shopIds`
- возвращает CSV через готовую ссылку

Это особенно важно, потому что `SELLS_REPORT` решает как раз проблему "товар продавался давно, но сейчас уже не продаётся".

## Вывод

Для проекта теперь правильная иерархия источников такая:

1. `seller-analytics CubeJS` и `documents reports` для анализа по времени
2. `snapshot_shop.py` как fallback, если аналитика напрямую недоступна
3. накопительные seller/public данные только как исторический слой

## Что добавлено в проект

- `cubejs_query.py`
- `request_document_report.py`

Оба инструмента сделаны как CLI-обёртки под эти источники.
