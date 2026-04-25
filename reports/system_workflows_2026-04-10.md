# System Workflows 2026-04-10

## Нужна ли БД

Коротко: да, потребность уже появляется, но не для немедленного big-bang migration.

### Почему уже появляется

- растёт число сущностей:
  - dashboard bundles
  - history
  - action center
  - events
  - cogs overrides
  - saved views
- уже есть stateful workflow, а не только генерация файлов
- нужен более удобный доступ для:
  - history by entity
  - queues by owner/status
  - time-series by report kind
  - dedup / joins / audit trail

### Почему не надо бросаться в БД прямо сейчас

- текущий file-based слой всё ещё понятен и дебажен;
- проект пока mostly single-user/local-first;
- резкий переход на DB легко сломает совместимость и простоту;
- UI и workflow ещё формируются, schema стабилизируется.

### Правильный следующий ход

Не “переписать всё на Postgres”, а сделать staged path:

1. formalize file contracts
2. ввести repository layer
3. подготовить optional SQLite backend
4. сначала перенести stateful слои:
   - action center
   - entity history
   - cogs overrides
   - saved views
5. отчёты и dashboard bundles пока оставить file-first

### Вывод

Да, БД станет удобнее для меня и для продукта.

Но сейчас оптимален не full migration, а:

- `JSON files as canonical reports`
- `SQLite as optional state/query layer`

## Схема получения данных и формирования отчётов

```mermaid
flowchart TD
    A[MM Public API] --> N1[Market Scans]
    B[Seller Documents API] --> N2[Official CSV Reports]
    C[Seller CubeJS] --> N3[Long-range Analytics]
    D[Manual COGS Fill] --> N4[COGS Overrides]
    E[Snapshots] --> N5[Fallback Time Windows]

    N1 --> R1[data/raw]
    N2 --> R1
    N3 --> R1
    N4 --> R2[data/local]
    N5 --> R1

    R1 --> P1[Normalization / core]
    R2 --> P1

    P1 --> G1[Operational Reports]
    P1 --> G2[Market Reports]
    P1 --> G3[Pricing Reports]
    P1 --> G4[Marketing Audit]
    P1 --> G5[Entity History Index]

    G1 --> D1[data/dashboard]
    G2 --> D1
    G3 --> D1
    G4 --> D1
    G5 --> D2[data/local/entity_history_index.json]

    D1 --> U1[Dashboard UI]
    D2 --> U1
    R2 --> U1
```

## Схема управленческих действий на основе дашборда

```mermaid
flowchart TD
    A[Дашборд / Report Selector] --> B{Тип сигнала}

    B -->|Operational| C[Риск OOS / Залежи / Прибыль]
    B -->|Market| D[HHI / Entry Windows / Margin Fit]
    B -->|Marketing| E[Price Trap / Title SEO / Card Audit]

    C --> F[Добавить в Watchlist]
    C --> G[Создать задачу]
    D --> F
    D --> G
    E --> F
    E --> G

    F --> H[Action Center]
    G --> H

    H --> I[Назначить owner]
    H --> J[Поставить статус]
    H --> K[Сохранить view]

    I --> L[Entity Detail Panel]
    J --> L
    K --> L

    L --> M[Подтвердить разбор]
    M --> N[Event Log / Management History]

    N --> O[Следующая итерация решений]
```

## Что делать дальше

Следующий логичный продуктовый шаг:

1. repository layer
2. optional SQLite
3. entity manager pages
4. queues by owner/status/view
