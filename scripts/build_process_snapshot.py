#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "process_snapshot.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def detect_repo() -> str:
    env_repo = os.environ.get("GH_REPO", "").strip()
    if env_repo:
        return env_repo
    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT,
            text=True,
        ).strip()
    except Exception as exc:
        raise RuntimeError("Cannot determine GH_REPO") from exc
    if remote.startswith("git@github.com:"):
        remote = remote.split(":", 1)[1]
    if remote.startswith("https://github.com/"):
        remote = remote.split("https://github.com/", 1)[1]
    return remote.removesuffix(".git")


def github_get(repo: str, path: str):
    url = f"https://api.github.com/repos/{repo}{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "mm-market-tools-process-view"})
    token = os.environ.get("GH_TOKEN", "").strip()
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def labels_for(item):
    return [label.get("name", "") for label in item.get("labels", [])]


def first_matching(labels, prefix):
    for label in labels:
        if label.startswith(prefix):
            return label
    return ""


def issue_meta(item, labels):
    status = first_matching(labels, "status:") or ("status:done" if item.get("state") == "closed" else "status:queued")
    return f"#{item['number']} · {status.replace('status:', '')} · {item.get('state', 'open')}"


def item_record(item):
    labels = labels_for(item)
    return {
        "title": item["title"],
        "url": item["html_url"],
        "meta": issue_meta(item, labels),
        "labels": [label for label in labels if label.startswith("type:") or label.startswith("status:") or label.startswith("priority:")],
    }


def workflow_record(run):
    return {
        "title": run.get("name") or run.get("display_title") or "workflow",
        "url": run.get("html_url") or "",
        "meta": f"{run.get('status', 'unknown')} · {run.get('head_branch', 'n/a')}",
        "labels": [run.get("conclusion") or run.get("status") or "unknown"],
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
    }


def memory_docs(repo: str):
    docs = [
        ("README.md", "Главный вход в проект", "https://github.com/{repo}/blob/main/README.md", ["memory", "canon"]),
        ("ROADMAP.md", "Приоритеты и backlog", "https://github.com/{repo}/blob/main/ROADMAP.md", ["memory", "planning"]),
        ("CHANGELOG.md", "История важных изменений", "https://github.com/{repo}/blob/main/CHANGELOG.md", ["memory", "history"]),
        ("METHODOLOGY.md", "Методологический слой", "https://github.com/{repo}/blob/main/METHODOLOGY.md", ["memory", "methodology"]),
        ("docs/github-operating-model.md", "GitHub-native process contract", "./github-operating-model.md", ["process"]),
        ("docs/github/labels-schema.md", "Schema labels", "./github/labels-schema.md", ["process"]),
        ("docs/github/project-fields.md", "Project fields", "./github/project-fields.md", ["process"])
    ]
    return [
        {"title": title, "url": url.format(repo=repo), "meta": meta, "labels": labels}
        for title, meta, url, labels in docs
    ]


def main():
    repo = detect_repo()
    issues = github_get(repo, "/issues?state=all&per_page=100")
    pulls = github_get(repo, "/pulls?state=open&per_page=30")
    try:
        runs = github_get(repo, "/actions/runs?per_page=10").get("workflow_runs", [])
    except Exception:
        runs = []

    task_issues = []
    disputes = []
    review_queue = []
    warnings = []

    for issue in issues:
        if "pull_request" in issue:
            continue
        labels = labels_for(issue)
        if "type:task" in labels:
            task_issues.append(item_record(issue))
            if "status:review" in labels or "needs:audit" in labels:
                review_queue.append(item_record(issue))
        elif "type:dispute" in labels:
            disputes.append(item_record(issue))

    if not task_issues:
        warnings.append({
            "title": "No native task issues found",
            "body": "Создай первую задачу через issue form `task.yml`, чтобы task lifecycle перестал зависеть от legacy-потока."
        })
    if not disputes:
        warnings.append({
            "title": "No formal disputes recorded",
            "body": "Это нормально, если конфликтов нет. Но спор без `type:dispute` issue не считается formal dispute."
        })

    workflow_rows = [workflow_record(run) for run in runs[:6]]
    failed_workflows = sum(1 for run in workflow_rows if run.get("conclusion") == "failure")

    snapshot = {
        "generated_at": now_iso(),
        "meta": {
            "repo": repo,
            "repo_url": f"https://github.com/{repo}",
            "issues_url": f"https://github.com/{repo}/issues",
            "pulls_url": f"https://github.com/{repo}/pulls",
            "actions_url": f"https://github.com/{repo}/actions",
            "project_url": f"https://github.com/{repo}/projects",
            "discussions_url": f"https://github.com/{repo}/discussions",
            "new_task_url": f"https://github.com/{repo}/issues/new?template=task.yml",
            "new_dispute_url": f"https://github.com/{repo}/issues/new?template=dispute.yml",
        },
        "summary": {
            "open_tasks": len(task_issues),
            "review_queue": len(review_queue),
            "open_disputes": len(disputes),
            "open_prs": len(pulls),
            "failed_workflows": failed_workflows,
            "warning_count": len(warnings),
        },
        "tasks": task_issues[:12],
        "review_queue": review_queue[:12],
        "disputes": disputes[:12],
        "pull_requests": [
            {
                "title": pr["title"],
                "url": pr["html_url"],
                "meta": f"#{pr['number']} · {pr['state']} · {pr['head']['ref']}",
                "labels": [label.get("name", "") for label in pr.get("labels", [])],
            }
            for pr in pulls[:8]
        ],
        "workflows": workflow_rows,
        "memory_docs": memory_docs(repo),
        "warnings": warnings,
    }

    OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"process snapshot build failed: {exc}", file=sys.stderr)
        sys.exit(1)
