# Agents — Current Implementation Index

> **What this is.** A pointer from the agent role definitions in this directory
> to the GitHub Actions workflows that actually run them today. The per-role
> `SOUL.md` / `SKILL.md` / `prompt_config.md` files describe the *intended*
> responsibilities of each role; **the workflows in `.github/workflows/` are
> the executable source of truth.**
>
> If a SOUL describes a `shared-memory/tasks/...` flow or a manual `coordinator`
> dispatch, treat that as historical context. State is no longer carried in
> `shared-memory/`; it now lives in GitHub Issues, labels, and PRs, and roles
> are triggered by workflow events (PRs, pushes, schedules, issue labels).

---

## Role → workflow mapping

| Role (this directory) | Implemented by | Trigger | Notes |
|---|---|---|---|
| `code-review-agent` / `code_review` | `.github/workflows/pipeline-code-review.yml` | `pull_request` | Runs `scripts/ci/run_claude_code_review.py` → posts inline + summary comments on the PR. Resolution of fixed threads is via GraphQL. |
| `implement-agent` / `task-agent` | `.github/workflows/implement-ready-issues.yml` | `schedule: */30` + `workflow_dispatch` | Two-stage: `scripts/ci/claim_and_plan_issue.py` (stage 1: claim `wip`, write plan to `.plans/issue-<N>.md`), then `scripts/ci/execute_implementation.py` (stage 2: implement + run tests + open PR). |
| `orchestrator` / `manager-agent` / `coordinator` | **No single workflow.** Coordination is decentralised across the workflows below; there is no central dispatcher. | — | Issue triage → triage labels via `monitor-issues.yml`. Ready issues → implementation via `implement-ready-issues.yml`. Push-to-feature → PR via `auto-pr.yml`. Each runs independently and is gated by GitHub labels rather than an in-process state machine. |
| `test-agent` / `test` | `.github/workflows/ci.yml` (unit + integration test jobs) and the test-gate step inside `implement-ready-issues.yml` | `pull_request` to master/develop, `push` to master | No dedicated coverage / flakiness analysis agent yet — only `pytest` + `ruff`. |
| `qc-agent` / `qc` | **Not yet implemented as a pipeline.** Some QC checks (lint, type, tests) are folded into `ci.yml` and the implement workflow's test gate. | — | A dedicated pre-merge QC gate (doc completeness, deploy-readiness, type checks beyond ruff) is a candidate addition. |
| `deploy-agent` | **Not yet implemented.** | — | Candidate: a `push: [master]` workflow that builds, tags, and deploys to staging. |
| `create-pipeline-roadmap` | **Not implemented.** | — | The `SKILL.md` describes a planning-time helper, not a runtime pipeline. |
| `create-pipeline-task` | **Not implemented.** | — | Same as above. |

## Issue-driven workflow (end to end)

The pipeline today is structured around GitHub Issues + labels, not in-memory orchestration:

```
       new issue
          │
          ▼
┌──────────────────────────┐
│ monitor-issues.yml       │  cron */10 (offset)
│ scripts/ci/validate_     │  → adds  ready  or  needs-clarification
│   open_issues.py         │
└─────────┬────────────────┘
          │ (label: ready)
          ▼
┌──────────────────────────┐
│ implement-ready-issues   │  cron */30 (next: offset)
│   .yml                   │
│ Stage 1: claim_and_plan_ │  → adds  wip , writes  .plans/issue-N.md
│   issue.py               │
│ docker compose up test-db│
│ Stage 2: execute_        │  → modifies code, runs tests
│   implementation.py      │
│ Test gate: ruff +        │  → final pass/fail
│   pytest unit+integ      │
│ Commit + push + PR       │  → PR with  Closes #N
└─────────┬────────────────┘
          │ (PR opened by PAT — fires downstream workflows)
          ▼
┌──────────────────────────┐
│ ci.yml                   │  pull_request
│ pipeline-code-review.yml │  pull_request → resolves PR comments on fix
└─────────┬────────────────┘
          │ (PR merged)
          ▼
       Issue auto-closed via "Closes #N"
```

## Cross-cutting workflows

| Workflow | Purpose | Trigger |
|---|---|---|
| `.github/workflows/auto-pr.yml` | Creates a PR from any non-master branch on push, idempotent (skips if PR exists). Uses PAT so the PR triggers downstream workflows. | `push` (branches: ignore master) |
| `.github/workflows/pipeline-doc-sync.yml` | Daily check: are README / CLAUDE.md / docs/ stale vs. code? Drift opens or updates a single `doc-sync`-labelled issue; resolved drift auto-closes it. | `schedule: 03:17 UTC daily` |
| `.github/workflows/monitor-issues.yml` | Validates newly-opened issues with Claude; labels valid ones `ready`, others `needs-clarification`. | `schedule: every 10 min (offset)` |

## Conventions

- **Labels are the state machine.** `ready` → eligible for implementation. `wip` → claimed by a run, do not re-pick. `needs-clarification` / `doc-sync` / `code-review-critical` → triage outputs. Manual relabelling re-enters the corresponding stage.
- **Markers identify bot artifacts.** Every comment / issue body produced by a workflow starts with an HTML-comment marker (e.g. `<!-- agent-job-issue-validator -->`) so dedup, upsert, and resolve operations can find their own output without matching on visible text.
- **One persistent tracking issue per concern** (doc drift, code-review critical — when re-enabled). Workflows update or close that issue rather than spawning a new one per run.
- **Long-running workflows use a `concurrency:` group** so a slow run doesn't race with the next cron tick.
- **PAT for cross-workflow chaining.** Workflows that create PRs use `COMMIT_GITHUB_TOKEN` (a PAT), since events triggered by `GITHUB_TOKEN` do **not** fire downstream `pull_request` workflows.

## When you'd touch what

- **Change how a role behaves** → edit the corresponding script in `scripts/ci/` and/or the YAML in `.github/workflows/`. The per-role SOUL.md files don't drive runtime behaviour.
- **Add a new role** → create a new workflow (and supporting script) here, then add a row to the mapping table above. A SOUL.md is optional and is for human reference only.
- **Retire a role** → remove its workflow. Leaving an orphaned SOUL.md is OK as long as this index makes its status clear.
