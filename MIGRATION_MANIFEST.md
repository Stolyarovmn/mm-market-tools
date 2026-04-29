# MIGRATION_MANIFEST

Status: draft for review  
Branch: `chore/migration-manifest`  
Related issues: `#10`, `#16`, `#17`, `#18`, `#19`, `#20`, `#21`, `#22`, `#23`

## Purpose

This manifest defines how to reconcile the local working tree at:

- local root: `/mnt/c/Users/maxim/Downloads/user/mm-market-tools`

into the canonical GitHub repository root:

- canonical root: `/mnt/c/Users/maxim/AIagentCowork/mm-market-tools-canonical`

This document is intentionally created in a canonical checkout. It does not perform migration. It only classifies paths and records the review order for later PRs.

## Classification Legend

- `migrate`: belongs in the canonical repository and should be preserved or merged there
- `remove`: should not remain in the canonical repository
- `local-only`: may exist on a developer machine, but should not be tracked in canonical git
- `needs-decision`: requires owner review before it is kept, removed, or moved

## Inventory Summary

Observed on 2026-04-30:

- local files: `406`
- canonical files: `382`
- shared file paths: `348`
- local-only file paths: `58`
- canonical-only file paths: `6`

The main divergence is not in core product code. It is in:

- local-only code additions not yet migrated
- generated reports and machine-local runtime state
- agent/process artifacts that should be removed or kept out of the product repo
- GitHub Pages / workflow / dashboard data areas that need explicit policy

## Path Mapping Rules

These rules cover the whole tree and are the primary classification layer. Explicit exception tables below override the broad rules when needed.

| local_path pattern | canonical_path pattern | classification | action |
|---|---|---|---|
| `<root-level product file>` | same relative path | `migrate` | compare local vs canonical content and merge intentionally |
| `core/**` | `core/**` | `migrate` | preserve as product code |
| `ui/**` | `ui/**` | `migrate` | preserve as product UI assets |
| `smoke_test_*.py` | same relative path | `migrate` | keep as executable diagnostics unless later consolidated |
| `mm-market-tools/<path>` | `<repo-root>/<path>` | see row-specific classification | nested local path maps directly to canonical repo root |
| `old/**` | `—` | `remove` | do not migrate into canonical product repo |
| `skills/mm-github/**` or `old/skills/mm-github/**` | `—` | `remove` | remove product-extraneous agent skill layer |
| `data/local/**` | `—` | `local-only` | ignore in canonical git |
| `data/job_runs/**` | `—` | `local-only` | ignore in canonical git |
| `data/raw_reports/**` | `—` | `local-only` | ignore in canonical git |
| `reports/**` | `—` | `local-only` | treat as generated output, not canonical source |
| `data/dashboard/**` | same relative path | `needs-decision` | decide whether dashboard JSONs are source artifacts or generated output |
| `data/normalized/**` | same relative path | `needs-decision` | decide whether normalized datasets belong in git |
| `.github/workflows/daily-plan.yml` | same relative path | `needs-decision` | decide whether scheduled automation still belongs here |
| `.github/workflows/deploy-pages.yml` | same relative path | `needs-decision` | decide whether Pages/UI publishing remains in scope |
| `docs/index.html` and `index.html` | same relative path | `needs-decision` | decide whether Pages entrypoints remain canonical |

## Top-Level Classification

