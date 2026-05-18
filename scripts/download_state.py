#!/usr/bin/env python3
"""Download state.db from Private Gist on first run / new PC."""
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    env = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    for key in ("GH_TOKEN", "GIST_ID"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def gh_get(url, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "mm-market-tools/download_state",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {}


def main():
    env = load_env()
    gist_id = env.get("GIST_ID", "")
    token = env.get("GH_TOKEN", "")

    # Ensure data/local exists
    local_dir = ROOT / "data/local"
    local_dir.mkdir(parents=True, exist_ok=True)

    if not gist_id:
        print("GIST_ID not set, skipping state restore")
        return

    if not token:
        print("GH_TOKEN not set, skipping state restore")
        return

    status, gist = gh_get(f"https://api.github.com/gists/{gist_id}", token)
    if status != 200:
        print(f"Could not fetch Gist (status {status}), starting fresh")
        return

    files = gist.get("files", {})
    if "state.db" not in files:
        print("No state.db in Gist yet, starting fresh")
        return

    raw_url = files["state.db"].get("raw_url", "")
    if not raw_url:
        print("No raw_url for state.db in Gist, starting fresh")
        return

    # Download raw content (it's base64-encoded)
    req = urllib.request.Request(raw_url, headers={"User-Agent": "mm-market-tools/download_state"})
    try:
        with urllib.request.urlopen(req) as resp:
            b64_content = resp.read().decode("ascii").strip()
    except Exception as e:
        print(f"Failed to download state.db content: {e}")
        return

    try:
        db_bytes = base64.b64decode(b64_content)
    except Exception as e:
        print(f"Failed to decode state.db content: {e}")
        return

    db_path = ROOT / "state.db"
    db_path.write_bytes(db_bytes)
    print(f"state.db restored from Gist ({len(db_bytes):,} bytes)")


if __name__ == "__main__":
    main()
