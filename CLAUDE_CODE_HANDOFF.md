# Claude Code Handoff — Integrate MM Market Tools Design System into `ui/`

This document is a list of issues ready to paste into GitHub (or feed straight to Claude Code as a task batch). Each issue is **self-contained**: what to do, where in the codebase, which files in this design system to mirror, and an acceptance test.

The design system lives in this project. The target codebase is the live Python project [`Stolyarovmn/mm-market-tools`](https://github.com/Stolyarovmn/mm-market-tools), specifically:
- `ui/` — the ES-modules dashboard
- `web_refresh_server.py` — the local API server
- `core/action_store.py` — the persistent action store
- `build_dashboard_index.py` — the dashboard index builder

## Map of the design system

| Path                                  | Use when                                                                  |
|---------------------------------------|---------------------------------------------------------------------------|
| `colors_and_type.css`                 | Drop in as the new `ui/styles.css` *companion* — it does not replace the existing stylesheet, it provides additional tokens. Both can coexist. |
| `ui_kits/dashboard/components.jsx`    | Reference implementation of every new component. JSX. Port to plain ES modules + DOM (matches `ui/app.js` style). |
| `ui_kits/dashboard/App.jsx`           | Reference composition — order of sections, mode toggle, where Quick wins lives. |
| `ui_kits/dashboard/data.js`           | **Contract** for the JSON shapes the backend has to produce. Treat as source of truth. |
| `ui_kits/refresh/`                    | Reference for the refresh runner — most of it already exists in `ui/refresh.html`. |
| `preview/*.html`                      | Pixel references for individual components — open in browser if a class name is ambiguous. |

---

## ISSUE 1 — `build_quick_wins.py` CLI

**Goal.** Produce the JSON the dashboard's Quick wins section consumes.

**Context.**
- The dashboard already has `data/dashboard/weekly_operational_report_*.json`, `marketing_card_audit_*.json`, etc.
- Quick wins is a derived, decision-oriented top-of-the-pile bundle.

**Do.**
1. Create `build_quick_wins.py` at repo root, modelled on `build_marketing_card_audit.py`.
2. Read latest:
   - operational weekly bundle → `reorder_now` count, `markdown_candidates` count
   - `marketing_card_audit` → `price_trap` count, `title_seo` count
   - `core/reviews_api.py` cache → unanswered review count + question count
   - `core/action_store.py` → watchlist size (for the "Проверить watchlist" win)
   - `data/job_runs/` → has weekly_operational run happened today? if not, `run_job: weekly` enters backlog
3. Emit `data/dashboard/quick_wins_<YYYY-MM-DD>.json` with this exact shape (see `ui_kits/dashboard/data.js` → `quick_wins_backlog`):

```json
{
  "schema_version": "v1",
  "session_date": "2026-04-08",
  "items": [
    { "id": "reorder",   "kind": "reorder",    "count": 14, "label": "Утвердить reorder_now",        "action": "Открыть список", "route": "reorder_now",          "priority": 1 },
    { "id": "markdown",  "kind": "markdown",   "count": 9,  "label": "Согласовать markdown",          "action": "Открыть список", "route": "markdown_candidates",  "priority": 2 },
    { "id": "reviews",   "kind": "reviews",    "count": 2,  "label": "Ответить покупателям",          "action": "К отзывам",       "route": "buyer_reviews",        "priority": 3 },
    { "id": "weekly",    "kind": "run_job",    "count": 1,  "label": "Запустить weekly_operational",  "action": "К runner",        "route": "refresh:weekly",       "priority": 4 }
  ]
}
```

4. Priority rule: **impact ÷ estimated minutes**, descending. Use the `estimateMin` table in `ui_kits/dashboard/components.jsx` as the canonical estimator and port it to Python.
5. Items with `count == 0` are dropped — no empty quick wins.
6. Register the new report kind in `build_dashboard_index.py` so it appears in `data/dashboard/index.json` as `kind: "quick_wins"`.

**Acceptance.**
- `python3 build_quick_wins.py` produces a non-empty JSON in `data/dashboard/`.
- Re-running with no new data is idempotent (overwrites the same dated file).
- `build_dashboard_index.py` picks it up; `data/dashboard/index.json` lists `quick_wins_<date>.json` under both `items` and `reports`.
- Add `smoke_test_quick_wins_pipeline.py` that prints `SMOKE_QUICK_WINS_OK` if every expected `kind` is reachable in fixture data.

---

## ISSUE 2 — Quick wins section in `ui/app.js`

**Goal.** Render the Quick wins strip at the top of the dashboard.

**Context.**
- All dashboard sections are rendered in `ui/app.js` (≈6,000 LOC). Generic UI helpers live in `ui/components.js`.
- The reference component is `QuickWinsSection` in `ui_kits/dashboard/components.jsx` — JSX, but the logic translates 1:1 to DOM.

**Do.**
1. Port `estimateMin`, `impactText`, `QuickWinCard`, `QuickWinsSection` from `ui_kits/dashboard/components.jsx` into a new module `ui/quick_wins.js`. Match the existing `ui/components.js` style — `export function el(tag, className, text)`, etc.
2. Render the strip as the **first panel after the hero**, above "Сводка отчёта".
3. Read the backlog from `data/dashboard/quick_wins_<latest>.json` via `ui/api.js` (extend it with `loadQuickWins()` if needed).
4. Show top 4 active items in `kpi-grid`. Subtitle: `"${visible.length} действия в очереди — примерно ${totalMin} мин на всё."`.
5. Below the strip: `"Ещё доступно: N"` / `"Готово за сессию: N"` / `"Показать все действия за цикл"` toggle — exactly as in the kit.
6. Add the `⋮⋮` drag handle on cards in the expanded panel only.

**Acceptance.**
- Strip renders on initial dashboard load. KPI grid shows 4 cards. Subtitle reflects real summed minutes.
- "Показать все действия за цикл" expands a second panel with the full backlog. Done items appear muted with line-through and a `↺ Вернуть в очередь` button.
- Visual: matches `ui_kits/dashboard/index.html` running locally.

---

## ISSUE 3 — Quick wins state persistence

**Goal.** Survive page reload. Per-session, not per-user.

**Context.**
- `web_refresh_server.py` already exposes a JSON-over-HTTP API for the action center (`/api/...`).
- Storage already uses `data/local/*.json` files via `core/action_store.py`.

**Do.**
1. Add `core/quick_wins_state.py` with helpers:
   - `load_state(session_date)` → `{ done_ids: [], custom_order: [] }`
   - `mark_done(session_date, id)`
   - `mark_active(session_date, id)`
   - `set_order(session_date, order)`
   - `reset_if_stale(session_date)` — wipes state when the underlying `quick_wins_<date>.json` changes.
2. Persist to `data/local/quick_wins_state.json`.
3. Wire endpoints in `web_refresh_server.py`:
   - `GET  /api/quick_wins/state`
   - `POST /api/quick_wins/complete`  body `{ id }`
   - `POST /api/quick_wins/restore`   body `{ id }`
   - `POST /api/quick_wins/reorder`   body `{ order: ["reorder", "reviews", ...] }`
4. All responses: `{ ok: true, state: { done_ids, custom_order, version } }`. Version is a monotonic int — bumped on any mutation, used by the frontend to detect concurrent edits.

**Acceptance.**
- Reload preserves done items and reordered priority.
- Running `build_quick_wins.py` produces a new dated backlog → state auto-resets on next `GET /api/quick_wins/state`.
- `smoke_test_action_center_api.py` extended with the four endpoints.

---

## ISSUE 4 — Wire the buttons

**Goal.** Every visible button in the Quick wins surface does something real.

**Mapping.**

| Button                          | Card kind / context        | Action                                                                                       |
|---------------------------------|----------------------------|----------------------------------------------------------------------------------------------|
| `Открыть список`                | reorder / markdown / protect_winners / price_trap / title_seo | Smooth-scroll to target panel + apply `panel-pulse` class for 1.2s. Target id = `win.route`. |
| `К отзывам`                     | reviews / questions         | Smooth-scroll to `#buyer-reviews-panel`, focus the first unanswered review's textarea.       |
| `К runner`                      | run_job                     | `window.location.href = '/refresh.html?target=' + jobName`. The runner already supports `?target=` deep-link (see `targeted-pulse` keyframe). |
| `Открыть список` (watchlist)    | watchlist                   | Smooth-scroll to `#action-center-panel`.                                                     |
| `✓ Готово` (mini-action)        | any active                 | `POST /api/quick_wins/complete { id }` → optimistic update → on error, revert + insight-card with bad tone. |
| `↺ Вернуть в очередь`           | any done                   | `POST /api/quick_wins/restore { id }` → optimistic update → on error, revert.                |
| Drop after drag                 | expanded panel              | `POST /api/quick_wins/reorder { order }` → debounce 300ms.                                   |
| `↺ Сбросить к приоритету`       | expanded panel header       | `POST /api/quick_wins/reorder { order: [] }` — empty array means "use server priority".      |

**Do.**
- Map the actions in `ui/quick_wins.js`. Use existing `ui/api.js` patterns.
- The `panel-pulse` animation is already defined in `ui/styles.css`. Apply it via `el.classList.add('panel-pulse')` and remove after `animationend`.
- The refresh runner's `?target=` deep-link already animates a `targeted-pulse` on the matching job card — no changes needed there.

**Acceptance.**
- Each button does what the table says. Click → visible feedback within 200ms.
- Network errors revert state and surface a transient `insight-card[data-tone="bad"]` near the strip footer.

---

## ISSUE 5 — Mode toggle: «Сейчас» / «Полный режим»

**Goal.** Default dashboard view is the focused quick-cycle one. Full analyst view is one click away.

**Context.**
- Reference: `ModeSwitch` + the `deep` boolean threaded through `App.jsx` in `ui_kits/dashboard/App.jsx`.
- Default is **always «Сейчас»**. Do not persist. Confirmed by stakeholder.

**Do.**
1. Add the segmented pill control to `.hero-actions` (between theme toggle and refresh link).
2. Hide in «Сейчас» mode (display:none, do not unmount): Карта Flow'ов, Что Изменилось, Сравнение Периодов, Центр действий, Очереди дальнейших действий, Карточка и история, mini-table grid, Распределения, История По Месяцам.
3. In «Сейчас», the KPI grid shows the **first 4** KPIs. In «Полный режим» — all.
4. In «Сейчас», the buyer-reviews panel shows the **first 2** reviews. A `Показать ещё` link reveals the rest.
5. Below the last visible panel in «Сейчас» — a single CTA card: `"Нужен глубокий разбор? → Открыть полный режим"`. Click flips the mode.
6. Switching modes does not reset Quick wins state.

**Acceptance.**
- Page loads in «Сейчас» mode. Switching to «Полный режим» reveals every panel the live UI has today.
- Mode pill matches `preview/badges.html` styling — accent pill background, white text on the selected one.

---

## ISSUE 6 — Polish: text-decoration on `.theme-toggle` anchors

**Goal.** Tiny visual fix.

**Do.** In `ui/styles.css`, find the `.theme-toggle` rule and add:

```css
.theme-toggle {
  text-decoration: none;
}
```

(Currently only `.compact-button` sets this; `<a class="theme-toggle">` inherits the default underline.)

**Acceptance.** No underline on the "Обновить данные" / "К дашборду" / "К runner" links in either mode.

---

## ISSUE 7 — Action Center, Manager Queues, Entity Detail (optional, deep-mode polish)

**Goal.** Bring the three sections that Claude Code skipped in the original pass.

The reference implementations (DOM-ready logic) are:
- `WatchlistCard`, `ManualActionsCard`, `ActionCenterStatusCard` in `ui_kits/dashboard/components.jsx`
- `QueueByBars`, `SavedViewsCard` (same file)
- `EntityDetail` (same file)

The data is already in `core/action_store.py`. The endpoints already exist. This is pure rendering work.

**Acceptance.** Three panels render real data in «Полный режим». No new Python required.

---

## Suggested order

1. **Issue 1** (build the data) — unblocks everything else
2. **Issue 3** (backend state) — unblocks Issue 4
3. **Issue 2** (frontend section, with mocked state)
4. **Issue 4** (wire buttons against the real API)
5. **Issue 5** (mode toggle)
6. **Issue 6** (polish)
7. **Issue 7** (deep-mode panels) — pick up after the core loop works

## How to feed this to Claude Code

In Claude Code, open the `mm-market-tools` repo, then:

> Read `CLAUDE_CODE_HANDOFF.md` from the attached design-system project. Pick up **Issue 1**. The design system is read-only — don't edit it. Reproduce visual references by opening `ui_kits/dashboard/index.html` locally if needed. Confirm the contract in `ui_kits/dashboard/data.js` before you start.

…and proceed issue by issue. Each issue's "Acceptance" section is the test for done.
