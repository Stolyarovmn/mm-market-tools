#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_json = tmp_path / "waybill_synthetic_sample.json"
        payload = {
            "sheet_name": "synthetic_waybill",
            "rows": [
                {
                    "штрихкод": "460000000001",
                    "себестоимость": 123.45,
                    "количество": 2,
                    "товар": "Пазл Три кота",
                    "артикул": "SKU-1",
                    "waybill id": "WB-1",
                }
            ],
        }
        input_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([
            'python3',
            str(PROJECT_ROOT / 'build_waybill_cost_layer.py'),
            '--input-json', str(input_json),
            '--report-dir', str(tmp_path / 'reports'),
            '--normalized-dir', str(tmp_path / 'normalized'),
            '--dashboard-dir', str(tmp_path / 'dashboard'),
            '--report-prefix', 'waybill_cost_layer_smoke_2026-04-13'
        ], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            raise SystemExit(result.returncode)
    print('SMOKE_WAYBILL_COST_LAYER_OK')


if __name__ == '__main__':
    main()
