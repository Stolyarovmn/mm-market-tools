#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from pathlib import Path

from core.dashboard_schema import DASHBOARD_SCHEMA_VERSION
from core.io_utils import write_csv_rows, write_json
from core.paths import DASHBOARD_DIR, NORMALIZED_DIR, REPORTS_DIR, ensure_dir, today_tag
from core.waybill_costs import build_historical_cogs_snapshot, load_waybill_source, normalize_waybill_rows


def parse_args():
    parser = argparse.ArgumentParser(description='Build waybill cost layer from Excel or synthetic JSON input.')
    parser.add_argument('--waybill-xlsx')
    parser.add_argument('--input-json')
    parser.add_argument('--sheet-name')
    parser.add_argument('--report-dir', default=str(REPORTS_DIR))
    parser.add_argument('--normalized-dir', default=str(NORMALIZED_DIR))
    parser.add_argument('--dashboard-dir', default=str(DASHBOARD_DIR))
    parser.add_argument('--report-prefix', default=f'waybill_cost_layer_{today_tag()}')
    return parser.parse_args()


def build_markdown(report):
    summary = report.get('summary') or {}
    metadata = report.get('metadata') or {}
    historical_items = ((report.get('historical_cogs') or {}).get('items') or [])
    lines = [
        '# Waybill Cost Layer',
        '',
        f"- source file: `{metadata.get('source_file')}`",
        f"- sheet: `{metadata.get('sheet_name')}`",
        f"- raw rows: `{summary.get('raw_rows_count')}`",
        f"- normalized rows: `{summary.get('normalized_rows_count')}`",
        f"- unmatched rows: `{summary.get('unmatched_rows_count')}`",
        f"- rows with barcode: `{summary.get('rows_with_barcode')}`",
        f"- rows with cogs: `{summary.get('rows_with_cogs')}`",
        f"- total quantity supplied: `{summary.get('total_quantity_supplied')}`",
        f"- total batch cogs: `{summary.get('total_batch_cogs')} ₽`",
        '',
        '## Column mapping',
        '',
    ]
    for key, value in (metadata.get('column_mapping') or {}).items():
        lines.append(f"- `{key}` -> `{value or 'н/д'}`")
    lines.extend(['', '## Historical COGS snapshot', ''])
    if not historical_items:
        lines.append('- Исторические cost-элементы пока не собраны.')
    else:
        for item in historical_items[:20]:
            lines.append(
                f"- `{item.get('identity_key')}` | latest cogs `{item.get('latest_unit_cogs')}` ₽ | batches `{item.get('batch_count')}` | title `{item.get('title') or 'н/д'}`"
            )
    return '\n'.join(lines)


def _build_actions(rows, historical_items):
    latest_batches = sorted(
        [row for row in rows if row.get('unit_cogs') is not None],
        key=lambda row: (str(row.get('planned_supply_at') or ''), row.get('batch_cogs_total') or 0),
        reverse=True,
    )
    gaps = [row for row in rows if not (row.get('barcode') or row.get('sku') or row.get('product_id'))]
    volatile_costs = [item for item in historical_items if (item.get('min_unit_cogs') is not None and item.get('max_unit_cogs') is not None and item.get('max_unit_cogs') > item.get('min_unit_cogs'))]
    return {
        'reorder_now': latest_batches[:8],
        'markdown_candidates': volatile_costs[:8],
        'protect_winners': sorted(rows, key=lambda row: row.get('batch_cogs_total') or 0, reverse=True)[:8],
        'watchlist_signals': gaps[:8],
    }


def _build_tables(rows, historical_items, unmatched_rows):
    latest_history = sorted(historical_items, key=lambda item: (item.get('latest_planned_supply_at') or '', item.get('latest_unit_cogs') or 0), reverse=True)
    return {
        'current_winners': sorted(rows, key=lambda row: row.get('batch_cogs_total') or 0, reverse=True)[:12],
        'profit_leaders': [
            {
                'title': item.get('title') or item.get('identity_key'),
                'gross_profit': item.get('latest_unit_cogs') or 0,
                'profit_margin_pct': item.get('avg_unit_cogs') or 0,
                'sku': item.get('sku'),
                'seller_sku_id': item.get('sku'),
                'product_id': item.get('product_id'),
            }
            for item in latest_history[:12]
        ],
        'stockout_risk': unmatched_rows[:12],
        'stale_stock': sorted(rows, key=lambda row: (row.get('quantity_supplied') or 0, row.get('unit_cogs') or 0), reverse=True)[:20],
    }


