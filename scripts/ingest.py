#!/usr/bin/env python3
"""Ingestion pipeline for manually uploaded report files.

Detects file type from content, saves to raw_reports/, triggers rebuild.

Usage:
    py -3 scripts/ingest.py --file path/to/file.csv
    py -3 scripts/ingest.py --file path/to/file.csv --tag 2026-05-18
    py -3 scripts/ingest.py --file path/to/paid-storage.xlsx --token KE_TOKEN

Exit codes:
    0 — success
    1 — error
    2 — file saved, but need companion file (sells needs left-out or vice versa)
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paths import (

from core.logging_config import get_logger
log = get_logger('scripts.ingest')
    DASHBOARD_DIR,
    NORMALIZED_DIR,
    RAW_REPORTS_DIR,
    ensure_dir,
)

SELLS_MARKERS = {"Продано (ед.)", "Выручка (руб.)", "Комиссия маркетплейса (руб.)"}
LEFT_OUT_MARKERS = {"Оборачиваемость", "Платные остатки (шт.)", "Среднесуточные продажи (шт.)"}


def detect_csv_kind(path: Path) -> str | None:
    """Return 'sells', 'left_out', or None."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        reader = csv.reader(text.splitlines())
        headers = set(next(reader, []))
        if SELLS_MARKERS & headers:
            return "sells"
        if LEFT_OUT_MARKERS & headers:
            return "left_out"
    except Exception:
        pass
    return None


def detect_kind(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "paid_storage"
    if suffix == ".csv":
        return detect_csv_kind(path)
    if suffix == ".json":
        return "json_report"
    return None


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode, output


def rebuild_index_and_plan(log: list[str], tag: str) -> bool:
    """Re-build dashboard index then daily action plan. Returns True on success."""
    rc, out = run([sys.executable, "build_dashboard_index.py"], ROOT)
    log.append(f"[index] {out}")
    if rc != 0:
        return False

    rc, out = run([sys.executable, "build_daily_action_plan.py"], ROOT)
    log.append(f"[plan] {out}")
    return rc == 0


def ingest_sells_or_left_out(src: Path, kind: str, tag: str, log: list[str]) -> dict:
    ensure_dir(RAW_REPORTS_DIR)
    canon_name = "sells-report.csv" if kind == "sells" else "left-out-report.csv"
    dest = RAW_REPORTS_DIR / canon_name
    shutil.copy2(src, dest)
    log.append(f"Saved {kind} → {dest}")

    # Check if both files are present for operational rebuild
    sells_path = RAW_REPORTS_DIR / "sells-report.csv"
    left_path = RAW_REPORTS_DIR / "left-out-report.csv"

    if not sells_path.exists() or not left_path.exists():
        missing = "sells-report.csv" if not sells_path.exists() else "left-out-report.csv"
        return {
            "ok": False,
            "need_companion": True,
            "report_kind": kind,
            "saved_as": str(dest),
            "message": f"Файл сохранён. Загрузите также {missing} для пересборки дашборда.",
            "log": log,
        }

    # Both present — run refresh_operational_dashboard.py
    ensure_dir(NORMALIZED_DIR)
    ensure_dir(DASHBOARD_DIR)
    norm_out = NORMALIZED_DIR / f"weekly_operational_report_{tag}.json"
    dash_out = DASHBOARD_DIR / f"weekly_operational_report_{tag}.json"

    cmd = [
        sys.executable, "refresh_operational_dashboard.py",
        "--sells-report", str(sells_path),
        "--left-out-report", str(left_path),
        "--normalized-output", str(norm_out),
        "--dashboard-output", str(dash_out),
    ]
    rc, out = run(cmd, ROOT)
    log.append(f"[operational] {out}")
    if rc != 0:
        return {"ok": False, "report_kind": kind, "message": "Ошибка refresh_operational_dashboard", "log": log}

    ok = rebuild_index_and_plan(log, tag)
    return {
        "ok": ok,
        "report_kind": "weekly_operational",
        "dashboard_file": dash_out.name,
        "message": "Операционный дашборд обновлён." if ok else "Ошибка при пересборке индекса.",
        "log": log,
    }


def ingest_paid_storage(src: Path, tag: str, token: str, log: list[str]) -> dict:
    ensure_dir(RAW_REPORTS_DIR)
    dest = RAW_REPORTS_DIR / "paid-storage-report.xlsx"
    shutil.copy2(src, dest)
    log.append(f"Saved paid_storage → {dest}")

    cmd = [sys.executable, "build_paid_storage_report.py", "--xlsx-path", str(dest)]
    if token:
        cmd += ["--token", token]
    rc, out = run(cmd, ROOT)
    log.append(f"[paid_storage] {out}")
    if rc != 0:
        return {"ok": False, "report_kind": "paid_storage", "message": "Ошибка build_paid_storage_report", "log": log}

    ok = rebuild_index_and_plan(log, tag)
    return {
        "ok": ok,
        "report_kind": "paid_storage",
        "message": "Отчёт по платному хранению обновлён." if ok else "Ошибка при пересборке индекса.",
        "log": log,
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest an uploaded report file.")
    parser.add_argument("--file", required=True, help="Path to uploaded file")
    parser.add_argument("--tag", default=date.today().isoformat(), help="Date tag for output files")
    parser.add_argument("--token", default="", help="KE API token (for paid_storage online reuse)")
    parser.add_argument("--output-json", default="", help="Write result JSON to this path")
    args = parser.parse_args()

    src = Path(args.file)
    if not src.exists():
        result = {"ok": False, "message": f"File not found: {src}"}
        if args.output_json:
            Path(args.output_json).write_text(json.dumps(result, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    log: list[str] = []
    kind = detect_kind(src)
    log.append(f"Detected kind: {kind} for {src.name}")

    if kind == "sells":
        result = ingest_sells_or_left_out(src, "sells", args.tag, log)
    elif kind == "left_out":
        result = ingest_sells_or_left_out(src, "left_out", args.tag, log)
    elif kind == "paid_storage":
        result = ingest_paid_storage(src, args.tag, args.token, log)
    else:
        result = {
            "ok": False,
            "message": f"Не удалось определить тип файла: {src.name}. Ожидаются sells-report.csv, left-out-report.csv или paid-storage.xlsx.",
            "log": log,
        }

    result.setdefault("log", log)
    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output_json:
        Path(args.output_json).write_text(output, encoding="utf-8")

    print(output)
    sys.exit(0 if result.get("ok") or result.get("need_companion") else 1)


if __name__ == "__main__":
    main()
