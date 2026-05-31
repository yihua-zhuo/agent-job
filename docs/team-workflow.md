# Agent-Job Team Workflow

This repo now uses GitHub Issues, labels, PRs, and CI workflows as the active
agent coordination layer. The old `shared-memory/tasks` manager flow is
historical and should not be used for new automation unless it is explicitly
reintroduced in a workflow.

## Runtime Pipeline

1. `monitor-issues.yml` runs `scripts/ci/validate_open_issues.py`.
2. Valid issues are labelled `ready`; blocked issues wait for dependencies;
   large issues are split into ordered subtasks.
3. `implement-ready-issues.yml` runs `scripts/ci/claim_and_plan_issue.py`.
4. The plan is saved to `.plans/issue-<N>.md` and committed to an
   implementation branch.
5. `scripts/ci/execute_implementation.py` executes the plan, edits files, and
   runs the required verification commands.
6. `scripts/ci/self_review_implementation.py` checks plan coverage and
   `codereview.md` before the workflow opens a PR.
7. PR-time CI and code review re-verify before merge.

## Dev-Plan Issue Contract

For Super AI Chain board work, the issue must include:

```text
Dev-Plan: docs/dev-plan/<domain>/<board>.md
```

The agent flow then follows the dev-plan rules:

- Read `docs/dev-plan/README.md`, then the matching template, then the board.
- Treat README §2 as mandatory constraints.
- Implement the board's §5 steps in order.
- Run §6 machine-checkable verification commands after each relevant step.
- Keep edits within the board's declared files unless the implementation plan
  explicitly allows a wider change.
- Report a blocker instead of guessing when a design decision is not covered.

Set `DEV_PLAN_ROOT` when the dev-plan directory is not checked out at
`docs/dev-plan` in the current repository.

## Quality Gates

The default implementation prompt requires these clean commands before the
agent can declare completion:

```bash
PYTHONPATH=src ruff check src/
PYTHONPATH=src pytest tests/unit/ -v
DATABASE_URL=postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db PYTHONPATH=src pytest tests/integration/ -v
```

Dev-plan board verification commands are additive. If a board defines
`bash verify/X.sh`, `forge test`, `curl`, or another machine-checkable gate,
the implementing agent must run it when the corresponding step is completed.

## Manual Control

Use the local dispatcher for ad hoc runs:

```bash
python scripts/dev/trigger_implement.py --list
python scripts/dev/trigger_implement.py --issue 123 --yes
```

Remove `wip` from an issue to allow a failed implementation to be retried.
