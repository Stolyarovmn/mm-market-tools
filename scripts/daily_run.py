#!/usr/bin/env python3
"""
Daily Run — последовательный запуск всех ежедневных jobs с одним токеном.

Порядок:
  1. validate_token          (fail fast — если токен плохой, дальше не идём)
  2. weekly_operational      (основные данные продаж, required)
  3. paid_storage_report     (платное хранение, optional)
  4. buyer_reviews           (отзывы без ответа, optional)
  5. price_trap_audit        (offline, на свежих данных)
  6. title_seo_audit         (offline)
  7. dynamic_pricing         (offline, если есть market данные)
  8. marketing_card_audit    (offline, сводный аудит)
  9. build_daily_action_plan (пересобирает daily_action_plan.json)
 10. build_dashboard_index   (обновляет индекс)

Usage:
  python scripts/daily_run.py --token <bearer_token>
  python scripts/daily_run.py --token <bearer_token> --skip-validate
  python scripts/daily_run.py --offline-only   # только шаги 5-10
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent  # project root
SCRIPTS = ROOT / "scripts"
PYTHON = sys.executable

# ── helpers ───────────────────────────────────────────────────────────────────

def _latest(directory: Path, pattern: str) -> str | None:
    """Найти самый свежий файл по glob-паттерну."""
    matches = sorted(directory.glob(pattern), reverse=True)
    return str(matches[0]) if matches else None


def run_step(name: str, cmd: list, required: bool = True) -> bool:
    sep = "─" * 56
    print(f"\n┌{sep}┐")
    print(f"│  {name}")
    print(f"└{sep}┘")
    sys.stdout.flush()

    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode != 0:
        print(f"\n✗ [{name}] завершился с ошибкой (код {result.returncode})")
        if required:
            print("  Прерываю daily run.")
            sys.exit(result.returncode)
        else:
            print("  Продолжаю (шаг опциональный).")
        return False

    print(f"\n✓ [{name}] OK")
    return True


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Daily run — все ежедневные jobs в одном запуске"
    )
    parser.add_argument("--token", default="", help="Bearer-токен из ЛК")
    parser.add_argument("--shop-id", type=int, default=98)
    parser.add_argument("--window-days", type=int, default=7,
                        help="Окно данных для weekly_operational")
    parser.add_argument("--skip-validate", action="store_true",
                        help="Пропустить validate_token (если уже проверяли)")
    parser.add_argument("--offline-only", action="store_true",
                        help="Только offline-шаги (5-10), без API-запросов")
    args = parser.parse_args()

    if not args.offline_only and not args.token:
        parser.error("--token обязателен (или используйте --offline-only)")

    dashboard_dir = ROOT / "data" / "dashboard"
    normalized_dir = ROOT / "data" / "normalized"

    print("\n╔══════════════════════════════════════════════════════╗")
    print("║              MM Market Tools — Daily Run             ║")
    print("╚══════════════════════════════════════════════════════╝")

    # ── ONLINE БЛОК ───────────────────────────────────────────────────────────
    if not args.offline_only:

        # 1. Validate token
        if not args.skip_validate:
            run_step("validate_token", [
                PYTHON, str(SCRIPTS / "validate_token_integrations.py"),
                "--token", args.token,
                "--shop-id", str(args.shop_id),
            ], required=True)

        # 2. Weekly operational (основные данные — продажи, остатки, выручка)
        run_step("weekly_operational", [
            PYTHON, str(SCRIPTS / "weekly_operational_report.py"),
            "--token", args.token,
            "--shop-id", str(args.shop_id),
            "--window-days", str(args.window_days),
        ], required=True)

        # 3. Paid storage (платное хранение)
        run_step("paid_storage_report", [
            PYTHON, str(SCRIPTS / "build_paid_storage_report.py"),
            "--token", args.token,
        ], required=False)

        # 4. Buyer reviews (отзывы без ответа)
        run_step("buyer_reviews", [
            PYTHON, str(SCRIPTS / "fetch_buyer_reviews.py"),
            "--token", args.token,
            "--status", "WITHOUT_ANSWER",
            "--max-pages", "10",
        ], required=False)

    # ── OFFLINE БЛОК (на основе только что полученных данных) ─────────────────

    # Находим свежий normalized JSON от weekly_operational
    weekly_json = _latest(normalized_dir, "weekly_operational_report_*.json")
    if not weekly_json:
        # Fallback на dashboard
        weekly_json = _latest(dashboard_dir, "weekly_operational_report_*.json")

    if weekly_json:
        print(f"\n  Используем: {Path(weekly_json).name}")

        # 5. Price trap audit
        run_step("price_trap_audit", [
            PYTHON, str(SCRIPTS / "build_price_trap_report.py"),
            "--input-json", weekly_json,
        ], required=False)

        # 6. Title SEO audit
        run_step("title_seo_audit", [
            PYTHON, str(SCRIPTS / "build_title_seo_report.py"),
            "--input-json", weekly_json,
        ], required=False)

    # 7. Dynamic pricing (нужны market данные)
    market_json = _latest(dashboard_dir, "market_rescored_after_cogs_*.json")
    if market_json:
        run_step("dynamic_pricing", [
            PYTHON, str(SCRIPTS / "build_dynamic_pricing_report.py"),
            "--market-json", market_json,
        ], required=False)
    else:
        print("\n  [dynamic_pricing] Пропуск — нет market данных (запустите market_scan)")

    # 8. Marketing card audit (сводный)
    if weekly_json:
        cmd = [
            PYTHON, str(SCRIPTS / "build_marketing_card_audit.py"),
            "--normalized-json", weekly_json,
        ]
        pricing_json = _latest(dashboard_dir, "dynamic_pricing_*.json")
        trap_json    = _latest(dashboard_dir, "price_trap_report_*.json")
        seo_json     = _latest(dashboard_dir, "title_seo_report_*.json")
        if pricing_json: cmd += ["--pricing-json", pricing_json]
        if trap_json:    cmd += ["--price-trap-json", trap_json]
        if seo_json:     cmd += ["--title-seo-json", seo_json]
        run_step("marketing_card_audit", cmd, required=False)

    # 9. Build daily action plan (главный plan → data/daily_action_plan.json)
    run_step("build_daily_action_plan", [
        PYTHON, str(SCRIPTS / "build_daily_action_plan.py"),
        "--offline-fallback",
    ], required=False)

    # 10. Dashboard index rebuild
    run_step("dashboard_rebuild", [
        PYTHON, str(SCRIPTS / "build_dashboard_index.py"),
    ], required=False)

    print("\n╔══════════════════════════════════════════════════════╗")
    print("║                   Daily Run — ГОТОВО                ║")
    print("╚══════════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    main()
