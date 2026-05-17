The deploy scripts are already fixed (no hardcoded token found), and `shared-memory/` doesn't exist in the repo yet. Only `.gitignore` needs updating.

# Implementation Plan — Issue #147

## Goal
Remove hardcoded Railway API tokens from `deploy.js` and `railway-deploy.js`, add safety checks requiring the `RAILWAY_TOKEN` environment variable, and prevent future accidental commits of shared-memory artifacts via `.gitignore`.

## Affected Files
- `deploy.js` — Already uses `process.env.RAILWAY_TOKEN` with a guard; no further code changes needed.
- `railway-deploy.js` — Already uses `process.env.RAILWAY_TOKEN` with a guard; no further code changes needed.
- `.gitignore` — Add three entries for shared-memory artifact directories.

## Implementation Steps
1. **Add `.gitignore` entries** — Append the following three lines to `.gitignore`:
   ```
   shared-memory/logs/
   shared-memory/results/
   shared-memory/reports/
   ```
2. **No changes to `deploy.js` or `railway-deploy.js`** — Both files already read `RAILWAY_TOKEN` from the environment with an early-exit guard; the hardcoded token is not present in the current codebase.

## Test Plan
- **No new unit or integration tests required** — The changes are configuration-only (`.gitignore` additions). No Python or JavaScript logic was modified.
- **Manual verification** — After the changes, run:
  - `grep -r "2dc2f4ae-4e33-4ec4-a715-474a16792c00" deploy.js railway-deploy.js` — must return no matches (confirm token is absent).
  - `echo "shared-memory/logs/" >> .gitignore && cat .gitignore | grep shared-memory` — confirm entries are present.

## Acceptance Criteria
- `deploy.js` and `railway-deploy.js` contain no hardcoded Railway tokens.
- `.gitignore` contains `shared-memory/logs/`, `shared-memory/results/`, and `shared-memory/reports/`.
- No secret tokens appear in `git diff` after the changes are applied.
