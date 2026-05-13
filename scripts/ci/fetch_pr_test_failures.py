#!/usr/bin/env python3
"""Dump the latest CI test failures on a PR's head branch to a temp file.

For each test workflow listed in TEST_WORKFLOWS (default: ``ci.yml``):

  1. Find the most recent COMPLETED run of that workflow on the PR's head
     branch via ``gh run list``.
  2. If its conclusion is ``failure``, fetch only the failed-step logs via
     ``gh run view --log-failed`` (no need to grep the whole log).
  3. Trim each workflow's log to a sensible size (head + tail), then concat
     them into a single Markdown file at PR_FAILURES_FILE.

The fix_pr_comments.py script reads that file (path via the same env var)
and adds the failures to Claude's prompt so they get fixed alongside the
reviewer comments.

Env vars:
    PR_NUMBER         required  PR number being fixed
    HEAD_REF          required  PR's head branch
    PR_FAILURES_FILE  optional  output path (default: /tmp/pr-<N>-failures.md)
    TEST_WORKFLOWS    optional  comma-separated workflow filenames (default: ci.yml)
    GH_REPO           optional  passed by the workflow when no git remote is set up
"""

import json
import os
import subprocess
import sys


# Per-workflow log cap. With head + tail elision this is the actual size of
# the chunk pasted into Claude's prompt — pytest failures usually live in
# the last few KB, but unhandled tracebacks can also surface near the top.
MAX_LOG_CHARS = 15_000
LOG_HEAD = 1_000  # keep the first N chars too, since errors can appear early


def log(msg: str) -> None:
    print(f"[fetch-failures] {msg}", flush=True)


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def latest_failed_run(workflow: str, branch: str) -> dict | None:
    """Return the most recent failed completed run of ``workflow`` on
    ``branch``, or None. Iterates a window of recent runs newest-first so a
    later successful run takes priority over an older failure."""
    result = run_gh([
        "run", "list",
        "--workflow", workflow,
        "--branch", branch,
        "--status", "completed",
        "--limit", "10",
        "--json", "databaseId,conclusion,event,createdAt,displayTitle,url,headSha",
    ])
    if result.returncode != 0:
        log(f"runs_list_failed workflow={workflow} branch={branch} stderr={result.stderr.strip()[:200]}")
        return None
    try:
        runs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not runs:
        return None
    # Newest-first: if the most recent completed run was successful, the
    # branch is currently green — no failures to surface even if older runs
    # failed. Only return the latest run AND only if it's a failure.
    latest = runs[0]
    if latest.get("conclusion") == "failure":
        return latest
    return None


def fetch_failed_log(run_id: int) -> str:
    """Pull only the failed-step logs (avoids needing to grep the full log)."""
    result = run_gh(["run", "view", str(run_id), "--log-failed"])
    if result.returncode != 0:
        log(f"log_fetch_failed run_id={run_id} stderr={result.stderr.strip()[:200]}")
        return ""
    return result.stdout or ""


def trim_log(text: str) -> str:
    """Keep head + tail; elide the middle if combined size exceeds the cap."""
    if len(text) <= MAX_LOG_CHARS:
        return text
    head = text[:LOG_HEAD]
    tail = text[-(MAX_LOG_CHARS - LOG_HEAD):]
    return f"{head}\n\n... [TRUNCATED {len(text) - MAX_LOG_CHARS} chars elided] ...\n\n{tail}"


def main() -> int:
    pr_number = os.environ.get("PR_NUMBER", "").strip()
    head_ref = os.environ.get("HEAD_REF", "").strip()
    if not pr_number or not head_ref:
        log("missing_env PR_NUMBER or HEAD_REF")
        return 1

    output = os.environ.get("PR_FAILURES_FILE") or f"/tmp/pr-{pr_number}-failures.md"
    workflows = [
        w.strip()
        for w in (os.environ.get("TEST_WORKFLOWS") or "ci.yml").split(",")
        if w.strip()
    ]

    log(f"pr=#{pr_number} branch={head_ref} workflows={workflows} output={output}")

    parts: list[str] = [f"# Test failures on PR #{pr_number} (branch `{head_ref}`)\n"]
    found_any = False

    for wf in workflows:
        run = latest_failed_run(wf, head_ref)
        if not run:
            log(f"latest_run_clean_or_missing workflow={wf}")
            continue

        found_any = True
        run_id = int(run.get("databaseId") or 0)
        url = run.get("url") or ""
        title = run.get("displayTitle") or ""
        created = run.get("createdAt") or ""
        sha = run.get("headSha") or ""
        log(f"failed_run workflow={wf} run_id={run_id} url={url}")

        parts.append(f"## {wf} — run {run_id}")
        parts.append(f"- **Title:** {title}")
        parts.append(f"- **Commit:** `{sha}`")
        parts.append(f"- **Created:** {created}")
        parts.append(f"- **URL:** {url}")
        parts.append("")
        parts.append("Failed-step logs (truncated):")
        parts.append("")
        parts.append("```")
        parts.append(trim_log(fetch_failed_log(run_id)))
        parts.append("```")
        parts.append("")

    if not found_any:
        log("no failed CI runs on latest commit — nothing to dump")
        # Remove any stale dump from a previous invocation on this runner.
        if os.path.exists(output):
            try:
                os.remove(output)
                log(f"removed_stale_file path={output}")
            except OSError:
                pass
        return 0

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    log(f"wrote {output} ({os.path.getsize(output)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
