# logs/

Gitignored. Daily log files written when `LOG_TO_FILE=1` in `.env`.

Format: `mm-YYYY-MM-DD.log`

Each line:
```
2026-05-19 14:32:01 INFO    scripts.build_quick_wins — built 7 items
2026-05-19 14:32:01 DEBUG   core.refresh_jobs — job quick_wins started
```

## Configuration
`.env`:
```
LOG_LEVEL=INFO          # global default
LOG_TO_FILE=1           # enable file logging
LOG_DIR=logs            # directory (relative to project root)
```

Per-module:
```
LOG_LEVEL_SCRIPTS_BUILD_QUICK_WINS=DEBUG
LOG_LEVEL_CORE_REFRESH_JOBS=INFO
```