def _build_charts(rows, historical_items):
    quantity_by_supply = {}
    for row in rows:
        key = str(row.get('planned_supply_at') or 'н/д')[:10]
        quantity_by_supply[key] = quantity_by_supply.get(key, 0) + int(row.get('quantity_supplied') or 0)
    return {
        'cost_distribution': [
            {'key': 'Топ-8 batch rows', 'value': round(sum((row.get('batch_cogs_total') or 0) for row in sorted(rows, key=lambda item: item.get('batch_cogs_total') or 0, reverse=True)[:8]), 2)},
            {'key': 'Остальные batch rows', 'value': round(max(sum((row.get('batch_cogs_total') or 0) for row in rows) - sum((row.get('batch_cogs_total') or 0) for row in sorted(rows, key=lambda item: item.get('batch_cogs_total') or 0, reverse=True)[:8]), 0), 2)},
        ],
        'numeric_columns': [
            {'key': 'Исторических identity', 'value': len(historical_items)},
            {'key': 'Batch rows with cogs', 'value': sum(1 for row in rows if row.get('unit_cogs') is not None)},
            {'key': 'Batch rows with barcode', 'value': sum(1 for row in rows if row.get('barcode'))},
        ],
        'daily_returns': [
            {'key': key, 'value': value}
            for key, value in sorted(quantity_by_supply.items())[-12:]
        ],
    }


def build_dashboard_report(payload, historical):
    metadata = payload.get('metadata') or {}
    summary = payload.get('summary') or {}
    rows = payload.get('rows') or []
    unmatched_rows = payload.get('unmatched_rows') or []
    historical_items = (historical.get('items') or [])
    report = {
        'schema_version': DASHBOARD_SCHEMA_VERSION,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'report_kind': 'waybill_cost_layer',
        'metadata': {
            'window': {},
            'documents': {
                'waybill_mode': 'local' if str(metadata.get('source_file') or '').endswith('.json') else 'xlsx',
                'waybill_source_file': metadata.get('source_file'),
                'waybill_sheet_name': metadata.get('sheet_name'),
            },
            **metadata,
        },
        'kpis': {
            'total_skus': len(historical_items),
            'sold_skus': summary.get('rows_with_cogs') or 0,
            'revenue_total': summary.get('total_batch_cogs') or 0,
            'gross_profit_total': 0,
            'stockout_risk_count': summary.get('unmatched_rows_count') or 0,
            'stale_stock_count': 0,
            'waybill_rows_count': summary.get('normalized_rows_count') or 0,
            'historical_cogs_items_count': len(historical_items),
            'rows_without_identity_count': summary.get('unmatched_rows_count') or 0,
            'total_amount': summary.get('total_batch_cogs') or 0,
            'avg_amount_per_row': summary.get('avg_unit_cogs') or 0,
            'total_quantity_supplied': summary.get('total_quantity_supplied') or 0,
        },
        'actions': _build_actions(rows, historical_items),
        'tables': _build_tables(rows, historical_items, unmatched_rows),
        'charts': _build_charts(rows, historical_items),
        'insights': [],
        'summary': summary,
        'rows': rows,
        'unmatched_rows': unmatched_rows,
        'historical_cogs': historical,
    }
    return report


def main():
    args = parse_args()
    if not args.waybill_xlsx and not args.input_json:
        raise SystemExit('Provide --waybill-xlsx or --input-json')
    report_dir = ensure_dir(Path(args.report_dir))
    normalized_dir = ensure_dir(Path(args.normalized_dir))
    dashboard_dir = ensure_dir(Path(args.dashboard_dir))
    source = load_waybill_source(path=args.waybill_xlsx, input_json=args.input_json, sheet_name=args.sheet_name)
    payload = normalize_waybill_rows(source)
    historical = build_historical_cogs_snapshot(payload.get('rows') or [])
    report = build_dashboard_report(payload, historical)
    json_path = report_dir / f"{args.report_prefix}.json"
    csv_path = report_dir / f"{args.report_prefix}.csv"
    md_path = report_dir / f"{args.report_prefix}.md"
    normalized_path = normalized_dir / f"{args.report_prefix}.json"
    dashboard_path = dashboard_dir / f"{args.report_prefix}.json"
    write_json(json_path, report)
    write_csv_rows(csv_path, report.get('rows') or [])
    md_path.write_text(build_markdown(report), encoding='utf-8')
    write_json(normalized_path, report)
    write_json(dashboard_path, report)
    print(f'Saved: {json_path}')
    print(f'Saved: {csv_path}')
    print(f'Saved: {md_path}')
    print(f'Saved: {normalized_path}')
    print(f'Saved: {dashboard_path}')


if __name__ == '__main__':
    main()
