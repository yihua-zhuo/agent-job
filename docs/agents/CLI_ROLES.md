# Agent CLI Roles

This document maps the command-line entrypoints to their roles in the active
GitHub-Issue driven agent flow. Files under `scripts/cron/`, `coordinator.py`,
`scripts/coordinator.py`, and `scripts/coordinate.py` are legacy OpenClaw /
shared-memory paths unless a workflow explicitly invokes them.

## Active Implementation Flow

| CLI | Owner Role | Invoked By | Responsibility | Prompt Contract |
|---|---|---|---|---|
| `scripts/ci/validate_open_issues.py` | Issue monitor / triage | `.github/workflows/monitor-issues.yml` | Reads open GitHub issues, handles dependency labels, asks Claude to classify issues as `ready`, `needs-clarification`, or `too_large`, and creates ordered subtasks for oversized work. | Emits and parses strict JSON. For `Dev-Plan: ...` issues, verifies the board can be resolved and tells Claude the board document defines scope. |
| `scripts/ci/claim_and_plan_issue.py` | Planner | `.github/workflows/implement-ready-issues.yml` Stage 1 | Selects one `ready` issue, adds `wip`, asks Claude for `.plans/issue-<N>.md`, and releases the claim if planning fails. | Requires a Markdown plan with `Goal`, `Source Contract`, `Affected Files`, `Implementation Steps`, `Test Plan`, and `Acceptance Criteria`. Dev-plan issues include concrete README/template/board paths. |
| `scripts/ci/execute_implementation.py` | Implementer | `.github/workflows/implement-ready-issues.yml` Stage 2 | Runs Claude Code against the saved plan, edits the working tree, and requires ruff, unit tests, and integration tests before completion. | Treats the plan as scope. If a Source Contract/dev-plan board exists, it must read the referenced docs, execute board steps in order, run board verification, and avoid unrelated cross-board edits. |
| `scripts/ci/self_review_implementation.py` | Self-review / QC | `.github/workflows/implement-ready-issues.yml` Stage 3 | Reviews the implementation diff against the plan and `codereview.md`, fixes gaps, and reruns verification when it changes code. | Checks plan coverage first, then review rules. Dev-plan issues additionally require board scope compliance and evidence that step verification ran. |
| `scripts/dev/trigger_implement.py` | Local dispatcher | Developer terminal | Lists claimable `ready` issues and dispatches `implement-ready-issues.yml` for a selected issue. | No LLM prompt. Validates repo/token context and lets the workflow do server-side eligibility checks. |

## Active PR Review / Fix Flow

| CLI | Owner Role | Invoked By | Responsibility |
|---|---|---|---|
| `scripts/ci/run_claude_code_review.py` | PR code reviewer | `.github/workflows/pipeline-code-review.yml` | Reviews changed PR files with Claude and writes a normalized JSON review artifact. |
| `scripts/ci/post_pr_line_comments.py` | Review publisher | `.github/workflows/pipeline-code-review.yml` | Converts review findings into PR inline comments and summary output, reusing existing bot threads where possible. |
| `scripts/ci/fetch_pr_test_failures.py` | Failure collector | `.github/workflows/fix-pr-comments.yml` | Pulls failing PR check logs into bounded Markdown for Claude's fix prompt. |
| `scripts/ci/fix_pr_comments.py` | PR fixer | `.github/workflows/fix-pr-comments.yml` | Applies fixes requested by PR comments and test-failure context without committing directly. |
| `scripts/ci/resolve_merge_conflicts.py` | Conflict resolver | `.github/workflows/fix-pr-comments.yml` | Lets Claude resolve branch merge conflicts, then verifies no conflict markers remain. |
| `scripts/ci/trigger_fix_for_issue.py` / `dispatch_pr_fixes.py` | Fix dispatcher | Manual / scheduled workflows | Dispatches PR-fix workflows while avoiding duplicate active runs. |

## Support Utilities

| CLI | Role | Notes |
|---|---|---|
| `scripts/ci/dev_plan_context.py` | Dev-plan resolver | Shared helper, not a standalone command. Resolves `Dev-Plan: docs/dev-plan/...`, including `DEV_PLAN_ROOT` and the sibling `../super-chain-testnet/docs/dev-plan` fallback for local work. |
| `scripts/ci/clear_triage_labels.py` | Triage maintenance | Manual cleanup for `ready`, `needs-clarification`, and related labels. |
| `scripts/ci/cleanup_orphan_subtasks.py` | Issue hygiene | Closes or cleans up generated subtasks whose parent state no longer needs them. |
| `scripts/ci/create_doc_sync_issue.py` / `run_claude_doc_sync_check.py` | Documentation drift monitor | Daily doc-sync pipeline. Separate from dev-plan board implementation. |
| `scripts/ci/create_cr_issue.py` / `create_deploy_issue.py` | Tracking issue creators | Convert pipeline findings into persistent GitHub issues. |

## Prompt Compatibility Checks

The active prompt chain is intentionally staged:

1. Triage prompt outputs JSON only.
2. Planning prompt outputs Markdown only and embeds the Source Contract.
3. Implementation prompt consumes that Markdown and enforces test and dev-plan gates.
4. Self-review prompt re-reads the plan and verifies both coverage and review rules.
5. PR-fix prompts operate on PR comments/test failures and do not change issue plans.

When changing any prompt, keep these boundaries intact. A prompt that changes
its output shape must be paired with parser changes in the same script.
