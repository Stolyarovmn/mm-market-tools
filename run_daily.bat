@echo off
REM MM Market Tools — Daily Data Collection & Sync
REM Usage: run_daily.bat
REM Requires: Python 3.x, .env file with GH_TOKEN + KE_TOKEN + GIST_ID

setlocal enabledelayedexpansion
set ROOT=%~dp0
cd /d %ROOT%

echo [MM] Starting daily run %date% %time%

REM === CHECK .env ===
if not exist .env (
    echo [ERROR] .env not found. Copy .env.example to .env and fill in tokens.
    pause
    exit /b 1
)

REM === STEP 0: Install deps + restore state ===
echo [0/6] Installing dependencies...
py -3 -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo [0/6] Restoring state.db from Gist...
py -3 scripts/download_state.py

REM === STEP 1-4: Data collection ===
echo [1/6] Building daily action plan...
py -3 build_daily_action_plan.py --offline-fallback

echo [2/6] Building paid storage report...
py -3 build_paid_storage_report.py || echo WARN: paid_storage_report failed

echo [3/6] Running A/B compare...
py -3 ab_compare.py || echo WARN: ab_compare failed (no applied actions yet?)

echo [4/6] Building quick wins...
py -3 build_quick_wins.py || echo WARN: build_quick_wins failed

REM === STEP 5: Build databases ===
echo [5/6] Building data.db...
py -3 scripts/build_sqlite.py

echo [5/6] Building state.db...
py -3 scripts/build_state_db.py

REM === STEP 6: Sync to GitHub ===
echo [6/6] Syncing to GitHub Pages + Release + Gist...
py -3 scripts/sync_to_pages.py

echo [MM] Done! GitHub Pages will update in ~2 minutes.
pause