| local_path | canonical_path | classification | reason | action |
|---|---|---|---|---|
| `.env.example` | `.env.example` | `migrate` | shared product config template | review local diff and keep canonical |
| `.github/workflows/daily-plan.yml` | `.github/workflows/daily-plan.yml` | `needs-decision` | depends on process-only skill layer and stale workflow assumptions | review under issue `#20` |
| `.github/workflows/deploy-pages.yml` | `.github/workflows/deploy-pages.yml` | `needs-decision` | depends on whether Pages/UI remains a product goal | review under issue `#20` |
| `.github/workflows/sync-tasks.yml` | `.github/workflows/sync-tasks.yml` | `remove` | agent-task sync workflow, not product runtime | remove from canonical |
| `.gitignore` | `.gitignore` | `migrate` | policy file needed for later cleanup PRs | update after manifest review |
| `README.md` | `README.md` | `migrate` | product documentation | merge local product-facing edits; remove agent-only sections under `#19` |
| `ROADMAP.md` | `ROADMAP.md` | `migrate` | planning document | merge product roadmap; remove agent-only sections under `#19` |
| `CHANGELOG.md` | `CHANGELOG.md` | `migrate` | release/change history | merge intentional content only |
| `METHODOLOGY.md` | `METHODOLOGY.md` | `migrate` | product method documentation | preserve |
| `<root-level product .py files>` | same relative paths | `migrate` | primary application code | merge intentionally |
| `core/**` | `core/**` | `migrate` | application modules | merge intentionally |
| `ui/**` | `ui/**` | `migrate` | UI assets | merge intentionally |
| `data/dashboard/**` | `data/dashboard/**` | `needs-decision` | currently tracked JSON outputs may be generated rather than source | decide retention policy |
| `data/normalized/**` | `data/normalized/**` | `needs-decision` | normalized datasets may be too environment-specific for canonical git | decide retention policy |
| `data/local/**` | `—` | `local-only` | machine-specific runtime state | ignore and remove from git scope |
| `data/raw_reports/**` | `—` | `local-only` | imported raw source files | ignore and keep local |
| `data/job_runs/**` | `—` | `local-only` | execution logs and transient statuses | ignore and keep local |
| `data/action_center/**` | same relative paths if kept | `needs-decision` | may be product state or runtime cache | decide source-vs-runtime policy |
| `data/reviews/**` | same relative paths if kept | `needs-decision` | may contain generated fetched review payloads | decide retention policy |
| `data/reply_config.json` | `data/reply_config.json` | `needs-decision` | config-like, but may contain machine or environment assumptions | review before preserve |
| `reports/**` | `—` | `local-only` | generated analysis outputs | remove from canonical over time |
| `old/**` | `—` | `remove` | archived agent/process artifacts | do not migrate |
| `AUDIT_2026-04-08.md` | `AUDIT_2026-04-08.md` | `remove` | agent audit artifact, not product documentation | remove from canonical |
| `skills/mm-github/**` | `—` | `remove` | process skill layer for old GitHub-native workflow | remove from canonical |
| `docs/index.html` | `docs/index.html` | `needs-decision` | GitHub Pages asset, canonical only today | decide whether product still ships Pages site |
| `index.html` | `index.html` | `needs-decision` | GitHub Pages root entrypoint, canonical only today | decide whether keep |

## Explicit Local-Only Source Files To Migrate

These files exist in local and are not present in canonical. They look like product code or executable diagnostics, so they should be reviewed for migration rather than dropped.

| local_path | canonical_path | classification | reason | action |
|---|---|---|---|---|
| `build_sku_vitality_report.py` | `build_sku_vitality_report.py` | `migrate` | product report builder missing on GitHub | review and add |
| `core/action_center.py` | `core/action_center.py` | `migrate` | product module missing on GitHub | review and add |
| `core/cost_context.py` | `core/cost_context.py` | `migrate` | product module missing on GitHub | review and add |
| `core/schema_versioning.py` | `core/schema_versioning.py` | `migrate` | product module missing on GitHub | review and add |
| `smoke_test_cogs_override_continuity.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_entity_browse.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_entity_history.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_entry_window_matrix.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_market_margin_fit_dashboard.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_market_margin_fit_sourcing.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_market_vs_shop.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_price_trap_dashboard.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_schema_versioning.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_sku_vitality.py` | same relative path | `migrate` | diagnostic code | review and add |
| `smoke_test_step_progress.py` | same relative path | `migrate` | diagnostic code | review and add |
| `ui/action_center.css` | `ui/action_center.css` | `migrate` | UI asset missing on GitHub | review and add |

