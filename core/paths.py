#!/usr/bin/env python3
import datetime as dt
from pathlib import Path
import os


# Поддержка запуска из разных мест (особенно для тестирования)
_cwd = Path(os.getcwd())
if (_cwd / "build_waybill_cost_layer.py").exists():
    # Запуск из корня проекта
    PROJECT_ROOT = _cwd
elif (_cwd.parent / "build_waybill_cost_layer.py").exists():
    # Запуск из подпапки
    PROJECT_ROOT = _cwd.parent
else:
    # Fallback на hardcoded path (для production)
    PROJECT_ROOT = Path("/home/user/mm-market-tools")
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
RAW_REPORTS_DIR = DATA_DIR / "raw_reports"
NORMALIZED_DIR = DATA_DIR / "normalized"
DASHBOARD_DIR = DATA_DIR / "dashboard"
LOCAL_DATA_DIR = DATA_DIR / "local"
COGS_OVERRIDES_PATH = LOCAL_DATA_DIR / "cogs_overrides.json"
ACTION_CENTER_PATH = LOCAL_DATA_DIR / "action_center.json"
ENTITY_HISTORY_INDEX_PATH = LOCAL_DATA_DIR / "entity_history_index.json"
PRODUCT_CONTENT_CACHE_PATH = LOCAL_DATA_DIR / "product_content_cache.json"
JOB_RUNS_DIR = DATA_DIR / "job_runs"


def today_tag():
    return dt.date.today().isoformat()


def ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path
