#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
import re
import zipfile


NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}


def _column_letters(cell_ref: str) -> str:
    letters = []
    for char in cell_ref:
        if char.isalpha():
            letters.append(char)
        else:
            break
    return "".join(letters)


def _normalize_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\xa0", " ").replace(" ", "")
    if not text:
        return None
    text = text.replace(",", ".")
    if text.endswith("%"):
        text = text[:-1]
    if not re.fullmatch(r"[-+]?\d+(\.\d+)?", text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _shared_strings(archive: zipfile.ZipFile):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall("x:si", NS):
        text_parts = []
        for node in item.findall(".//x:t", NS):
            text_parts.append(node.text or "")
        values.append("".join(text_parts))
    return values


def _sheet_targets(archive: zipfile.ZipFile):
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib.get("Id"): rel.attrib.get("Target")
        for rel in rels.findall("r:Relationship", REL_NS)
    }
    sheets = []
    for sheet in workbook.findall("x:sheets/x:sheet", NS):
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_map.get(rel_id)
        if not target:
            continue
        sheets.append(
            {
                "name": sheet.attrib.get("name") or target,
                "path": f"xl/{target}" if not target.startswith("xl/") else target,
            }
        )
    return sheets


def _cell_value(cell, shared_strings):
    cell_type = cell.attrib.get("t")
    value_node = cell.find("x:v", NS)
    inline_node = cell.find("x:is/x:t", NS)
    if cell_type == "inlineStr":
        return inline_node.text if inline_node is not None else ""
    if value_node is None:
        return ""
    raw = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw
    return raw


def read_xlsx_sheet_rows(path, sheet_index=0):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        shared_strings = _shared_strings(archive)
        sheets = _sheet_targets(archive)
        if not sheets:
            raise ValueError(f"No worksheets found in {path}")
        target_sheet = sheets[sheet_index]
        root = ET.fromstring(archive.read(target_sheet["path"]))
        raw_rows = []
        for row in root.findall("x:sheetData/x:row", NS):
            row_values = {}
            for cell in row.findall("x:c", NS):
                ref = cell.attrib.get("r") or ""
                row_values[_column_letters(ref)] = _cell_value(cell, shared_strings)
            raw_rows.append(row_values)
        if not raw_rows:
            return {"sheet_name": target_sheet["name"], "headers": [], "rows": []}
        header_map = raw_rows[0]
        ordered_columns = sorted(header_map.keys(), key=lambda col: (len(col), col))
        headers = [str(header_map.get(col, "")).strip() or col for col in ordered_columns]
        rows = []
        for raw_row in raw_rows[1:]:
            row = {}
            for col, header in zip(ordered_columns, headers):
                value = raw_row.get(col, "")
                row[header] = value
                numeric_value = _normalize_number(value)
                if numeric_value is not None:
                    row[f"{header}__num"] = numeric_value
            if any(str(value).strip() for key, value in row.items() if not key.endswith("__num")):
                rows.append(row)
        return {"sheet_name": target_sheet["name"], "headers": headers, "rows": rows}


def list_xlsx_sheets(path):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        return _sheet_targets(archive)


def read_xlsx_sheet_rows_by_name(path, sheet_name):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        shared_strings = _shared_strings(archive)
        sheets = _sheet_targets(archive)
        target_sheet = None
        for sheet in sheets:
            if (sheet.get("name") or "").strip() == str(sheet_name).strip():
                target_sheet = sheet
                break
        if not target_sheet:
            raise ValueError(f"Worksheet not found: {sheet_name}")
        root = ET.fromstring(archive.read(target_sheet["path"]))
        raw_rows = []
        for row in root.findall("x:sheetData/x:row", NS):
            row_values = {}
            for cell in row.findall("x:c", NS):
                ref = cell.attrib.get("r") or ""
                row_values[_column_letters(ref)] = _cell_value(cell, shared_strings)
            raw_rows.append(row_values)
        if not raw_rows:
            return {"sheet_name": target_sheet["name"], "headers": [], "rows": []}
        header_map = raw_rows[0]
        ordered_columns = sorted(header_map.keys(), key=lambda col: (len(col), col))
        headers = [str(header_map.get(col, "")).strip() or col for col in ordered_columns]
        rows = []
        for raw_row in raw_rows[1:]:
            row = {}
            for col, header in zip(ordered_columns, headers):
                value = raw_row.get(col, "")
                row[header] = value
                numeric_value = _normalize_number(value)
                if numeric_value is not None:
                    row[f"{header}__num"] = numeric_value
            if any(str(value).strip() for key, value in row.items() if not key.endswith("__num")):
                rows.append(row)
        return {"sheet_name": target_sheet["name"], "headers": headers, "rows": rows}
