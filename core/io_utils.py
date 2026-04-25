#!/usr/bin/env python3
import csv
import json


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_csv_rows(path, rows):
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as handle:
        if not fieldnames:
            handle.write("")
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
