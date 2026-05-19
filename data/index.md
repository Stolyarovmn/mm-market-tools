# data/

**Gitignored. Not in version control.**
Portable — copy this folder between machines (GDrive, USB, rsync).

```
data/
  db/                    SQLite databases
    data.db              Main analytics DB
    state.db             Quick-wins and action-center state
  src/                   Raw files from marketplace
    sells-report.csv     Weekly sells report
    left-out-report.csv  Left-out/inventory report
    paid-storage-report.xlsx  Paid storage report
    snapshots/           Per-run snapshots for replay
  reports/               Processed JSON for the dashboard
    dashboard/           index.json + per-report JSONs (served by /api/*)
    normalized/          Intermediate normalized JSONs
  cache/                 API response cache (safe to delete to free space)
  local/                 Per-machine overrides (not synced)
    cogs_overrides.json
    action_center.json
    entity_history_index.json
    product_content_cache.json
  job_runs/              Per-job run metadata
  logs/                  Daily log files (mm-YYYY-MM-DD.log) if LOG_TO_FILE=1
```

## Setup from scratch
```bat
mkdir data\db data\src data\src\snapshots
mkdir data\reports\dashboard data\reports\normalized
mkdir data\cache data\local data\job_runs data\logs
```
Restore `data.db` and `state.db` from backup into `data/db/`.

## Path constants
All paths defined in `core/paths.py`. Import from there — never hardcode.