## Explicit Local-Only Runtime / Artifact Paths

These files exist only in local and should not be migrated as canonical source.

| local_path | canonical_path | classification | reason | action |
|---|---|---|---|---|
| `data/job_runs/**` | `—` | `local-only` | transient execution logs and status files | ignore and keep local |
| `data/local/action_center.json` | `—` | `local-only` | machine-local state | ignore and keep local |
| `data/local/cogs_overrides.json` | `—` | `local-only` | machine-local overrides with path coupling | ignore and keep local |
| `data/local/entity_history_index.json` | `—` | `local-only` | machine-local index | ignore and keep local |
| `data/local/product_content_cache.json` | `—` | `local-only` | runtime cache | ignore and keep local |
| `data/local/session_status_2026-04-10.json` | `—` | `local-only` | transient session status | ignore and keep local |
| `data/local/waybill_synthetic_sample.json` | `—` | `local-only` | local synthetic data | ignore and keep local |
| `data/reviews/reviews.json` | `—` | `local-only` | fetched/generated payload | ignore until retention policy is defined |
| `old/AUDIT_2026-04-08.md` | `—` | `remove` | agent audit artifact | do not migrate |
| `old/automation_reports/executions/TASK-010_execution_1777161138.md` | `—` | `remove` | agent execution artifact | do not migrate |
| `old/metrics.log` | `—` | `remove` | runtime log artifact | do not migrate |
| `old/outbox/for-orchestrator.md` | `—` | `remove` | agent IPC artifact | do not migrate |
| `old/skills/mm-github/SKILL.md` | `—` | `remove` | old process skill | do not migrate |
| `old/skills/mm-github/mm_github.py` | `—` | `remove` | old process skill code | do not migrate |
| `old/sync-tasks.yml` | `—` | `remove` | old process workflow | do not migrate |

## Canonical-Only Paths Requiring Reconciliation

These paths are present in the canonical repo but absent from the local nested tree.

| canonical_path | local_path | classification | reason | action |
|---|---|---|---|---|
| `.github/workflows/sync-tasks.yml` | `—` | `remove` | stale task-sync workflow | remove from canonical |
| `AUDIT_2026-04-08.md` | `—` | `remove` | agent audit artifact | remove from canonical |
| `skills/mm-github/SKILL.md` | `—` | `remove` | old process skill | remove from canonical |
| `skills/mm-github/mm_github.py` | `—` | `remove` | old process skill code | remove from canonical |
| `docs/index.html` | `—` | `needs-decision` | Pages asset exists only in canonical | review keep/remove |
| `index.html` | `—` | `needs-decision` | Pages root entrypoint exists only in canonical | review keep/remove |

## Needs-Decision Questions

These questions should be answered before the first bulk sync PR after this manifest:

1. Should `data/dashboard/**` remain tracked, or should it become generated output like `reports/**`?
2. Should `data/normalized/**` remain tracked, or move to local/generated storage?
3. Should `data/action_center/**` be treated as product seed data or runtime state?
4. Should `data/reviews/**` be retained in git, or regenerated on demand?
5. Is `data/reply_config.json` canonical product config, or environment-specific state?
6. Do `docs/index.html` and `index.html` still represent a supported Pages/UI surface?
7. Should `.github/workflows/daily-plan.yml` and `deploy-pages.yml` stay in the product repo after cleanup?

## Recommended Execution Order

1. Merge this manifest PR.
2. Open a focused removal PR for `AUDIT_2026-04-08.md`, `skills/mm-github/**`, and `sync-tasks.yml`.
3. Open a focused `.gitignore` / local-state PR for `data/local/**`, `data/job_runs/**`, and report outputs.
4. Open a focused migration PR for the local-only product code paths listed above.
5. Resolve the `needs-decision` data/workflow/UI areas in separate reviewable PRs.

## Non-Goals

This manifest does not:

- rewrite git history
- force-push any branch
- copy the whole local tree into canonical wholesale
- decide unresolved data-retention policy on behalf of the owner
