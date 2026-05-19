"""Central path definitions. Import from here — never hardcode paths.

data/ layout (gitignored, portable):
  db/       SQLite: data.db, state.db
  src/      Raw CSV/XLSX from marketplace
  reports/  Processed JSON for dashboard
    dashboard/  index.json + per-report JSONs
    normalized/ Intermediate normalized JSONs
  cache/    API response cache
  local/    Per-machine overrides
  logs/     Log files
"""
from __future__ import annotations
import datetime as dt, os
from pathlib import Path

_cwd = Path(os.getcwd())
if (_cwd/"web_refresh_server.py").exists(): PROJECT_ROOT=_cwd
elif (_cwd.parent/"web_refresh_server.py").exists(): PROJECT_ROOT=_cwd.parent
else: PROJECT_ROOT=Path(__file__).resolve().parent.parent

DATA_DIR     = PROJECT_ROOT / "data"
SCRIPTS_DIR  = PROJECT_ROOT / "scripts"
LOGS_DIR     = PROJECT_ROOT / "logs"

DB_DIR       = DATA_DIR / "db"
SRC_DIR      = DATA_DIR / "src"
REPORTS_DIR  = DATA_DIR / "reports"
CACHE_DIR    = DATA_DIR / "cache"
LOCAL_DATA_DIR = DATA_DIR / "local"

DB_PATH                    = DB_DIR / "data.db"
STATE_DB_PATH              = DB_DIR / "state.db"
COGS_OVERRIDES_PATH        = LOCAL_DATA_DIR / "cogs_overrides.json"
ACTION_CENTER_PATH         = LOCAL_DATA_DIR / "action_center.json"
ENTITY_HISTORY_INDEX_PATH  = LOCAL_DATA_DIR / "entity_history_index.json"
PRODUCT_CONTENT_CACHE_PATH = LOCAL_DATA_DIR / "product_content_cache.json"
JOB_RUNS_DIR               = DATA_DIR / "job_runs"

# Backward-compat aliases
RAW_REPORTS_DIR = SRC_DIR
NORMALIZED_DIR  = REPORTS_DIR / "normalized"
DASHBOARD_DIR   = REPORTS_DIR / "dashboard"
SNAPSHOTS_DIR   = SRC_DIR / "snapshots"

def today_tag() -> str: return dt.date.today().isoformat()
def ensure_dir(path: Path) -> Path: path.mkdir(parents=True, exist_ok=True); return path
