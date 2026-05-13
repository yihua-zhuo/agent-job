#!/usr/bin/env python3
"""Trigger fix-pr-comments.yml for a single issue's PR.

Usage:
    python3 scripts/ci/trigger_fix_for_issue.py <issue_id> [--force]

Steps it runs (in order):
    1. Look up the open PR linked to <issue_id> via gh CLI:
       - First by head-branch convention `auto/issue-<N>`.
       - Falls back to `gh pr list --search "in:body Closes #<N>"`.
    2. Check `gh run list --workflow fix-pr-comments.yml --branch <head>`
       across `queued`, `in_progress`, `waiting`, and `pending` statuses.
       If one is already active for that branch, SKIP (override with --force).
    3. Dispatch `gh workflow run fix-pr-comments.yml -f pr_number=<PR>`.

Re-uses dispatch_pr_fixes.find_active_fix_runs and dispatch_fix so the
"is a fix already running?" and "how do we trigger it?" logic stays in
one place.
"""

import argparse
import json
import os
import subprocess
import sys

# Reuse helpers from sibling scripts so behaviour stays consistent.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatch_pr_fixes import (  # noqa: E402
    WORKFLOW_FILE,
    dispatch_fix,
    find_active_fix_runs,
)
from fix_pr_comments import infer_repo  # noqa: E402


def log(msg: str) -> None:
    print(f"[trigger-fix] {msg}", flush=True)


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def find_pr_for_issue(issue_id: int) -> dict | None:
    """Return the open PR linked to ``issue_id``, or None.

    Tries the project's `auto/issue-<N>` branch convention first (covers PRs
    created by the auto-implement pipeline), then falls back to a body-text
    search for `Closes #<N>`. Returns the first match in each case.
    """
    # 1. Branch-name convention
    result = run_gh([
        "pr", "list",
        "--state", "open",
        "--head", f"auto/issue-{issue_id}",
        "--json", "number,headRefName,title,url",
        "--limit", "5",
    ])
    if result.returncode == 0:
        try:
            prs = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            prs = []
        if prs:
            return prs[0]

    # 2. Body-text fallback
    result = run_gh([
        "pr", "list",
        "--state", "open",
        "--search", f"Closes #{issue_id} in:body",
        "--json", "number,headRefName,title,url",
        "--limit", "5",
    ])
    if result.returncode == 0:
        try:
            prs = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            prs = []
        if prs:
            return prs[0]

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch fix-pr-comments.yml for the PR linked to a given issue.",
    )
    parser.add_argument("issue_id", type=int, help="GitHub issue number, e.g. 72")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Dispatch even if a fix run is already active for the PR's branch.",
    )
    args = parser.parse_args()

    repo = infer_repo()
    if not repo:
        log("could not determine repository (set GITHUB_REPOSITORY or run inside a checkout)")
        return 1

    log(f"repo={repo} issue=#{args.issue_id}")

    pr = find_pr_for_issue(args.issue_id)
    if not pr:
        log(f"no open PR found for issue #{args.issue_id}")
        log("Tried branch 'auto/issue-<N>' and body search 'Closes #<N>'.")
        log("If the PR exists under a different convention, dispatch manually:")
        log(f"    gh workflow run {WORKFLOW_FILE} -f pr_number=<PR>")
        return 1

    pr_number = int(pr["number"])
    head_ref = pr.get("headRefName") or ""
    title = pr.get("title") or ""
    url = pr.get("url") or ""
    log(f"matched PR #{pr_number} on branch {head_ref!r}")
    log(f"  title: {title}")
    log(f"  url:   {url}")

    if not args.force:
        active = find_active_fix_runs(head_ref)
        if active:
            ids = ", ".join(str(r.get("databaseId")) for r in active)
            log(f"SKIP: a fix run is already active for {head_ref} (run ids: {ids})")
            log("Pass --force to dispatch anyway.")
            return 0

    if dispatch_fix(pr_number):
        log(f"DISPATCHED fix-pr-comments.yml for PR #{pr_number}")
        log("Track with:")
        log(f"    gh run list --workflow {WORKFLOW_FILE} --limit 3")
        log("    gh run watch")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
