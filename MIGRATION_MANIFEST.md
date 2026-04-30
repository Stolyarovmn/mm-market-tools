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

## Decision Sync (2026-04-30)

The owner decisions collected during the PR `#26` review currently resolve the main policy questions like this:

- `data/dashboard/**` -> `local-only` generated pipeline state; the long-term delivery artifact is `data.db` via GitHub Releases, not tracked JSON payloads
- `data/normalized/**` -> `local-only` generated/intermediate state; small explicit fixtures may still be kept separately if needed for smoke/debug
- `data/action_center/**` -> split required; runtime state should stay local-only, while any future canonical rules/config should live in a separate explicit config surface
- `data/reviews/**` -> `local-only`; regenerate or fetch on demand
- `data/reply_config.json` -> split required between canonical reply rules and local/runtime overrides
- `docs/index.html` -> supported canonical Pages UI surface
- `index.html` -> non-canonical duplicate entrypoint; remove or replace with a minimal redirect/stub when the Pages cleanup PR lands
- `.github/workflows/daily-plan.yml` and `deploy-pages.yml` -> keep in repo, but rewrite around the approved Actions -> SQLite -> Releases -> Pages architecture

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
| `data/dashboard/**` | `—` | `local-only` | generated dashboard payloads are intermediate pipeline state, not canonical source | keep out of canonical git; rebuild in Actions/agent runs |
| `data/normalized/**` | `—` | `local-only` | generated/intermediate normalized layer should not remain as tracked bulk data | keep out of canonical git; optional fixtures must be explicit and narrow |
| `.github/workflows/daily-plan.yml` | same relative path | `migrate` | supported automation surface for data/SQLite generation remains in scope | keep and rewrite under the approved architecture |
| `.github/workflows/deploy-pages.yml` | same relative path | `migrate` | supported Pages/UI publishing remains in scope | keep and align with the approved architecture |
| `docs/index.html` | `docs/index.html` | `migrate` | canonical Pages UI surface remains in scope | keep and evolve as the main interface |
| `index.html` | `—` | `remove` | duplicate/non-canonical entrypoint once `docs/index.html` is canonical | remove or replace with a minimal redirect/stub in a focused cleanup PR |

## Top-Level Classification

| local_path | canonical_path | classification | reason | action |
|---|---|---|---|---|
| `.env.example` | `.env.example` | `migrate` | shared product config template | review local diff and keep canonical |
| `.github/workflows/daily-plan.yml` | `.github/workflows/daily-plan.yml` | `migrate` | scheduled product automation remains in scope, but should be rewritten around Actions -> SQLite -> Releases | keep in repo and update under issue `#20` |
| `.github/workflows/deploy-pages.yml` | `.github/workflows/deploy-pages.yml` | `migrate` | Pages/UI remains a supported product surface | keep in repo and align with canonical Pages entrypoint |
| `.github/workflows/sync-tasks.yml` | `.github/workflows/sync-tasks.yml` | `remove` | agent-task sync workflow, not product runtime | remove from canonical |
| `.gitignore` | `.gitignore` | `migrate` | policy file needed for later cleanup PRs | update after manifest review |
| `README.md` | `README.md` | `migrate` | product documentation | merge local product-facing edits; remove agent-only sections under `#19` |
| `ROADMAP.md` | `ROADMAP.md` | `migrate` | planning document | merge product roadmap; remove agent-only sections under `#19` |
| `CHANGELOG.md` | `CHANGELOG.md` | `migrate` | release/change history | merge intentional content only |
| `METHODOLOGY.md` | `METHODOLOGY.md` | `migrate` | product method documentation | preserve |
| `<root-level product .py files>` | same relative paths | `migrate` | primary application code | merge intentionally |
| `core/**` | `core/**` | `migrate` | application modules | merge intentionally |
| `ui/**` | `ui/**` | `migrate` | UI assets | merge intentionally |
| `data/dashboard/**` | `—` | `local-only` | generated dashboard payload layer is intermediate state once SQLite/Releases is canonical | ignore in canonical git and rebuild in pipeline |
| `data/normalized/**` | `—` | `local-only` | normalized layer is generated/intermediate and should not be tracked in bulk | ignore in canonical git; keep only explicit small fixtures if later needed |
| `data/local/**` | `—` | `local-only` | machine-specific runtime state | ignore and remove from git scope |
| `data/raw_reports/**` | `—` | `local-only` | imported raw source files | ignore and keep local |
| `data/job_runs/**` | `—` | `local-only` | execution logs and transient statuses | ignore and keep local |
| `data/action_center/**` | split by future policy | `needs-decision` | path should be split between canonical config/rules and runtime state instead of treated as one class | define canonical subset, keep computed state local-only |
| `data/reviews/**` | `—` | `local-only` | fetched/generated review payloads should be regenerated on demand | ignore in canonical git |
| `data/reply_config.json` | split into canonical + local files | `needs-decision` | reply rules should be versioned separately from local/runtime overrides | split before preserve |
| `reports/**` | `—` | `local-only` | generated analysis outputs | remove from canonical over time |
| `old/**` | `—` | `remove` | archived agent/process artifacts | do not migrate |
| `AUDIT_2026-04-08.md` | `AUDIT_2026-04-08.md` | `remove` | agent audit artifact, not product documentation | remove from canonical |
| `skills/mm-github/**` | `—` | `remove` | process skill layer for old GitHub-native workflow | remove from canonical |
| `docs/index.html` | `docs/index.html` | `migrate` | GitHub Pages UI remains a supported product surface and primary interface | keep as canonical entrypoint |
| `index.html` | `—` | `remove` | redundant non-canonical entrypoint once `docs/index.html` is canonical | remove or replace with a redirect/stub in a focused PR |

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
| `data/reviews/reviews.json` | `—` | `local-only` | fetched/generated payload | ignore and regenerate on demand |
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
| `docs/index.html` | `—` | `migrate` | canonical Pages UI already exists only in canonical and remains supported | keep |
| `index.html` | `—` | `remove` | duplicate/non-canonical root entrypoint | remove or replace with a redirect/stub |

## Needs-Decision Questions

The main repo-boundary questions are now resolved. Remaining focused follow-ups before the first bulk sync PR after this manifest:

1. Define the split for `data/action_center/**`: which files become canonical config/rules, and which stay runtime/local-only?
2. Split `data/reply_config.json` into canonical reply rules vs local/runtime overrides.
3. In the future Pages cleanup PR, choose whether `index.html` is removed entirely or replaced with a minimal redirect/stub to the canonical `docs/index.html` surface.

## Recommended Execution Order

1. Merge this manifest PR.
2. Open a focused removal PR for `AUDIT_2026-04-08.md`, `skills/mm-github/**`, and `sync-tasks.yml`.
3. Open a focused `.gitignore` / local-state PR for `data/local/**`, `data/job_runs/**`, and report outputs.
4. Open a focused migration PR for the local-only product code paths listed above.
5. Resolve the remaining split-focused follow-ups (`data/action_center/**`, `data/reply_config.json`, root `index.html`) in separate reviewable PRs.

## Non-Goals

This manifest does not:

- rewrite git history
- force-push any branch
- copy the whole local tree into canonical wholesale
- decide unresolved data-retention policy on behalf of the owner
