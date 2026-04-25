# Consistency Audit

Дата: `2026-04-10`

## Scope

Проверялись:

- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- project memory
- `issues.md`
- `disagreements_2026-04-09.md`
- main UI
- refresh runner UI
- dashboard/index contracts

## Что согласуется корректно

### 1. Issue tracking

- `ISSUE-002` и `ISSUE-005` теперь согласованы между:
  - `issues.md`
  - `disagreements_2026-04-09.md`
  - `CHANGELOG.md`
  - кодом

### 2. Dashboard schema

- `schema_version` теперь реально существует в bundles и index.
- Это отражено в:
  - `README.md`
  - `ROADMAP.md`
  - `CHANGELOG.md`
  - memory

### 3. Refresh workflow

- split workflow `analysis in main workspace / online refresh in separate network session` уже согласован между:
  - кодом
  - `README.md`
  - refresh UI

### 4. Action Center

- новый stateful слой есть одновременно:
  - в коде
  - в main UI
  - в `CHANGELOG.md`
  - в memory

## Что было найдено и уже исправлено

### 1. Stale refresh runner process

Симптом:

- новый UI ожидал `/api/action-center`, но живой runner был старым процессом без этого endpoint.

Почему это важно:

- пользователь видит “UI сломан”, хотя на самом деле запущен старый server process.

Статус:

- подтверждено;
- процесс перезапущен на новом коде;
- live API тесты после этого прошли.

### 2. Index rebuild ambiguity

Симптом:

- при запуске `build_dashboard_index.py` по абсолютному пути индекс один раз оказался собран не из того import-context.

Статус:

- исправлено через явный `sys.path` bootstrap в `build_dashboard_index.py`.

## Остаточные замечания

### 1. `app.js` остаётся большим

- Это уже не авария, но всё ещё техдолг.
- В `issues.md` это теперь отражено через `ISSUE-007`.

### 2. Не все исследовательские скрипты должны идти в UI

- Это не inconsistency, а важно зафиксированное решение.
- Coverage audit подтверждает, что часть функций правильно оставить CLI-only.

### 3. Live browser QA всё ещё частично ручная

- Синтаксис, API и local contracts уже проверены.
- Но реальный DOM-UX по кнопкам и flow всё ещё требует manual click-through.

## Итог

Критических конфликтов между документацией, issue-слоем и кодом сейчас не найдено.

Главные практические выводы:

- после обновления runner его нужно перезапускать;
- dashboard/index contract теперь достаточно стабилен, чтобы строить на нём следующий UI-слой;
- проект уже ближе к “продукту”, чем к “набору скриптов”, но JS modularization и manual QA остаются следующим естественным этапом.
