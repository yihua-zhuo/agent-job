# Implementation Plan — Issue #434

## Goal
Replace the existing `.github/workflows/ci.yml` with a streamlined CI workflow that runs unit/lint tests in a `test` job, uploads artifacts, and chains a `code-review` job that calls an external code-review agent via an authenticated gateway, triggered on push to `master`/`develop`.

## Affected Files
- `.github/workflows/ci.yml` — Replace the existing multi-job workflow with a two-job workflow (`test`, `code-review`) as specified in the issue

## Implementation Steps
1. Read the existing `.github/workflows/ci.yml` in full to understand all current jobs before replacing it (already done above).
2. Replace `.github/workflows/ci.yml` content with a new workflow containing:
   - `name: CI`
   - `on: push: branches: [master, develop]` (no pull_request trigger needed per the issue)
   - `env: PYTHON_VERSION: '3.11'`
   - A `test` job on `ubuntu-latest` that:
     - Checks out code
     - Sets up Python `${{ env.PYTHON_VERSION }}`
     - Installs deps (`pip install -q ".[dev]"`)
     - Runs `pytest tests/ -m "not integration" -v`
     - Runs `ruff check src/`
     - Uploads pytest artifacts via `actions/upload-artifact@v4`
   - A `code-review` job on `ubuntu-latest` with `needs: [test]` that:
     - Checks out code with `fetch-depth: 0`
     - Calls the code-review agent via authenticated gateway using:
       - URL: `${{ vars.CLAUDE_GATEWAY_URL }}`
       - Token: `${{ secrets.CLAUDE_GATEWAY_TOKEN }}`
       - Method/headers passed as `Authorization: Bearer <token>` or similar bearer auth
     - Uses `actions/setup-python@v5` with `python-version: ${{ env.PYTHON_VERSION }}` before the agent call
     - Runs `python3 scripts/ci/run_code_review.py` (or the appropriate entry point for the agent), passing gateway URL and token as env vars

## Test Plan
- Unit tests in `tests/unit/`: No new unit tests required — the workflow itself is a configuration file; the `pytest tests/ -m "not integration" -v` command is exercised by the CI run.
- Integration tests in `tests/integration/`: No new integration tests required.

## Acceptance Criteria
- The new `ci.yml` defines exactly two jobs: `test` and `code-review`.
- The `code-review` job uses `needs: [test]` so it only runs after `test` succeeds.
- The `test` job runs `pytest tests/ -m "not integration" -v` and `ruff check src/` and uploads pytest artifacts.
- The `code-review` job references `${{ vars.CLAUDE_GATEWAY_URL }}` and `${{ secrets.CLAUDE_GATEWAY_TOKEN }}` as placeholder env vars.
- The workflow triggers on push to `master` and `develop`.
- Ruff linting passes on the new file (`ruff check .github/workflows/ci.yml`).

## Risks / Open Questions
- The existing `ci.yml` has jobs (`coordinator`, `unit-test`, `integration-test`, `quality-check`, `build`, `deploy`) that are not mentioned in issue #434. Replacing the file with a two-job workflow removes those jobs entirely. Confirm whether those jobs are being superseded or should be preserved in a separate workflow file.
- The entry point for the code-review agent (`scripts/ci/run_code_review.py` or similar) should be verified to exist; if it does not yet exist, the `code-review` job step is a stub that will need that script created first.
