# ui/

React frontend served by `web_refresh_server.py` at http://localhost:8080.

| File | Purpose |
|------|---------|
| `index.html` | Shell: loads React 18 + Babel + stylesheets, mounts `#root` |
| `App.jsx` | Main app: mode toggle (Сейчас/Полный режим), panel layout |
| `components.jsx` | All React components: Panel, KpiCard, QuickWinsSection, ReviewCard, ... |
| `data-loader.js` | Fetches /api/* endpoints → assembles `window.DashboardData` for App.jsx |
| `styles.css` | Design tokens + component styles (mirrors ui/styles.css from design system) |

## Data flow
```
data-loader.js  →  fetch /api/quick_wins/state    → window.DashboardData.quick_wins_backlog
                →  fetch /api/dashboard            → .kpis, .meta, .priorities
                →  fetch /api/action_center        → .watchlist, .manual_actions
                →  fetch /api/reviews              → .reviews
                →  ReactDOM.render(<DashboardApp/>)
```

## Modes
- **Сейчас** (quick, 15-30 min): QuickWins → Сводка → KPIs → Приоритеты → Действия → Покупатели
- **Полный режим** (analyst): all panels + Explorer, Операции, Отчёты, A/B, ROMI, API, Блокеры, Источники

## Design system
Source: `MM Market Tools Design System/ui_kits/dashboard/`
Components match `components.jsx` from the design kit.
CSS tokens: `--bg`, `--surface`, `--ink`, `--accent`, `--good`, `--warn`, `--bad`, `--line`
