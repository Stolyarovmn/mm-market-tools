# Labels Schema

## Type labels

- `type:task`
- `type:dispute`
- `type:process-change`
- `type:blocker`

## Status labels

Используются как fallback, пока GitHub Project ещё не стал единственным статусным источником:

- `status:queued`
- `status:in_progress`
- `status:review`
- `status:done`
- `status:blocked`

## Helper labels

- `needs:audit`
- `needs:triage`
- `area:ui`
- `area:analytics`
- `area:refresh-runner`
- `area:github-process`
- `priority:high`
- `priority:medium`
- `priority:low`

## Rules

- На issue должен быть ровно один `type:*`.
- `status:*` не должен дублировать несколько состояний одновременно.
- Formal dispute без `type:dispute` считается обычным обсуждением, а не спором.

