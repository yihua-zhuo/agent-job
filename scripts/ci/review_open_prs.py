#!/usr/bin/env python3
"""Review open PRs and decide: merge, send to fix-pr-comments, or wait.

For each open non-draft PR:

  1. Skip if a fix-pr-comments.yml run is already queued or in-progress
     against the PR's head branch (don't pile fix runs on top of each other).
  2. If GitHub still says mergeable=UNKNOWN, skip — let GH finish computing.
  3. If any required CI check is failing, OR the branch is conflicted with
     base → dispatch fix-pr-comments (it has the conflict resolver + the
     CI-failure-fixing prompt).
  4. If any UNRESOLVED review thread contains a 🔴 "Critical" finding from
     `claude_code_review.py` → dispatch fix-pr-comments.
  5. Otherwise ask Claude whether the diff actually fulfils the linked issue
     (parsed from "Closes #N" in the PR body). If incomplete → leave a
     comment and skip; if complete → enable auto-merge via
     `gh pr merge --squash --auto --delete-branch`.

Comments left by this agent are tagged with `<!-- agent-job-pr-reviewer -->`
so repeat ticks don't spam.
"""

import json
import os
import re
import subprocess
import sys
from json import JSONDecoder
from typing import Any

# Reuse the comment-fetching / actionable-feedback logic so "what counts as
# unresolved" stays in one place.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dispatch_pr_fixes import (  # noqa: E402
    find_active_fix_runs,
    dispatch_fix,
)
from fix_pr_comments import (  # noqa: E402
    fetch_review_threads,
    infer_repo,
)


REVIEWER_MARKER = "<!-- agent-job-pr-reviewer -->"
# Critical findings from claude_code_review.py render as either the emoji
# (inline comments) or the literal "**Critical**" string (summary table). We
# match either so we don't depend on whether the review path is inline or
# summary-only.
CRITICAL_MARKERS = ("🔴", "**Critical**")
# Same-repo "Closes #N" / "Fixes #N" / "Resolves #N" references in the PR body
# tell us which issue this PR was meant to satisfy. Cross-repo is ignored —
# we can't read foreign-repo issue bodies with the repo's GITHUB_TOKEN.
LINKED_ISSUE_PATTERN = re.compile(r"(?i)\b(?:closes|fixes|resolves)\s+#(\d+)\b")
# Failing required checks block merge regardless of human review state. Mirror
# the set the GH "Merge" button uses — anything that resolves to a non-success
# conclusion on a required check.
FAILING_CONCLUSIONS = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STALE"}


def log(msg: str) -> None:
    print(f"[review-prs] {msg}", flush=True)


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def list_open_prs() -> list[dict]:
    result = run_gh([
        "pr", "list",
        "--state", "open",
        "--json", "number,title,body,headRefName,baseRefName,isDraft,author",
        "--limit", "200",
    ])
    if result.returncode != 0:
        log(f"list_prs_failed rc={result.returncode} stderr={result.stderr.strip()}")
        return []
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []


def fetch_pr_state(number: int) -> dict[str, Any] | None:
    """Pull mergeability + check rollup for a single PR.

    Done in a second call because `--json mergeable` triggers GH to compute the
    mergeability state, which is async — the bulk list above may return stale
    values. A targeted view is cheap and current.
    """
    result = run_gh([
        "pr", "view", str(number),
        "--json", "mergeable,mergeStateStatus,statusCheckRollup,reviewDecision,isDraft",
    ])
    if result.returncode != 0:
        log(f"pr_view_failed pr=#{number} rc={result.returncode} stderr={result.stderr.strip()[:200]}")
        return None
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None


