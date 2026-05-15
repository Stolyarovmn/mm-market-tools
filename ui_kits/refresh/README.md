# Refresh runner UI kit

Recreation of `ui/refresh.html` from `Stolyarovmn/mm-market-tools` — the local web runner that triggers MM API jobs from a browser when the agent session can't reach the API directly.

## Files

| File         | Purpose                                                              |
|--------------|----------------------------------------------------------------------|
| `index.html` | Entry — same chrome as the dashboard kit, plus the progress-bar CSS. |
| `App.jsx`    | One-file composed view — every panel `ui/refresh.html` exposes.      |
| `data.js`    | Fixture: status, token meta, jobs, current run + log, recent runs.   |

## What's covered

- Hero with theme toggle, focus-mode toggle (`⊞ Фокус`) and back link.
- Sticky "Панель запуска" with quick status.
- Token panel with inline input + toolbar.
- Workflow guide (`1. Подключиться → 2. Запустить → 3. Дождаться → 4. Вернуться`) as tone-haloed insight cards.
- Online + offline job groups, each card showing date-range form and primary action.
- Current run panel: meta-grid + indeterminate `progress-fill` bar + mono log block.
- Recent runs grid with `Running` / `Succeeded` / `Failed` badges.

## What's intentionally not covered

- The full job-parameter forms — only date-range is shown; the live runner exposes 5–12 fields per job. Add them in `JobCard` if you need them.
- Live SSE log streaming + per-run history nav.
- Targeted-pulse animation on deep-linked job cards (the source includes a `@keyframes targeted-pulse`; the kit has the visual surface but not the deep-link trigger).
