#!/usr/bin/env python3
"""
mm-github — unified GitHub operations skill for mm-market-tools.

Works identically for both Claude (Cowork) and Codex (CLI).
Wraps `gh` + `git` with project-specific conventions.

Usage:
  python3 skills/mm-github/mm_github.py <command> [args]

Commands:
  status              Show repo health, CI status, open issues, Pages URL
  setup               Initialize GitHub remote (first-time setup)
  push [message]      Commit all changes and push to origin/main
  deploy-dashboard    Push dashboard HTML to gh-pages branch → GitHub Pages
  sync-tasks          Sync TASKS.md → GitHub Issues (create/update)
  update-wiki         Push docs/*.md to GitHub Wiki
  new-release [ver]   Tag current state as a release
  lock <file>         Mark file as "in-use" by current agent
  unlock <file>       Release lock
  check-locks         List all active file locks

Environment:
  GH_TOKEN   — GitHub PAT with repo + workflow scopes
  GH_REPO    — owner/repo slug (e.g. "wonders-shop/mm-market-tools")
  AGENT_NAME — "claude" or "codex" (for lock attribution)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCKS_DIR    = PROJECT_ROOT / ".locks"
TASKS_FILE   = PROJECT_ROOT / "TASKS.md"
DOCS_DIR     = PROJECT_ROOT / "docs"
DASHBOARD_SRC = PROJECT_ROOT.parent / "magnit_command_center_v3.html"  # latest artifact
GH_BIN       = Path("/sessions/keen-wizardly-turing/gh_bin")  # Cowork session binary
GH_CMD       = str(GH_BIN) if GH_BIN.exists() else "gh"

AGENT_NAME   = os.environ.get("AGENT_NAME", "unknown")
GH_TOKEN     = os.environ.get("GH_TOKEN", "")
GH_REPO      = os.environ.get("GH_REPO", "")

# ── Helpers ───────────────────────────────────────────────────────────────────
def run(cmd: list[str], check=True, capture=False, cwd=None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if GH_TOKEN:
        env["GH_TOKEN"] = GH_TOKEN
    return subprocess.run(
        cmd, check=check, capture_output=capture, text=True,
        cwd=cwd or str(PROJECT_ROOT), env=env
    )

def git(*args, capture=False) -> str:
    r = run(["git"] + list(args), capture=capture)
    return r.stdout.strip() if capture else ""

def gh(*args, capture=False) -> str:
    r = run([GH_CMD] + list(args), capture=capture)
    return r.stdout.strip() if capture else ""

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def ok(msg): print(f"  ✓  {msg}")
def err(msg): print(f"  ✗  {msg}", file=sys.stderr)
def info(msg): print(f"  →  {msg}")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_status(args):
    """Show current repo/CI/Pages health."""
    print("\n── mm-market-tools status ──────────────────────────")

    # Git state
    branch = git("branch", "--show-current", capture=True)
    uncommitted = git("status", "--porcelain", capture=True)
    last_commit = git("log", "--oneline", "-1", capture=True)
    info(f"Branch: {branch}   Last commit: {last_commit}")
    if uncommitted:
        print(f"     Uncommitted changes ({len(uncommitted.splitlines())} files)")
    else:
        ok("Working tree clean")

    # Remote
    remote = git("remote", "get-url", "origin", capture=True) if run(
        ["git", "remote"], check=False, capture=True, cwd=str(PROJECT_ROOT)
    ).stdout.strip() else ""
    if remote:
        info(f"Remote: {remote}")
    else:
        err("No remote set — run: mm-github setup")

    # Active locks
    locks = list(LOCKS_DIR.glob("*.lock")) if LOCKS_DIR.exists() else []
    if locks:
        print(f"\n  🔒 Active locks ({len(locks)}):")
        for lf in locks:
            data = json.loads(lf.read_text())
            print(f"     {data['file']}  [{data['agent']}  {data['at'][:16]}]")
    else:
        ok("No file locks")

    # Tasks summary
    if TASKS_FILE.exists():
        text = TASKS_FILE.read_text()
        pending   = len(re.findall(r"\[pending\]",     text, re.I))
        active    = len(re.findall(r"\[in.progress\]", text, re.I))
        done      = len(re.findall(r"\[completed?\]",  text, re.I))
        info(f"Tasks: {active} active · {pending} pending · {done} done")

    # GitHub Pages URL
    if GH_REPO:
        owner, repo = GH_REPO.split("/")
        pages_url = f"https://{owner}.github.io/{repo}/"
        info(f"Pages URL: {pages_url}")

    print()


def cmd_setup(args):
    """First-time: create GitHub repo and push."""
    if not GH_TOKEN:
        err("GH_TOKEN not set. Export it before running setup.")
        sys.exit(1)

    repo_name = getattr(args, "repo", None) or input("Repo name (e.g. mm-market-tools): ").strip()
    visibility = getattr(args, "visibility", "private")

    print(f"\n── Creating GitHub repo: {repo_name} ({visibility}) ──")

    # Authenticate gh
    run([GH_CMD, "auth", "login", "--with-token"], check=False,
        cwd=str(PROJECT_ROOT))

    # Create repo
    gh("repo", "create", repo_name,
       f"--{visibility}",
       "--description", "MM Market Tools — Seller analytics for Магнит Маркет",
       "--source", ".",
       "--remote", "origin",
       "--push")

    ok(f"Repo created and pushed: github.com/$(gh api user -q .login)/{repo_name}")

    # Enable GitHub Pages from docs/ on main branch
    gh("api", f"repos/:owner/{repo_name}/pages",
       "--method", "POST",
       "--field", "source[branch]=main",
       "--field", "source[path]=/docs")

    ok("GitHub Pages enabled → docs/ on main branch")
    info(f"Dashboard will be live at: https://$(gh api user -q .login).github.io/{repo_name}/")


def cmd_push(args):
    """Commit all changes and push."""
    message = getattr(args, "message", None) or f"chore: auto-push by {AGENT_NAME} [{now_iso()[:16]}]"
    uncommitted = git("status", "--porcelain", capture=True)
    if not uncommitted:
        ok("Nothing to commit")
        return
    git("add", "-A")
    git("commit", "-m", message)
    git("push", "origin", "main")
    ok(f"Pushed: {message}")


def cmd_deploy_dashboard(args):
    """Copy dashboard HTML to docs/index.html and push → GitHub Pages."""
    # Find latest dashboard
    src = DASHBOARD_SRC
    if not src.exists():
        # Try other versions
        for v in ["v3", "v2", "v1", ""]:
            cand = PROJECT_ROOT.parent / f"magnit_command_center{'_'+v if v else ''}.html"
            if cand.exists():
                src = cand
                break
    if not src or not src.exists():
        err(f"Dashboard HTML not found near {PROJECT_ROOT.parent}")
        sys.exit(1)

    DOCS_DIR.mkdir(exist_ok=True)
    dest = DOCS_DIR / "index.html"
    dest.write_bytes(src.read_bytes())
    ok(f"Copied {src.name} → docs/index.html  ({src.stat().st_size // 1024}KB)")

    # Also write a simple redirect at root for convenience
    root_index = PROJECT_ROOT / "index.html"
    root_index.write_text(
        '<meta http-equiv="refresh" content="0;url=docs/index.html">\n'
        '<a href="docs/index.html">Открыть дашборд →</a>\n'
    )

    cmd_push(type("A", (), {"message": f"deploy: dashboard update [{now_iso()[:10]}]"})())
    info("GitHub Pages will update in ~1 minute")
    if GH_REPO:
        owner, repo = GH_REPO.split("/")
        ok(f"Live at: https://{owner}.github.io/{repo}/")


def cmd_sync_tasks(args):
    """Sync TASKS.md → GitHub Issues."""
    if not GH_TOKEN or not GH_REPO:
        err("GH_TOKEN and GH_REPO required for sync-tasks")
        sys.exit(1)

    if not TASKS_FILE.exists():
        err("TASKS.md not found")
        return

    # Parse TASKS.md  (format: - [ ] / - [x] / #N. [status] Title)
    tasks = []
    for line in TASKS_FILE.read_text().splitlines():
        m = re.match(r"^#(\d+)\.\s+\[(\w[\w\s]*)\]\s+(.+)$", line)
        if m:
            tasks.append({
                "id":     m.group(1),
                "status": m.group(2).strip().lower(),
                "title":  m.group(3).strip(),
            })

    info(f"Found {len(tasks)} tasks in TASKS.md")

    # Get existing issues
    existing_raw = gh("issue", "list", "--repo", GH_REPO,
                      "--state", "all", "--json", "number,title,state,labels",
                      "--limit", "200", capture=True)
    existing = json.loads(existing_raw) if existing_raw else []
    existing_by_title = {i["title"]: i for i in existing}

    created = updated = skipped = 0
    for t in tasks:
        label = "status:done" if "complet" in t["status"] else (
                "status:active" if "progress" in t["status"] else "status:pending")
        if t["title"] in existing_by_title:
            skipped += 1
        else:
            # Create new issue
            try:
                gh("issue", "create",
                   "--repo", GH_REPO,
                   "--title", t["title"],
                   "--label", label,
                   "--body", f"Synced from TASKS.md #{t['id']}\nStatus: {t['status']}")
                created += 1
            except Exception as e:
                err(f"Failed to create issue for #{t['id']}: {e}")

    ok(f"Tasks synced: {created} created, {updated} updated, {skipped} skipped")


def cmd_update_wiki(args):
    """Push docs/*.md to the GitHub Wiki (separate wiki repo)."""
    if not GH_REPO:
        err("GH_REPO not set")
        return

    wiki_url = f"https://github.com/{GH_REPO}.wiki.git"
    wiki_dir = PROJECT_ROOT / ".wiki_tmp"

    # Clone wiki
    run(["git", "clone", wiki_url, str(wiki_dir)], check=False)

    if not wiki_dir.exists():
        err(f"Could not clone wiki: {wiki_url}\nEnable wiki in repo Settings first.")
        return

    # Copy docs
    docs = list(DOCS_DIR.glob("*.md")) if DOCS_DIR.exists() else []
    for doc in docs:
        import shutil
        shutil.copy(doc, wiki_dir / doc.name)

    # Also copy project root docs
    for name in ["README.md", "ROADMAP.md", "METHODOLOGY.md"]:
        src = PROJECT_ROOT / name
        if src.exists():
            import shutil
            shutil.copy(src, wiki_dir / name)

    # Commit and push wiki
    run(["git", "add", "-A"], cwd=str(wiki_dir))
    run(["git", "commit", "-m", f"wiki: sync from mm-market-tools [{now_iso()[:10]}]"],
        cwd=str(wiki_dir), check=False)
    run(["git", "push"], cwd=str(wiki_dir), check=False)

    import shutil
    shutil.rmtree(wiki_dir, ignore_errors=True)
    ok(f"Wiki updated: {len(docs)} docs pushed")


def cmd_new_release(args):
    """Tag current commit as a release."""
    version = getattr(args, "version", None)
    if not version:
        # Auto-derive from iteration in CLAUDE.md or latest tag
        last_tag = git("describe", "--tags", "--abbrev=0", capture=True)
        if last_tag and re.match(r"v\d+\.\d+", last_tag):
            major, minor = last_tag.lstrip("v").split(".")[:2]
            version = f"v{major}.{int(minor)+1}"
        else:
            version = "v0.4"

    notes = f"Iteration {version}\nAuto-release from mm-github skill.\nDate: {now_iso()[:10]}"
    gh("release", "create", version,
       "--repo", GH_REPO,
       "--title", f"Итерация {version}",
       "--notes", notes)
    ok(f"Release {version} created")


def cmd_lock(args):
    """Mark a file as in-use by this agent."""
    LOCKS_DIR.mkdir(exist_ok=True)
    file_path = args.file
    lock_file = LOCKS_DIR / (file_path.replace("/", "_").replace(".", "_") + ".lock")
    lock_file.write_text(json.dumps({
        "file": file_path,
        "agent": AGENT_NAME,
        "at": now_iso(),
    }, ensure_ascii=False, indent=2))
    ok(f"Locked: {file_path}  [{AGENT_NAME}]")


def cmd_unlock(args):
    """Release a file lock."""
    file_path = args.file
    lock_file = LOCKS_DIR / (file_path.replace("/", "_").replace(".", "_") + ".lock")
    if lock_file.exists():
        lock_file.unlink()
        ok(f"Unlocked: {file_path}")
    else:
        info(f"No lock found for: {file_path}")


def cmd_check_locks(args):
    """List all active locks."""
    locks = list(LOCKS_DIR.glob("*.lock")) if LOCKS_DIR.exists() else []
    if not locks:
        ok("No active locks")
        return
    print(f"\n  Active locks ({len(locks)}):")
    for lf in locks:
        d = json.loads(lf.read_text())
        print(f"    {d['file']:40s}  [{d['agent']}]  {d['at'][:16]}")
    print()


# ── Dispatch ──────────────────────────────────────────────────────────────────
COMMANDS = {
    "status":           cmd_status,
    "setup":            cmd_setup,
    "push":             cmd_push,
    "deploy-dashboard": cmd_deploy_dashboard,
    "sync-tasks":       cmd_sync_tasks,
    "update-wiki":      cmd_update_wiki,
    "new-release":      cmd_new_release,
    "lock":             cmd_lock,
    "unlock":           cmd_unlock,
    "check-locks":      cmd_check_locks,
}

def main():
    parser = argparse.ArgumentParser(
        description="mm-github — unified GitHub skill for Claude + Codex",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(f"  {k}" for k in COMMANDS)
    )
    parser.add_argument("command", choices=list(COMMANDS))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    # Common optional flags
    parser.add_argument("--message", "-m", help="Commit message (for push)")
    parser.add_argument("--version", "-v", help="Version tag (for new-release)")
    parser.add_argument("--repo",    "-r", help="Repo name (for setup)")
    parser.add_argument("--file",    "-f", help="File path (for lock/unlock)")
    parser.add_argument("--visibility", default="private",
                        choices=["private", "public", "internal"])

    args = parser.parse_args()
    COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
