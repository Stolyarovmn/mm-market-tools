#!/usr/bin/env bash
set -euo pipefail

required_files=(
  ".github/ISSUE_TEMPLATE/task.yml"
  ".github/ISSUE_TEMPLATE/dispute.yml"
  ".github/ISSUE_TEMPLATE/process-change.yml"
  ".github/ISSUE_TEMPLATE/blocker-escalation.yml"
  ".github/ISSUE_TEMPLATE/config.yml"
  ".github/PULL_REQUEST_TEMPLATE.md"
  ".github/CODEOWNERS"
  ".github/workflows/process-hygiene.yml"
  "docs/github-operating-model.md"
  "docs/github/labels-schema.md"
  "docs/github/project-fields.md"
  "docs/process.html"
  "docs/process.css"
  "docs/process.js"
  "docs/process_snapshot.json"
  "scripts/build_process_snapshot.py"
)

for path in "${required_files[@]}"; do
  [[ -f "$path" ]] || {
    echo "missing file: $path"
    exit 1
  }
done

grep -q "GitHub-native" docs/github-operating-model.md || {
  echo "missing operating model wording"
  exit 1
}

grep -q "Status" docs/github/project-fields.md || {
  echo "missing project status doc"
  exit 1
}

grep -qi "linked task" .github/PULL_REQUEST_TEMPLATE.md || {
  echo "missing linked task section"
  exit 1
}

grep -qi "process hygiene" .github/workflows/process-hygiene.yml || {
  echo "missing process hygiene workflow"
  exit 1
}

grep -q "process.html" docs/index.html || {
  echo "missing process page link in dashboard"
  exit 1
}

echo "github process layer files present"
