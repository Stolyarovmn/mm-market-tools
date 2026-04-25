# GitHub-native Operating Model

`mm-market-tools` использует GitHub-native процесс вместо файлового control plane.

Это означает:

- `Issues` являются каноническим контейнером задач, блокеров и formal disputes.
- `Projects` являются каноническим местом для live status.
- `Pull Requests` являются execution artifact, а не каноном задачи.
- `Discussions` нужны для RFC, onboarding и предварительных дебатов, но не заменяют formal dispute.
- `GitHub Pages` расширяет уже существующий магазинный UI и даёт lightweight process-view, а не второй отдельный dashboard.

## Что мы берём из v4 только как принципы

- evidence-first verification;
- retry / blocker / dispute discipline;
- fresh-agent continuity без скрытой чат-истории;
- минимальный набор ролей: orchestrator, executor, auditor;
- любое системное решение должно оставлять явный артефакт.

## Что не переносится буквально

- tmux/inbox/outbox/watchdog;
- локальные `TASK-XXX.md` как канон;
- отдельный файловый `STATE.md`, если GitHub уже выражает то же нативно;
- второй process dashboard поверх текущего Pages UI.

## GitHub mapping

- `type:task` issue: основная рабочая задача
- `type:dispute` issue: formal dispute
- `type:process-change` issue: изменение процесса
- `type:blocker` issue: blocker/escalation

## Status contract

Канонический lifecycle задаётся в GitHub Projects:

- `QUEUED`
- `IN_PROGRESS`
- `REVIEW`
- `DONE`
- `BLOCKED`

Если Project field ещё не настроен, допустим временный fallback через labels:

- `status:queued`
- `status:in_progress`
- `status:review`
- `status:done`
- `status:blocked`

## Pages process view

`docs/process.html` показывает:

- task queue
- review/audit queue
- disputes
- open PRs
- latest workflow health
- memory/docs links

Этот view только отражает состояние GitHub и docs.
Редактирование канонических данных происходит в самих GitHub issues, projects, PR и repo docs.

