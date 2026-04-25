#!/usr/bin/env python3
from pathlib import Path
import subprocess


SYNTHETIC_INPUT = Path('/home/user/mm-market-tools/data/local/waybill_synthetic_sample.json')


def main():
    result = subprocess.run([
        'python3',
        '/home/user/mm-market-tools/build_waybill_cost_layer.py',
        '--input-json', str(SYNTHETIC_INPUT),
        '--report-prefix', 'waybill_cost_layer_smoke_2026-04-13'
    ], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(result.returncode)
    print('SMOKE_WAYBILL_COST_LAYER_OK')


if __name__ == '__main__':
    main()
