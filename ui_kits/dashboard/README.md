# Dashboard UI kit

Pixel-faithful recreation of `ui/index.html` from `Stolyarovmn/mm-market-tools` — the analyst-facing dashboard. Built as small, reusable React components that mirror the live class names in `ui/styles.css`, so styles drop in without remapping.

## Files

| File              | Purpose                                                                 |
|-------------------|-------------------------------------------------------------------------|
| `index.html`      | Entry — loads tokens + source stylesheet + React + Babel.               |
| `components.jsx`  | Atom + card library: `Hero`, `Panel`, `KpiCard`, `Badge`, `Delta`, `MiniButton`, `ActionList`, `MiniTableCard`, `BarChartCard`, `SparklineCard`, `AbcCard`, `CompareCard`, `PriorityCard`, `InsightCard`, `FlowCard`, `ReviewCard`, `QuickWinCard`, `WatchlistCard`, `ManualActionsCard`, `ActionCenterStatusCard`, `QueueByBars`, `SavedViewsCard`, `EntityDetail`. |
| `App.jsx`         | Composed dashboard — every section the live UI exposes for `weekly_operational_report`. |
| `data.js`         | One fixture, shaped like the live dashboard JSON. Edit to explore states. |

## Two modes — Quick wins vs Full analyst view

The kit now opens in **«Сейчас»** by default — a focused entry point built for the 15-30 minute working session. The mode pill in the hero (left of the theme toggle) flips between:

- **«Сейчас»** — Quick wins backlog · Сводка · Top-4 KPI · Приоритеты Сейчас · Действия · 2 свежих отзыва. One scroll, one cycle.
- **«Полный режим»** — Everything above, plus Карта Flow'ов, Что Изменилось, Сравнение Периодов, Центр действий, Очереди дальнейших действий, Карточка и история, четыре mini-tables, Распределения (bars + ABC), и История По Месяцам.

The mode preference is not persisted — the dashboard always opens in «Сейчас» as agreed.

### Quick wins backlog mechanics

- The backlog holds **N quick-win cards** (currently 8 in the fixture). The strip shows the top 4 by priority.
- Each card carries a **time estimate computed from its `kind` and `count`** — see `estimateMin()` in `components.jsx`. Edit the table there, not in data.
- Subtitle of the strip totals visible minutes: *"4 действия в очереди — примерно 19 мин на всё."*
- Each card has two actions: the primary (`Открыть список`, `К отзывам`…) and **`✓ Готово`**.
- Clicking **`✓ Готово`** removes the card from the strip; the next-priority backlog item slides into its place. A counter appears below: *"Готово за сессию: N"*.
- **"Показать все действия за цикл"** expands a second panel showing the full backlog (active + done). Done cards are muted with line-through and carry a **`↺ Вернуть в очередь`** button — for accidental clicks.
- When all backlog items are done, the strip shows a *"Цикл закрыт"* insight card with a pointer back to the full list.
- **Drag-to-reorder** in the expanded "Все действия за цикл" panel — every active card has a `⋮⋮` handle (top-right) and is `draggable`. Drop one card on another and the dragged card slides in above the drop target. The drop target gets a 2px accent outline while hovered. Done cards aren't draggable; their order is irrelevant. Once you reorder by hand, a *"Порядок изменён вручную"* note appears in the strip footer and an **`↺ Сбросить к приоритету из данных`** button shows up at the top of the expanded panel.

State lives in `useState` inside `QuickWinsSection` — it resets on reload, which is intentional for a session-scoped concept.

## What's covered

- Hero with mode pill, theme toggle, refresh link and (in deep mode) report selector.
- **Quick wins panel** — top 4 actions for the session, each with `~N мин` time badge, count, impact note, and a one-click button.
- Flow map (`available` / `partial` / `runner` badges).
- Meta grid (period, mode, source).
- KPI grid with `info` popovers and signed delta chips. Quick mode shows top 4; deep mode shows all.
- "Приоритеты Сейчас" — tone-haloed priority cards.
- "Что Изменилось" — tone insight cards. *(deep only)*
- "Сравнение Периодов" — Trailing / YTD / 3Y compare cards. *(deep only)*
- Three-up action grid: `reorder_now`, `markdown_candidates`, `protect_winners`.
- **Центр действий** — Watchlist + Ручные задачи + status summary. *(deep only)*
- **Очереди дальнейших действий** — bars by status + bars by owner + saved-view chips. *(deep only)*
- **Карточка и история** — entity detail with weekly sparkline, position/cross badges, and an event log. *(deep only)*
- Four-up mini-table grid: winners, profit leaders, stock risk, stale stock. *(deep only)*
- Bar chart + ABC card. *(deep only)*
- Monthly sparkline. *(deep only)*
- Reviews + question reply cards with `DRAFT / APPROVED / SENT` status pills. Quick mode shows top 2.

## What's intentionally not covered

- Real interactions: theme toggle, mode toggle, and the in-component info popover work. Everything else is visual.
- Tooltip pinning + outside-click dismiss — wired to `useState` per-icon, not the centralized overlay manager from `ui_source/components.js`.
- Per-job parameter forms in the runner (see refresh kit).

## Notes for re-use

- Class names match `ui_source/styles.css` 1:1. To consume in another project, copy `colors_and_type.css` + `ui_source/styles.css` and the component file you want.
- Components are deliberately uncoupled — no shared store, no context, no theming hook. State is local. Theme is toggled by setting `data-theme` on `<body>`.
- All copy is in Russian. Translate at the call site, not in the component.
