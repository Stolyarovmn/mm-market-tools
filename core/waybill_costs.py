#!/usr/bin/env python3
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from core.io_utils import load_json
from core.xlsx_reader import list_xlsx_sheets, read_xlsx_sheet_rows, read_xlsx_sheet_rows_by_name


WAYBILL_SHEET_HINTS = [
    'товары на отправку',
    'товары',
    'отправку',
    'поставка',
]

COLUMN_ALIASES = {
    'barcode': ['штрихкод', 'штрих-код', 'barcode', 'bar code', 'ean'],
    'cogs': ['себестоимость', 'закупочная цена', 'цена закупки', 'purchase price', 'cost'],
    'quantity': ['количество', 'кол-во', 'qty', 'quantity'],
    'title': ['товар', 'наименование', 'название', 'product', 'title'],
    'sku': ['sku', 'артикул', 'seller sku', 'seller_sku_id', 'артикул продавца'],
    'product_id': ['product id', 'product_id', 'id товара'],
    'upd_id': ['упд', 'идентификатор упд', 'upd id'],
    'planned_supply_at': ['дата поставки', 'таймслот', 'дата отгрузки', 'поставка'],
    'waybill_id': ['номер накладной', 'накладная', 'waybill', 'waybill id'],
}


def _normalize_header(value: str) -> str:
    text = str(value or '').strip().lower().replace(' ', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text


def _pick_sheet_name(path):
    sheets = list_xlsx_sheets(path)
    for sheet in sheets:
        normalized = _normalize_header(sheet.get('name') or '')
        if any(hint in normalized for hint in WAYBILL_SHEET_HINTS):
            return sheet.get('name')
    return sheets[0]['name'] if sheets else None


def _find_column(headers, aliases):
    normalized_map = {_normalize_header(header): header for header in headers}
    for alias in aliases:
        if alias in normalized_map:
            return normalized_map[alias]
    for alias in aliases:
        for normalized, original in normalized_map.items():
            if alias in normalized:
                return original
    return None


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(' ', ' ').replace(' ', '').replace(',', '.')
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value):
    number = _to_float(value)
    if number is None:
        return None
    return int(number)


def load_waybill_source(path=None, input_json=None, sheet_name=None):
    if input_json:
        payload = load_json(input_json)
        rows = payload.get('rows') or payload.get('items') or []
        headers = sorted({key for row in rows for key in row.keys()}) if rows else []
        return {'sheet_name': payload.get('sheet_name') or 'synthetic_waybill', 'headers': headers, 'rows': rows, 'source': str(input_json)}
    if not path:
        raise ValueError('Either path or input_json must be provided')
    chosen_sheet = sheet_name or _pick_sheet_name(path)
    if chosen_sheet:
        payload = read_xlsx_sheet_rows_by_name(path, chosen_sheet)
    else:
        payload = read_xlsx_sheet_rows(path, sheet_index=0)
    payload['source'] = str(path)
    return payload


