#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

import requests

from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION
from core.documents_api import download_file, fetch_requests
from core.io_utils import write_json
from core.paths import DASHBOARD_DIR, RAW_REPORTS_DIR, REPORTS_DIR, ensure_dir, today_tag
from core.xlsx_reader import read_xlsx_sheet_rows


def parse_args():
    parser = argparse.ArgumentParser(description="Reuse latest completed PAID_STORAGE_REPORT and build a manager-facing dashboard bundle.")
    parser.add_argument("--token")
    parser.add_argument("--token-file", default="")
    parser.add_argument("--requests-page-size", type=int, default=200)
    parser.add_argument("--xlsx-path", default="")
    parser.add_argument("--request-id", type=int)
    parser.add_argument("--report-dir", default=str(REPORTS_DIR))
    parser.add_argument("--raw-dir", default=str(RAW_REPORTS_DIR))
    parser.add_argument("--dashboard-dir", default=str(DASHBOARD_DIR))
    parser.add_argument("--report-prefix", default=f"paid_storage_report_{today_tag()}")
    return parser.parse_args()


def _normalize_header(header):
    return re.sub(r"[^a-zа-я0-9]+", "_", str(header).strip().lower()).strip("_")


def _is_amount_header(header):
    normalized = _normalize_header(header)
    return any(token in normalized for token in ["сум", "стоим", "оплат", "итог", "хран", "начис", "услуг", "комисс"])


def _is_penalty_header(header):
    normalized = _normalize_header(header)
    return any(token in normalized for token in ["штраф", "пен", "удерж"])


def _is_identity_header(header):
    normalized = _normalize_header(header)
    return any(token in normalized for token in ["sku", "артикул", "штрих", "баркод", "товар", "номенк", "назван"])


def _best_numeric_header(rows):
    scores = []
    if not rows:
        return None
    for key in rows[0].keys():
        if key.endswith("__num"):
            continue
        values = [row.get(f"{key}__num") for row in rows if row.get(f"{key}__num") is not None]
        if not values:
            continue
        score = sum(values)
        if _is_amount_header(key):
            score += 1_000_000
        scores.append((score, key))
    scores.sort(reverse=True)
    return scores[0][1] if scores else None


def _select_latest_request(payload, request_id=None):
    requests_list = ((payload.get("payload") or {}).get("requests") or [])
    candidates = [row for row in requests_list if row.get("jobType") == "PAID_STORAGE_REPORT" and row.get("status") == "COMPLETED"]
    if request_id is not None:
        candidates = [row for row in candidates if int(row.get("requestId") or 0) == int(request_id)]
    return candidates[0] if candidates else None


def _build_rows(parsed_rows):
    amount_header = _best_numeric_header(parsed_rows)
    rows = []
    for row in parsed_rows:
        identity_values = [str(row.get(key) or "").strip() for key in row.keys() if not key.endswith("__num") and _is_identity_header(key)]
        amount = row.get(f"{amount_header}__num") if amount_header else None
        normalized = {
            "title": next((value for value in identity_values if value), "Строка без названия"),
            "amount": round(amount, 2) if amount is not None else None,
            "amount_label": amount_header or "Сумма",
            "identity": next((value for value in identity_values if value), None),
            "raw": {key: value for key, value in row.items() if not key.endswith("__num")},
        }
        for key, value in row.items():
            if key.endswith("__num"):
                continue
            num = row.get(f"{key}__num")
            normalized[_normalize_header(key)] = value
            if num is not None:
                normalized[f"{_normalize_header(key)}_num"] = round(num, 2)
        rows.append(normalized)
    rows.sort(key=lambda item: item.get("amount") or 0, reverse=True)
    return rows, amount_header


def _column_totals(parsed_rows):
    totals = []
    if not parsed_rows:
        return totals
    for key in parsed_rows[0].keys():
        if key.endswith("__num"):
            continue
        values = [row.get(f"{key}__num") for row in parsed_rows if row.get(f"{key}__num") is not None]
        if not values:
            continue
        totals.append(
            {
                "column": key,
                "total": round(sum(values), 2),
                "avg": round(sum(values) / len(values), 2),
                "rows_with_value": len(values),
                "kind": "penalty" if _is_penalty_header(key) else ("amount" if _is_amount_header(key) else "numeric"),
            }
        )
    totals.sort(key=lambda item: abs(item["total"]), reverse=True)
    return totals


