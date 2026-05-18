@echo off
REM MM Market Tools — Daily Data Collection & Sync
REM Usage: run_daily.bat
REM Requires: Python 3.x, .env file with GH_TOKEN + GIST_ID

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
echo [0/5] Installing dependencies...
py -3 -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo [0/5] Restoring state.db from Gist...
py -3 scripts/download_state.py

REM === STEP 0b: MM API token (5-min JWT — paste fresh each run) ===
py -3 scripts/token_wizard.py
if errorlevel 2 (
    echo WARN: Пропускаем API-шаги — токен не введён
    set SKIP_API=1
) else (
    set /p KE_TOKEN=< .token_session
    del .token_session 2>nul
)

REM === STEP 1-3: Data collection ===
echo [1/5] Building daily action plan...
py -3 build_daily_action_plan.py --offline-fallback

echo [2/5] Building paid storage report...
if not defined SKIP_API (
    py -3 build_paid_storage_report.py --token %KE_TOKEN% || echo WARN: paid_storage_report failed
) else (
    echo SKIP: paid_storage_report ^(нет токена^)
)

REM ab_compare.py requires specific product args — runs on-demand, not daily
REM Use: py -3 ab_compare.py --a-product-id ... --a-date-range ... --b-pro