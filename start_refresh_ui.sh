#!/usr/bin/env bash
set -euo pipefail
cd /home/user/mm-market-tools
python3 web_refresh_server.py --host 127.0.0.1 --port 8040