def build_markdown(summary, top_rows, column_totals, metadata):
    lines = [
        "# Paid Storage Report",
        "",
        f"- request id: `{metadata.get('request_id', 'н/д')}`",
        f"- source file: `{metadata.get('file_name', 'н/д')}`",
        f"- sheet: `{metadata.get('sheet_name', 'н/д')}`",
        f"- rows: `{summary['total_rows']}`",
        f"- total amount: `{summary['total_amount']} ₽`",
        f"- rows without identity: `{summary['rows_without_identity']}`",
        "",
        "## Top storage/service charges",
        "",
    ]
    if not top_rows:
        lines.append("- В отчёте не найдено строк с явной суммой.")
    else:
        for row in top_rows[:20]:
            lines.extend(
                [
                    f"### {row['title']}",
                    "",
                    f"- {row['amount_label']}: `{row.get('amount', 'н/д')} ₽`",
                    f"- identity: `{row.get('identity') or 'н/д'}`",
                    "",
                ]
            )
    lines.extend(["## Numeric columns", ""])
    for row in column_totals[:12]:
        lines.append(f"- `{row['column']}`: total `{row['total']}`, avg `{row['avg']}`, rows `{row['rows_with_value']}`")
    return "\n".join(lines)


def build_dashboard_payload(rows, summary, column_totals, metadata):
    top_costs = rows[:8]
    check_rows = [row for row in rows if not row.get("identity")][:8]
    penalty_total = round(sum(item["total"] for item in column_totals if item["kind"] == "penalty"), 2)
    amount_total = round(sum(item["total"] for item in column_totals if item["kind"] == "amount"), 2)
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "window": {},
            "documents": {
                "paid_storage_request_id": metadata.get("request_id"),
                "paid_storage_file_name": metadata.get("file_name"),
                "paid_storage_download_url": metadata.get("download_url"),
                "paid_storage_mode": metadata.get("mode"),
            },
            "paid_storage": metadata,
        },
        "kpis": {
            "total_skus": summary["total_rows"],
            "sold_skus": summary["rows_with_amount"],
            "revenue_total": amount_total,
            "gross_profit_total": 0.0,
            "stockout_risk_count": summary["rows_without_identity"],
            "stale_stock_count": len([row for row in rows if (row.get("amount") or 0) > 0]),
            "storage_rows_count": summary["total_rows"],
            "rows_with_amount_count": summary["rows_with_amount"],
            "rows_without_identity_count": summary["rows_without_identity"],
            "total_amount": summary["total_amount"],
            "penalty_total": penalty_total,
            "avg_amount_per_row": summary["avg_amount_per_row"],
        },
        "actions": {
            "reorder_now": top_costs,
            "markdown_candidates": check_rows,
            "protect_winners": [row for row in rows if (row.get("amount") or 0) >= summary["high_cost_threshold"]][:8],
            "watchlist_signals": [row for row in rows if (row.get("amount") or 0) > 0 and not row.get("identity")][:8],
        },
        "tables": {
            "current_winners": top_costs,
            "profit_leaders": [{"title": row["column"], "gross_profit": row["total"], "profit_margin_pct": row["avg"]} for row in column_totals[:8]],
            "stockout_risk": check_rows,
            "stale_stock": rows[:20],
        },
        "charts": {
            "cost_distribution": [
                {"key": "Топ-8 строк", "value": round(sum(row.get("amount") or 0 for row in top_costs), 2)},
                {"key": "Остальные строки", "value": round(max(summary["total_amount"] - sum(row.get("amount") or 0 for row in top_costs), 0), 2)},
            ],
            "numeric_columns": [{"key": row["column"], "value": row["total"]} for row in column_totals[:8]],
        },
        "insights": [
            {
                "title": "Отчёт по платному хранению подключён",
                "text": f"В текущем файле видно {summary['total_rows']} строк и суммарный платный слой {summary['total_amount']} ₽. Это новый контур затрат, которого раньше не было в дашборде.",
                "tone": "good",
            },
            {
                "title": "Есть строки без надёжной идентификации",
                "text": f"{summary['rows_without_identity']} строк не содержат явного SKU/артикула/названия. Их нужно сверять вручную, иначе разбор затрат по карточкам будет неполным.",
                "tone": "warn" if summary["rows_without_identity"] else "good",
            },
            {
                "title": "Сначала смотри крупнейшие начисления",
                "text": "Этот экран пока manager-facing и объяснительный: он показывает, где платный storage/service слой накапливается быстрее всего и что требует ручной проверки.",
                "tone": "neutral",
            },
        ],
    }