def normalize_waybill_rows(source_payload):
    headers = source_payload.get('headers') or []
    rows = source_payload.get('rows') or []
    mapping = {key: _find_column(headers, aliases) for key, aliases in COLUMN_ALIASES.items()}
    normalized = []
    unmatched = []
    for index, row in enumerate(rows, start=2):
        barcode = row.get(mapping['barcode']) if mapping.get('barcode') else None
        cogs = _to_float(row.get(mapping['cogs'])) if mapping.get('cogs') else None
        quantity = _to_int(row.get(mapping['quantity'])) if mapping.get('quantity') else None
        if not barcode and cogs is None and quantity is None:
            continue
        item = {
            'waybill_id': row.get(mapping['waybill_id']) if mapping.get('waybill_id') else None,
            'planned_supply_at': row.get(mapping['planned_supply_at']) if mapping.get('planned_supply_at') else None,
            'barcode': str(barcode).strip() if barcode is not None else None,
            'sku': row.get(mapping['sku']) if mapping.get('sku') else None,
            'product_id': row.get(mapping['product_id']) if mapping.get('product_id') else None,
            'title': row.get(mapping['title']) if mapping.get('title') else None,
            'quantity_supplied': quantity,
            'unit_cogs': cogs,
            'batch_cogs_total': round(cogs * quantity, 2) if cogs is not None and quantity is not None else None,
            'upd_id': row.get(mapping['upd_id']) if mapping.get('upd_id') else None,
            'source_row': index,
            'source_sheet': source_payload.get('sheet_name'),
            'source_file': source_payload.get('source'),
            'cost_source': 'waybill_excel',
        }
        if item['barcode'] or item['sku'] or item['product_id']:
            normalized.append(item)
        else:
            unmatched.append(item)
    summary = build_waybill_summary(normalized, unmatched, mapping, source_payload)
    return {'metadata': {'sheet_name': source_payload.get('sheet_name'), 'source_file': source_payload.get('source'), 'column_mapping': mapping}, 'summary': summary, 'rows': normalized, 'unmatched_rows': unmatched}


def build_waybill_summary(rows, unmatched_rows, mapping, source_payload):
    cogs_values = [row['unit_cogs'] for row in rows if row.get('unit_cogs') is not None]
    quantities = [row['quantity_supplied'] for row in rows if row.get('quantity_supplied') is not None]
    total_batch_cogs = sum(row.get('batch_cogs_total') or 0 for row in rows)
    return {
        'sheet_name': source_payload.get('sheet_name'),
        'source_file': source_payload.get('source'),
        'raw_rows_count': len(source_payload.get('rows') or []),
        'normalized_rows_count': len(rows),
        'unmatched_rows_count': len(unmatched_rows),
        'rows_with_barcode': sum(1 for row in rows if row.get('barcode')),
        'rows_with_cogs': sum(1 for row in rows if row.get('unit_cogs') is not None),
        'rows_with_quantity': sum(1 for row in rows if row.get('quantity_supplied') is not None),
        'total_quantity_supplied': sum(quantities) if quantities else 0,
        'total_batch_cogs': round(total_batch_cogs, 2),
        'avg_unit_cogs': round(sum(cogs_values) / len(cogs_values), 2) if cogs_values else None,
        'column_mapping_coverage': sum(1 for value in mapping.values() if value) / len(mapping) if mapping else 0,
    }


def build_historical_cogs_snapshot(rows):
    grouped = defaultdict(list)
    for row in rows:
        key = row.get('barcode') or row.get('sku') or row.get('product_id')
        if not key or row.get('unit_cogs') is None:
            continue
        grouped[str(key)].append(row)
    items = []
    for key, group in grouped.items():
        group = sorted(group, key=lambda row: (str(row.get('planned_supply_at') or ''), row.get('source_row') or 0))
        latest = group[-1]
        cogs_values = [row['unit_cogs'] for row in group if row.get('unit_cogs') is not None]
        items.append({
            'identity_key': key,
            'barcode': latest.get('barcode'),
            'sku': latest.get('sku'),
            'product_id': latest.get('product_id'),
            'title': latest.get('title'),
            'latest_unit_cogs': latest.get('unit_cogs'),
            'latest_planned_supply_at': latest.get('planned_supply_at'),
            'batch_count': len(group),
            'avg_unit_cogs': round(sum(cogs_values) / len(cogs_values), 2) if cogs_values else None,
            'min_unit_cogs': min(cogs_values) if cogs_values else None,
            'max_unit_cogs': max(cogs_values) if cogs_values else None,
            'sources': sorted({row.get('cost_source') or 'waybill_excel' for row in group}),
        })
    return {'items': items, 'summary': {'historical_cogs_items': len(items), 'items_with_cost': sum(1 for item in items if item.get('latest_unit_cogs') is not None)}}
