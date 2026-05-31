# Agent Job

Agent Job is a GitHub-Issue driven automation pipeline for implementation,
review, and verification. The runtime source of truth is the workflow set in
`.github/workflows/` plus the supporting scripts in `scripts/ci/`.

## Current Flow

```
GitHub issue
  -> monitor-issues.yml labels ready / needs-clarification / split / blocked
  -> implement-ready-issues.yml claims one ready issue with wip
  -> claim_and_plan_issue.py writes .plans/issue-<N>.md
  -> execute_implementation.py edits code and runs verification
  -> self_review_implementation.py checks plan coverage and review rules
  -> workflow commits changes and opens a PR
  -> ci.yml and pipeline-code-review.yml verify the PR
```

Labels are the state machine:

- `ready`: eligible for implementation.
- `wip`: claimed by an implementation run.
- `needs-clarification`: missing enough detail to start.
- `blocked`: waiting on declared issue dependencies.
- `split`: parent issue was decomposed into smaller issues.

## Dev-Plan Boards

Issues can bind the agent flow to a `docs/dev-plan` board by including a line:

```text
Dev-Plan: docs/dev-plan/20-defi/21-bridge-relayer-nm.md
```

For these issues, the CI agents follow the Super AI Chain dev-plan contract:

1. Read `docs/dev-plan/README.md`.
2. Read the matching `_template-medium.md` or `_template-deep.md`.
3. Read the target board document.
4. Implement the board's steps in order.
5. Run the board's machine-checkable verification commands after each relevant step.
6. Avoid cross-board edits unless the board or plan explicitly permits them.

If the dev-plan directory lives somewhere other than the workflow checkout, set
`DEV_PLAN_ROOT` to the absolute path of `docs/dev-plan`.

## Local Dispatch

List and trigger ready issues with:

```bash
python scripts/dev/trigger_implement.py --list
python scripts/dev/trigger_implement.py --issue 123 --yes
```

Required environment:

- `GH_TOKEN` or `GITHUB_TOKEN` with repo/actions access.
- `ANTHROPIC_API_KEY` for CI runs that invoke Claude Code.

## Agent Docs

See `docs/agents/README.md` for the role-to-workflow mapping. Older
`shared-memory/` and OpenClaw coordinator files remain as historical references
unless a workflow explicitly invokes them.