def has_failing_checks(state: dict[str, Any]) -> bool:
    """Treat any non-success required check as failing."""
    rollup = state.get("statusCheckRollup") or []
    for check in rollup:
        # statusCheckRollup mixes two shapes:
        #   - CheckRun: {status, conclusion, name, ...}
        #   - StatusContext: {state, context, ...}
        conclusion = (check.get("conclusion") or "").upper()
        legacy_state = (check.get("state") or "").upper()
        if conclusion in FAILING_CONCLUSIONS:
            return True
        if legacy_state in {"FAILURE", "ERROR"}:
            return True
    return False


def unresolved_critical_threads(threads: list[dict]) -> list[dict]:
    """Subset of unresolved threads that contain at least one critical comment."""
    out: list[dict] = []
    for t in threads:
        comments = (t.get("comments") or {}).get("nodes") or []
        for c in comments:
            body = c.get("body") or ""
            if any(marker in body for marker in CRITICAL_MARKERS):
                out.append(t)
                break
    return out


def parse_linked_issue(body: str | None) -> int | None:
    if not body:
        return None
    m = LINKED_ISSUE_PATTERN.search(body)
    return int(m.group(1)) if m else None


def fetch_issue(number: int) -> dict[str, Any] | None:
    r = run_gh(["issue", "view", str(number), "--json", "number,title,body,state"])
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None


def fetch_pr_summary(number: int) -> dict[str, Any] | None:
    """Title, body, file list, and commit subjects — enough for completeness review.

    We deliberately don't fetch the full diff. Most PRs in this repo are
    auto-implemented and the diff is huge; commits + filenames are enough
    signal for Claude to judge "does this look like it covers the spec?".
    """
    r = run_gh([
        "pr", "view", str(number),
        "--json", "title,body,files,commits",
    ])
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None


def already_commented(repo: str, number: int) -> bool:
    """True if we've ever posted our reviewer marker on this PR."""
    r = run_gh(["api", f"/repos/{repo}/issues/{number}/comments?per_page=100"])
    if r.returncode != 0:
        return False
    try:
        comments = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return False
    return any(REVIEWER_MARKER in (c.get("body") or "") for c in comments)


def post_pr_comment(number: int, body: str) -> bool:
    full = f"{REVIEWER_MARKER}\n{body}"
    r = run_gh(["pr", "comment", str(number), "--body", full])
    if r.returncode != 0:
        log(f"comment_failed pr=#{number} stderr={r.stderr.strip()[:200]}")
        return False
    return True


def enable_auto_merge(number: int) -> bool:
    """Use --auto so GH only merges once required checks pass.

    Squash because the implement workflow produces a "plan" commit + an
    implementation commit; one squash keeps master's history clean.
    --delete-branch keeps the auto-implement branches from piling up.
    """
    r = run_gh([
        "pr", "merge", str(number),
        "--squash", "--auto", "--delete-branch",
    ])
    if r.returncode != 0:
        log(f"merge_failed pr=#{number} stderr={r.stderr.strip()[:300]}")
        return False
    return True


def build_prompt(issue_title: str, issue_body: str, pr_title: str, pr_body: str,
                 commit_subjects: list[str], file_paths: list[str]) -> str:
    files_block = "\n".join(f"- {p}" for p in file_paths[:200]) or "(no files)"
    commits_block = "\n".join(f"- {s}" for s in commit_subjects[:50]) or "(no commits)"
    return f"""You are reviewing whether a PR fulfils its linked issue.

----- LINKED ISSUE -----
Title: {issue_title}

{issue_body or "(no body)"}
----- END LINKED ISSUE -----

----- PR -----
Title: {pr_title}

{pr_body or "(no body)"}
----- END PR -----

Commits on the PR branch:
{commits_block}

Files changed in the PR:
{files_block}

Decide ONE verdict:

- "complete" — the PR appears to implement everything the issue requested.
  All listed acceptance criteria / required files appear to be touched, and
  the commit messages reference the implementation work (not just plans).

- "incomplete" — the PR is missing something the issue clearly asked for.
  Examples: issue lists 3 endpoints, PR only adds 1; issue asks for tests,
  no test files were touched; issue requires a migration, no alembic file
  appears.

Be generous about "complete": you are NOT reviewing code quality here (that
is what the inline reviewer does). You are only checking that the SCOPE of
the issue is covered. Missing edge-case handling or stylistic issues are
NOT grounds for "incomplete".

Respond with JSON only, no prose, no markdown fence:
{{
  "verdict": "complete" | "incomplete",
  "reason": "<one short sentence>",
  "missing": ["<only when incomplete — specific gaps>"]
}}
"""


def extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        inner = data.get("result")
        if isinstance(inner, str):
            nested = extract_json(inner)
            if nested is not None:
                return nested
        return data
    decoder = JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def call_claude(prompt: str) -> tuple[dict[str, Any] | None, str]:
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "240"))
    max_attempts = max(1, int(os.environ.get("CLAUDE_MAX_ATTEMPTS", "2")))
    cmd = [
        "claude", "-p",
        "--model", model,
        "--max-turns", "8",
        "--output-format", "json",
    ]
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                check=False, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return None, "claude_timed_out"
        except OSError as e:
            return None, f"claude_not_runnable: {e}"

        if result.returncode != 0:
            last_err = f"claude_rc={result.returncode} stderr={(result.stderr or '').strip()[-200:]!r}"
        else:
            parsed = extract_json(result.stdout or "")
            if isinstance(parsed, dict) and "verdict" in parsed:
                return parsed, ""
            last_err = f"parse_failed stdout_head={(result.stdout or '').strip()[:300]!r}"
        if attempt < max_attempts:
            log(f"claude_retry attempt={attempt}/{max_attempts} err={last_err}")
    return None, last_err


def process_pr(repo: str, pr: dict[str, Any]) -> str:
    """Returns one of: MERGED, DISPATCHED, COMMENTED, SKIPPED, ERROR."""
    number = int(pr["number"])
    title = (pr.get("title") or "")[:60]
    head = pr.get("headRefName") or "?"
    log(f"reviewing pr=#{number} branch={head} title={title!r}")

    if pr.get("isDraft"):
        log(f"skip pr=#{number} reason=draft")
        return "SKIPPED"

    # Don't pile fix dispatches on top of an in-flight one.
    if find_active_fix_runs(head):
        log(f"skip pr=#{number} reason=fix_already_running")
        return "SKIPPED"

    state = fetch_pr_state(number)
    if state is None:
        return "ERROR"

    mergeable = (state.get("mergeable") or "").upper()
    merge_state = (state.get("mergeStateStatus") or "").upper()

    # Conflict detection requires a known mergeable state. When UNKNOWN, skip
    # this branch and fall through — we can still dispatch fixes based on CI
    # failures and critical reviewer findings, which don't depend on the merge
    # computation. The merge step at the bottom re-checks mergeable.
    # All dispatch_fix calls pass head_ref so the resulting run is associated
    # with the PR's branch in the Actions UI (not master).
    if mergeable == "CONFLICTING" or merge_state == "DIRTY":
        if dispatch_fix(number, head_ref=head):
            log(f"dispatched pr=#{number} reason=merge_conflict")
            return "DISPATCHED"
        return "ERROR"

    # Failing required checks — fix-pr-comments has the CI-fix prompt.
    # Independent of mergeability; runs even when mergeable=UNKNOWN.
    if has_failing_checks(state):
        if dispatch_fix(number, head_ref=head):
            log(f"dispatched pr=#{number} reason=failing_checks")
            return "DISPATCHED"
        return "ERROR"

    # Unresolved critical reviewer findings — fix-pr-comments addresses them.
    # Independent of mergeability; runs even when mergeable=UNKNOWN.
    threads = fetch_review_threads(repo, number)
    critical = unresolved_critical_threads(threads)
    if critical:
        log(f"dispatched_reason pr=#{number} critical_threads={len(critical)}")
        if dispatch_fix(number, head_ref=head):
            return "DISPATCHED"
        return "ERROR"

    # Beyond this point we'd enable auto-merge. We can't safely do that
    # while GH is still computing mergeability — defer to the next tick.
    if mergeable == "UNKNOWN":
        log(f"skip pr=#{number} reason=mergeable_unknown_after_fix_checks")
        return "SKIPPED"

    # Feature-completeness check vs linked issue (if any).
    issue_number = parse_linked_issue(pr.get("body"))
    summary = fetch_pr_summary(number) or {}
    if issue_number is None:
        log(f"no_linked_issue pr=#{number} — skipping completeness check, treating as complete")
        verdict, missing, reason = "complete", [], "No linked issue; scope check skipped."
    else:
        issue = fetch_issue(issue_number)
        if issue is None:
            log(f"linked_issue_unreadable pr=#{number} issue=#{issue_number} — treating as complete")
            verdict, missing, reason = "complete", [], f"Linked issue #{issue_number} not readable."
        else:
            prompt = build_prompt(
                issue_title=issue.get("title") or "",
                issue_body=(issue.get("body") or "").strip(),
                pr_title=(summary.get("title") or pr.get("title") or "").strip(),
                pr_body=(summary.get("body") or pr.get("body") or "").strip(),
                commit_subjects=[c.get("messageHeadline") or "" for c in summary.get("commits") or []],
                file_paths=[f.get("path") or "" for f in summary.get("files") or []],
            )
            parsed, err = call_claude(prompt)
            if err or not parsed:
                log(f"claude_failed pr=#{number} err={err}")
                return "ERROR"
            verdict = (parsed.get("verdict") or "").strip().lower()
            reason = (parsed.get("reason") or "").strip()
            missing = parsed.get("missing") or []
            if not isinstance(missing, list):
                missing = [str(missing)]

    if verdict == "incomplete":
        if already_commented(repo, number):
            log(f"skip pr=#{number} reason=incomplete_already_flagged")
            return "SKIPPED"
        lines = [f"**Feature scope appears incomplete vs #{issue_number}** ⚠️"]
        if reason:
            lines.extend(("", reason))
        if missing:
            lines.extend(("", "**Missing:**"))
            lines.extend(f"- {m}" for m in missing if isinstance(m, str) and m.strip())
        lines.extend((
            "",
            "_Posted by the PR-reviewer agent. Push more commits and the next tick will re-evaluate._",
        ))
        if post_pr_comment(number, "\n".join(lines)):
            log(f"commented pr=#{number} reason=incomplete")
            return "COMMENTED"
        return "ERROR"

    # All gates passed — enable auto-merge.
    if enable_auto_merge(number):
        log(f"merged pr=#{number} (auto-merge enabled; will land when checks pass)")
        return "MERGED"
    return "ERROR"


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

    max_per_run = int(os.environ.get("MAX_PRS_PER_RUN", "10"))

    rows: list[tuple[int, str, str]] = []  # (number, status, reason/title)
    for pr in prs[:max_per_run]:
        try:
            status = process_pr(repo, pr)
        except Exception as e:  # noqa: BLE001 — keep the loop alive
            log(f"unhandled pr=#{pr.get('number')} err={type(e).__name__}: {e}")
            status = "ERROR"
        rows.append((int(pr["number"]), status, (pr.get("title") or "")[:60]))

    print()
    print(f"{'PR':>5}  {'STATUS':<11}  TITLE")
    print("-" * 90)
    for number, status, title in rows:
        print(f"{number:>5}  {status:<11}  {title}")
    print()
    by_status: dict[str, int] = {}
    for _, s, _ in rows:
        by_status[s] = by_status.get(s, 0) + 1
    print("summary:", " ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
    # Don't fail the workflow just because some PRs hit transient errors — let
    # the next tick retry. Only fail if literally every PR errored.
    if rows and all(s == "ERROR" for _, s, _ in rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
