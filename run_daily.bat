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

REM === STEP 1-3: Data collection ===
echo [1/5] Building daily action plan...
py -3 build_daily_action_plan.py --offline-fallback

echo [2/5] Building paid storage report...
py -3 build_paid_storage_report.py || echo WARN: paid_storage_report failed (token needed)

REM ab_compare.py requires specific product args — runs on-demand, not daily
REM Use: py -3 ab_compare.py --a-product-id ... --a-date-range ... --b-product-id ... --b-date-range ...

echo [3/5] Building quick wins...
py -3 build_quick_wins.py || echo WARN: build_quick_wins failed

REM === STEP 4: Build databases ===
echo [4/5] Building data.db...
py -3 scripts/build_sqlite.py

echo [4/5] Building state.db...
py -3 scripts/build_state_db.py

REM === STEP 5: Sync to GitHub ===
echo [5/5] Syncing to GitHub Pages + Release + Gist...
py -3 s