# Implementation Plan — Issue #148

## Goal
Consolidate and extend the existing GitHub Actions CI pipeline in `.github/workflows/ci.yml` to fully implement the four-stage pipeline (Test → Code Review → QC → Deploy) described in issue #148, replacing the placeholder `openclaw run --role` commands with the actual scripts and steps already present in the repository.

## Affected Files
- `.github/workflows/ci.yml` — Replace placeholder `openclaw run --role` jobs with real script calls; add job chaining; align trigger conditions with issue spec
- `pyproject.toml` — Add `pytest-xdist` and `pylint` to the existing `[project.optional-dependencies].dev` group
- `pytest.ini` — Already present and correct; no changes needed

## Implementation Steps

1. **Update `.github/workflows/ci.yml`**
   - Remove the `coordinator` job (not part of the issue #148 spec)
   - Align the `on:` trigger to match the issue: push to `master`, `develop`, and `feature/**`; pull_request to `master` and `develop`
   - Replace the `code-review` job's `if: false` stub and placeholder `openclaw` step with a direct call to `scripts/ci/run_claude_code_review.py` (mirroring the pattern in `.github/workflows/pipeline-code-review.yml`)
   - Replace the `quality-check` job's `openclaw run --role qc` with a call to `docs/agents/qc/qc_agent.py` or the equivalent script path
   - Replace the `deploy` job's `openclaw run --role deploy` stub with `python3 scripts/deploy.py`
   - Ensure `deploy` retains `if: github.ref == 'refs/heads/master'` and add `needs: quality-check` to enforce proper job chaining
   - Remove or disable the existing `integration-test` job (not in the issue #148 spec); re-add separately if needed

2. **Add missing dev dependencies to `pyproject.toml`**
   - Add `"pytest-xdist>=3.0"` and `"pylint>=3.0"` to the existing `dev` list under `[project.optional-dependencies]`
   - Keep existing entries (`pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `httpx`, `openpyxl`) intact

3. **Verify `pytest.ini` is correctly configured**
   - Confirm `pythonpath = src`, `asyncio_mode = auto`, and `addopts = -v --tb=short --strict-markers` are present (already correct; no action needed)

## Test Plan
- Unit tests in `tests/unit/`: No new test files required — the existing `pytest tests/unit/ -v` step in `ci.yml` already runs the full unit suite. After dependency updates, verify `pytest tests/unit/ --collect-only` produces zero collection errors.
- Integration tests in `tests/integration/`: No new test files required for this issue. Integration test job may be kept in `ci.yml` as a separate optional job if needed, but it is not part of the issue #148 spec.

## Acceptance Criteria
- All four jobs (`test`, `code-review`, `qc`, `deploy`) appear in the CI workflow with proper `needs:` ordering
- Push to `develop` triggers the workflow; push to `master` additionally triggers the `deploy` job
- `pytest tests/unit/ --collect-only` exits with code 0 and zero collection errors
- `ruff check src/` and `mypy src/ --ignore-missing-imports` each exit with code 0 (QC gate)
- `python3 scripts/deploy.py` executes without error when called in the `deploy` job
- The `code-review` job calls `scripts/ci/run_claude_code_review.py` (or the equivalent real script path) instead of the placeholder `openclaw` CLI
