# mm-market-tools — Agent Briefing

Seller analytics for WONDERS shop on Магнит Маркет. Local-first, single operator.

## Start
```bat
python web_refresh_server.py
```
Open http://localhost:8080

## Structure
| Path | Role |
|------|------|
| `web_refresh_server.py` | HTTP server + /api/* endpoints |
| `scripts/` | 61 runnable analytics scripts |
| `core/` | Library modules (imported, not run directly) |
| `ui/` | React frontend |
| `data/` | All data files (gitignored, portable) |
| `logs/` | Log files (gitignored) |

## Key files
- `core/paths.py` — all file path constants
- `core/refresh_jobs.py` — job name → subprocess command map
- `core/logging_config.py` — logging: `log = get_logger(__name__)`

## Data layout (data/ is gitignored)
```
data/db/        SQLite: data.db, state.db
data/src/       Raw CSV/XLSX from marketplace
data/reports/   Processed JSON (dashboard/, normalized/)
data/local/     Per-machine overrides
data/cache/     API cache (safe to delete)
```

## Logging
.env: `LOG_LEVEL=INFO` (global), `LOG_LEVEL_SCRIPTS_BUILD_X=DEBUG` (per-module).
Levels: TRACE < DEBUG < INFO < WARNING < ERROR.

## GitHub issues
Use `.github/ISSUE_TEMPLATE/task.md`. Every issue must have:
Контекст + Цель + Затронутые файлы + Acceptance criteria + Не входит в scope.
