#!/usr/bin/env python3
"""Scan open PRs and dispatch the fix-pr-comments workflow where needed.

For each open PR in the repo:

  1. Skip if a fix-pr-comments.yml run is already queued or in-progress
     targeting that PR's head branch (don't stack fix runs).
  2. Skip if every review thread is resolved AND there are no actionable
     conversation comments (nothing to fix).
  3. Otherwise, dispatch the workflow via `gh workflow run`.

Designed for manual / interactive invocation:

    python3 scripts/ci/dispatch_pr_fixes.py

Reuses fetch_review_threads / fetch_issue_comments / build_actionable_feedback
from fix_pr_comments.py so the "what counts as actionable feedback" logic
stays in one place.
"""

import json
import os
import subprocess
import sys

# Reuse the comment-fetching + filtering logic from the sibling script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_pr_comments import (  # noqa: E402
    build_actionable_feedback,
    fetch_issue_comments,
    fetch_review_threads,
    infer_repo,
)


WORKFLOW_FILE = "fix-pr-comments.yml"
RUNNING_STATUSES = ("queued", "in_progress", "waiting", "pending")


def log(msg: str) -> None:
    print(f"[dispatch-pr-fixes] {msg}", flush=True)


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def list_open_prs() -> list[dict]:
    result = run_gh([
        "pr", "list",
        "--state", "open",
        "--json", "number,headRefName,baseRefName,title",
        "--limit", "200",
    ])
    if result.returncode != 0:
        log(f"list_prs_failed rc={result.returncode} stderr={result.stderr.strip()}")
        return []
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []


def find_active_fix_runs(head_branch: str) -> list[dict]:
    """Return any non-completed fix-workflow runs targeting this branch.

    `gh run list --status` only accepts ONE status; iterate the few that mean
    "still going" so we don't miss a queued run that hasn't started yet.
    """
    active: list[dict] = []
    for status in RUNNING_STATUSES:
        result = run_gh([
            "run", "list",
            "--workflow", WORKFLOW_FILE,
            "--branch", head_branch,
            "--status", status,
            "--json", "databaseId,status,createdAt,displayTitle",
            "--limit", "10",
        ])
        if result.returncode != 0:
            continue
        try:
            chunk = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            continue
        active.extend(chunk)
    return active


def count_actionable_feedback(repo: str, pr_number: int) -> int:
    threads = fetch_review_threads(repo, pr_number)
    issue_comments = fetch_issue_comments(repo, pr_number)
    return len(build_actionable_feedback(threads, issue_comments))


def dispatch_fix(pr_number: int) -> bool:
    result = run_gh([
        "workflow", "run", WORKFLOW_FILE,
        "-f", f"pr_number={pr_number}",
    ])
    if result.returncode != 0:
        log(f"dispatch_failed pr=#{pr_number} rc={result.returncode} stderr={result.stderr.strip()}")
        return False
    return True


def main() -> int:
    repo = infer_repo()
    if not repo:
        log("missing_GITHUB_REPOSITORY_and_remote_inference_failed")
        return 1

    log(f"repo={repo}")
    prs = list_open_prs()
    log(f"open_prs={len(prs)}")

    if not prs:
        return 0

    rows: list[tuple[int, str, str, str, str]] = []  # (pr, branch, title, status, reason)

    for pr in prs:
        number = int(pr["number"])
        head = pr.get("headRefName") or "?"
        title = (pr.get("title") or "").strip()[:60]

        # 1. Already-running guard: don't stack a second fix run.
        active = find_active_fix_runs(head)
        if active:
            ids = ",".join(str(r.get("databaseId")) for r in active)
            rows.append((number, head, title, "SKIP", f"fix run already active (run ids: {ids})"))
            continue

        # 2. Anything to fix?
        try:
            n_items = count_actionable_feedback(repo, number)
        except Exception as e:  # noqa: BLE001 — surface, don't crash the loop
            rows.append((number, head, title, "ERROR", f"feedback fetch: {type(e).__name__}: {e}"))
            continue

        if n_items == 0:
            rows.append((number, head, title, "SKIP", "no unresolved feedback"))
            continue

        # 3. Dispatch.
        if dispatch_fix(number):
            rows.append((number, head, title, "DISPATCHED", f"{n_items} actionable item(s)"))
        else:
            rows.append((number, head, title, "ERROR", "dispatch failed; see logs above"))

    # Summary table
    print()
    print(f"{'PR':>5}  {'BRANCH':<40}  {'STATUS':<11}  {'TITLE':<60}  REASON")
    print("-" * 160)
    for number, head, title, status, reason in rows:
        print(f"{number:>5}  {head[:40]:<40}  {status:<11}  {title:<60}  {reason}")

    dispatched = sum(1 for r in rows if r[3] == "DISPATCHED")
    skipped = sum(1 for r in rows if r[3] == "SKIP")
    errors = sum(1 for r in rows if r[3] == "ERROR")
    print()
    print(f"summary: dispatched={dispatched} skipped={skipped} errors={errors}")
    return 1 if errors and not dispatched else 0


if __name__ == "__main__":
    sys.exit(main())
