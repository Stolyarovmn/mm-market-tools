#!/usr/bin/env python3
"""Sync local report data to GitHub Pages and Releases.

Usage:
    py -3 scripts/sync_to_pages.py

Reads from .env: GH_TOKEN, GH_REPO, GIST_ID
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.logging_config import get_logger
log = get_logger('scripts.sync_to_pages')

# ── Config ────────────────────────────────────────────────────────────────────

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
    for key in ("GH_TOKEN", "GH_REPO", "GIST_ID"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def gh_request(method, url, token, data=None, extra_headers=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "mm-market-tools/sync_to_pages",
    }
    if extra_headers:
        headers.update(extra_headers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode("utf-8")) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw.decode("utf-8")) if raw.strip() else {}


def upload_request(url, token, data_bytes, content_type="application/octet-stream"):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": content_type,
        "User-Agent": "mm-market-tools/sync_to_pages",
    }
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            result = json.loads(body) if body.strip() else {"uploaded": True}
            return resp.status, result
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            result = json.loads(body) if body else {}
        except Exception:
            result = {"raw": body.decode("utf-8", errors="replace")[:200]}
        return e.code, result


# ── Step A — Trees API batch commit ──────────────────────────────────────────

def step_a(token, repo):
    print("[A] Syncing JSON reports to docs/data/ via Trees API...")
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    files_map = {}

    def add_file(src_path, dst_path):
        p = ROOT / src_path
        if not p.exists():
            return
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            print(f"  Skip (>30d): {src_path}")
            return
        files_map[str(dst_path)] = p

    # daily_action_plan.json
    add_file("data/dashboard/daily_action_plan.json", "docs/data/daily_action_plan.json")

    # ab_result_*.json
    for f in (ROOT / "data/reports").glob("ab_result_*.json"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        if mtime >= cutoff:
            files_map[f"docs/data/reports/{f.name}"] = f

    # quick_wins_*.json
    for f in (ROOT / "data/dashboard").glob("quick_wins_*.json"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        if mtime >= cutoff:
            files_map[f"docs/data/dashboard/{f.name}"] = f

    if not files_map:
        print("[A] Nothing to sync.")
        return

    api = f"https://api.github.com/repos/{repo}"

    # Get main SHA
    status, ref_data = gh_request("GET", f"{api}/git/refs/heads/main", token)
    if status != 200:
        print(f"[A] ERROR getting main ref: {status} {ref_data}")
        return
    main_sha = ref_data["object"]["sha"]

    # Get base tree
    status, commit_data = gh_request("GET", f"{api}/git/commits/{main_sha}", token)
    if status != 200:
        print(f"[A] ERROR getting commit: {status}")
        return
    base_tree = commit_data["tree"]["sha"]

    # Create blobs
    tree_entries = []
    for dst_path, src_file in files_map.items():
        content = src_file.read_bytes()
        b64 = base64.b64encode(content).decode("ascii")
        status, blob = gh_request("POST", f"{api}/git/blobs", token, {
            "content": b64,
            "encoding": "base64",
        })
        if status not in (200, 201):
            print(f"[A] ERROR creating blob for {dst_path}: {status}")
            continue
        tree_entries.append({
            "path": dst_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"],
        })
        print(f"  blob: {dst_path}")

    if not tree_entries:
        print("[A] No blobs created, skipping.")
        return

    # Create tree
    status, tree_data = gh_request("POST", f"{api}/git/trees", token, {
        "base_tree": base_tree,
        "tree": tree_entries,
    })
    if status not in (200, 201):
        print(f"[A] ERROR creating tree: {status}")
        return

    # Create commit
    status, commit = gh_request("POST", f"{api}/git/commits", token, {
        "message": f"chore: sync report data to docs/data [{datetime.now(timezone.utc).date()}]",
        "tree": tree_data["sha"],
        "parents": [main_sha],
    })
    if status not in (200, 201):
        print(f"[A] ERROR creating commit: {status}")
        return

    # Update ref
    status, _ = gh_request("PATCH", f"{api}/git/refs/heads/main", token, {
        "sha": commit["sha"],
        "force": False,
    })
    if status not in (200, 201):
        print(f"[A] ERROR updating ref: {status}")
        return

    print(f"[A] Committed {len(tree_entries)} files → {commit['sha'][:8]}")
    time.sleep(10)


# ── Step B — data.db in GitHub Release ───────────────────────────────────────

def step_b(token, repo):
    print("[B] Uploading data.db to GitHub Release...")
    db_path = ROOT / "data.db"
    if not db_path.exists():
        print("[B] WARN: data.db not found, skipping.")
        return

    today = datetime.now(timezone.utc).date().isoformat()
    tag = f"data-{today}"
    api = f"https://api.github.com/repos/{repo}"

    # Check if release exists
    status, release = gh_request("GET", f"{api}/releases/tags/{tag}", token)
    if status == 200:
        release_id = release["id"]
        upload_url_base = release["upload_url"].split("{")[0]
        # Delete existing data.db asset
        for asset in release.get("assets", []):
            if asset["name"] == "data.db":
                gh_request("DELETE", f"{api}/releases/assets/{asset['id']}", token)
    else:
        # Create release
        status, release = gh_request("POST", f"{api}/releases", token, {
            "tag_name": tag,
            "name": f"Data snapshot {today}",
            "body": "Automated daily data snapshot. Generated locally.",
            "prerelease": True,
        })
        if status not in (200, 201):
            print(f"[B] ERROR creating release: {status} {release}")
            return
        release_id = release["id"]
        upload_url_base = release["upload_url"].split("{")[0]

    # Upload data.db
    data_bytes = db_path.read_bytes()
    upload_url = f"{upload_url_base}?name=data.db"
    status, result = upload_request(upload_url, token, data_bytes, "application/octet-stream")
    if status in (200, 201):
        print(f"[B] Uploaded data.db to release {tag} ({len(data_bytes):,} bytes)")
    else:
        print(f"[B] ERROR uploading data.db: {status} {result}")

    # Delete old releases (>7 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    status, releases = gh_request("GET", f"{api}/releases?per_page=100", token)
    if status == 200:
        for rel in releases:
            rtag = rel.get("tag_name", "")
            if not rtag.startswith("data-"):
                continue
            created = rel.get("created_at", "")
            try:
                rel_date = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                continue
            if rel_date < cutoff:
                print(f"[B] Deleting old release: {rtag}")
                gh_request("DELETE", f"{api}/releases/{rel['id']}", token)
                gh_request("DELETE", f"{api}/git/refs/tags/{rtag}", token)


# ── Step C — state.db in Private Gist ────────────────────────────────────────

def step_c(token, gist_id):
    print("[C] Uploading state.db to Private Gist...")
    db_path = ROOT / "state.db"
    if not db_path.exists():
        print("[C] WARN: state.db not found, skipping.")
        return
    if not gist_id:
        print("[C] WARN: GIST_ID not set, skipping.")
        return

    content = base64.b64encode(db_path.read_bytes()).decode("ascii")
    status, result = gh_request("PATCH", f"https://api.github.com/gists/{gist_id}", token, {
        "files": {
            "state.db": {"content": content},
        }
    })
    if status == 200:
        print(f"[C] state.db synced to Gist {gist_id[:8]}...")
    elif status == 404:
        print("[C] Gist not found, creating new private Gist...")
        status2, result2 = gh_request("POST", "https://api.github.com/gists", token, {
            "description": "mm-market-tools state.db",
            "public": False,
            "files": {
                "state.db": {"content": content},
            }
        })
        if status2 in (200, 201):
            new_id = result2["id"]
            print(f"[C] Created new Gist. Set GIST_ID={new_id} in .env")
        else:
            print(f"[C] ERROR creating Gist: {status2} {result2}")
    else:
        print(f"[C] ERROR patching Gist: {status} {result}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    env = load_env()
    token = env.get("GH_TOKEN", "")
    repo = env.get("GH_REPO", "Stolyarovmn/mm-market-tools")
    gist_id = env.get("GIST_ID", "")

    if not token:
        print("ERROR: GH_TOKEN not set in .env")
        return

    print(f"Syncing to {repo} ...")

    try:
        step_a(token, repo)
    except Exception as