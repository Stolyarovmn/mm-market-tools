# Project Fields

## Canonical fields

### Status

Обязательное поле статуса:

- `QUEUED`
- `IN_PROGRESS`
- `REVIEW`
- `DONE`
- `BLOCKED`

### Role owner

- `orchestrator`
- `executor`
- `auditor`
- `unassigned`

### Retry count

Целое число, отражающее количество возвратов после audit/review fail.

### Needs audit

- `yes`
- `no`

### Priority

- `high`
- `medium`
- `low`

### Target

Короткая зона ответственности:

- `ui`
- `analytics`
- `refresh-runner`
- `github-process`

### Dispute linked

- `yes`
- `no`

## Rules

- `Status` — главный статусный источник.
- Labels используются как вспомогательные маркеры, а не как канонический live state.
- Если Project field временно недоступен, fallback даётся через `status:*` labels.