def _fetch_latest_xlsx(token, raw_dir, page_size, request_id=None):
    with requests.Session() as session:
        requests_payload = fetch_requests(session, token, page=0, size=page_size)
        latest = _select_latest_request(requests_payload, request_id=request_id)
        if not latest:
            raise SystemExit("Не найден completed PAID_STORAGE_REPORT в seller documents.")
        result = latest.get("result") or {}
        link = result.get("link")
        if not link:
            raise SystemExit("В найденном PAID_STORAGE_REPORT нет download link.")
        file_name = result.get("fileName") or f"paid-storage-{today_tag()}.xlsx"
        xlsx_path = download_file(session, link, raw_dir / file_name)
        return xlsx_path, {
            "request_id": latest.get("requestId"),
            "file_name": file_name,
            "download_url": link,
            "mode": "reused",
        }


def main():
    args = parse_args()
    report_dir = ensure_dir(Path(args.report_dir))
    raw_dir = ensure_dir(Path(args.raw_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))

    metadata = {}
    token = args.token
    if args.token_file:
        token = Path(args.token_file).read_text(encoding="utf-8").strip()
    if args.xlsx_path:
        xlsx_path = Path(args.xlsx_path)
        metadata.update({"request_id": None, "file_name": xlsx_path.name, "download_url": None, "mode": "local"})
    else:
        if not token:
            raise SystemExit("Для online reuse нужен --token или локальный --xlsx-path.")
        xlsx_path, metadata = _fetch_latest_xlsx(token, raw_dir, args.requests_page_size, request_id=args.request_id)

    parsed = read_xlsx_sheet_rows(xlsx_path)
    parsed_rows = parsed["rows"]
    rows, amount_header = _build_rows(parsed_rows)
    column_totals = _column_totals(parsed_rows)
    amount_values = [row.get("amount") for row in rows if row.get("amount") is not None]
    total_amount = round(sum(amount_values), 2) if amount_values else 0.0
    summary = {
        "total_rows": len(rows),
        "rows_with_amount": len(amount_values),
        "rows_without_identity": sum(1 for row in rows if not row.get("identity")),
        "total_amount": total_amount,
        "avg_amount_per_row": round(total_amount / len(amount_values), 2) if amount_values else 0.0,
        "high_cost_threshold": round((sorted(amount_values, reverse=True)[min(4, len(amount_values) - 1)] if amount_values else 0), 2),
        "primary_amount_header": amount_header,
    }
    metadata.update({"sheet_name": parsed["sheet_name"], "xlsx_path": str(xlsx_path), "amount_header": amount_header})

    raw_json = {
        "metadata": metadata,
        "summary": summary,
        "column_totals": column_totals,
        "rows": rows,
    }
    json_path = report_dir / f"{args.report_prefix}.json"
    md_path = report_dir / f"{args.report_prefix}.md"
    dashboard_path = dashboard_dir / f"{args.report_prefix}.json"
    write_json(json_path, raw_json)
    md_path.write_text(build_markdown(summary, rows, column_totals, metadata), encoding="utf-8")
    write_json(dashboard_path, build_dashboard_payload(rows, summary, column_totals, metadata))
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")
    print(f"Saved: {dashboard_path}")


if __name__ == "__main__":
    main()
