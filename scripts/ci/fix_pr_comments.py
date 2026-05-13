#!/usr/bin/env python3
"""Fetch unresolved reviewer feedback on a PR and have Claude Code fix it.

Designed to run on the PR's head branch (the workflow checks it out before
invoking this script). Fetches:

- Inline review threads via GraphQL, filtered to ``isResolved == false``
  and ``isOutdated == false``.
- Top-level conversation comments via REST.

Strips bot-authored comments (matched by HTML-comment markers our other
workflows leave behind) so we don't try to "fix" our own summary posts,
then formats the rest as actionable feedback and passes it to Claude
with bypassPermissions. Claude edits files in place; the workflow stages,
commits, and pushes back to the feature branch.
"""

import json
import os
import select
import subprocess
import sys
import time


# Markers our other pipelines leave on bot-authored comments — skip them
# so we don't ask Claude to "address" our own summaries.
BOT_MARKERS = (
    "<!-- agent-job-code-review-result -->",
    "<!-- agent-job-code-review-line-comments -->",
    "<!-- agent-job-code-review-inline -->",
    "<!-- agent-job-issue-validator -->",
    "<!-- agent-job-issue-preparer -->",
)


def log(msg: str) -> None:
    print(f"[fix-pr-comments] {msg}", flush=True)


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def infer_repo() -> str | None:
    env_repo = os.environ.get("GITHUB_REPOSITORY")
    if env_repo:
        return env_repo
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    if url.startswith("git@github.com:"):
        path = url.removeprefix("git@github.com:")
    elif "github.com/" in url:
        path = url.split("github.com/", 1)[1]
    else:
        return None
    return path.removesuffix(".git") or None


def fetch_review_threads(repo: str, pr_number: int) -> list[dict]:
    """Inline-comment threads on the PR, paginated via GraphQL.

    Only returns threads where ``isResolved == false`` and ``isOutdated == false``,
    so resolved or commit-superseded feedback isn't re-applied.
    """
    owner, name = repo.split("/", 1)
    query = """
    query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $number) {
          reviewThreads(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              isResolved
              isOutdated
              path
              line
              originalLine
              comments(first: 20) {
                nodes {
                  id
                  body
                  author { login }
                  createdAt
                }
              }
            }
          }
        }
      }
    }
    """
    threads: list[dict] = []
    cursor: str | None = None
    while True:
        args = [
            "api", "graphql",
            "-f", f"query={query}",
            "-F", f"owner={owner}",
            "-F", f"repo={name}",
            "-F", f"number={pr_number}",
        ]
        if cursor:
            args.extend(["-F", f"cursor={cursor}"])
        result = run_gh(args)
        if result.returncode != 0:
            log(f"graphql_failed rc={result.returncode} stderr={result.stderr.strip()[:200]}")
            break
        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            break
        page = (data.get("data") or {}).get("repository", {}).get("pullRequest", {}).get("reviewThreads", {})
        threads.extend(page.get("nodes") or [])
        info = page.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            break
        cursor = info.get("endCursor")
    # Filter to unresolved & not-outdated
    return [t for t in threads if not t.get("isResolved") and not t.get("isOutdated")]


def fetch_issue_comments(repo: str, pr_number: int) -> list[dict]:
    """Top-level conversation comments on the PR (paginated REST)."""
    comments: list[dict] = []
    page = 1
    while True:
        result = run_gh([
            "api",
            f"/repos/{repo}/issues/{pr_number}/comments?per_page=100&page={page}",
        ])
        if result.returncode != 0:
            log(f"issue_comments_failed page={page} rc={result.returncode}")
            break
        try:
            chunk = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            break
        if not chunk:
            break
        comments.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return comments


def is_bot_authored(body: str) -> bool:
    return any(marker in (body or "") for marker in BOT_MARKERS)


def build_actionable_feedback(
    threads: list[dict],
    issue_comments: list[dict],
) -> list[dict]:
    """Distil raw API output into a flat list of feedback items."""
    items: list[dict] = []

    for thread in threads:
        comments = (thread.get("comments") or {}).get("nodes") or []
        if not comments:
            continue
        # If every comment in the thread is bot-authored, skip — that's a
        # summary thread we left ourselves, not reviewer feedback.
        if all(is_bot_authored(c.get("body") or "") for c in comments):
            continue
        items.append({
            "kind": "inline",
            "path": thread.get("path"),
            "line": thread.get("line") or thread.get("originalLine"),
            "comments": [
                {
                    "author": ((c.get("author") or {}).get("login")) or "unknown",
                    "body": (c.get("body") or "").strip(),
                }
                for c in comments
                if not is_bot_authored(c.get("body") or "")
            ],
        })

    for c in issue_comments:
        body = (c.get("body") or "").strip()
        if not body or is_bot_authored(body):
            continue
        items.append({
            "kind": "conversation",
            "author": ((c.get("user") or {}).get("login")) or "unknown",
            "body": body,
        })

    return items


def format_feedback_md(items: list[dict]) -> str:
    parts: list[str] = []
    for i, item in enumerate(items, 1):
        if item["kind"] == "inline":
            parts.append(f"### {i}. Inline on `{item['path']}` line {item['line']}")
            for c in item["comments"]:
                parts.append(f"- **@{c['author']}**: {c['body']}")
        else:
            parts.append(f"### {i}. Conversation comment from @{item['author']}")
            parts.append(item["body"])
        parts.append("")
    return "\n".join(parts)


def build_prompt(pr_number: str, head_ref: str, feedback_md: str, failures_md: str = "") -> str:
    # When the latest CI run on the PR's branch failed, the workflow's
    # fetch_pr_test_failures.py step dumps the failed-step logs into a temp
    # file and exposes them via PR_FAILURES_FILE. We splice them in here so
    # Claude treats them as the FIRST thing to fix — broken tests block any
    # downstream review work.
    failure_section = ""
    failures_intro = ""
    if failures_md.strip():
        failure_section = f"""

----- CI TEST FAILURES (latest failed run on this branch) -----
{failures_md}
----- END CI TEST FAILURES -----
"""
        failures_intro = " AND fixing the CI test failures listed below"

    return f"""You are addressing reviewer feedback{failures_intro} on PR #{pr_number} (branch `{head_ref}`).{failure_section}

Below is every unresolved actionable reviewer comment on the PR. Each item
is feedback you must address by modifying the code at the indicated location.

----- REVIEWER FEEDBACK -----
{feedback_md}
----- END FEEDBACK -----

Rules:

0. If CI TEST FAILURES are listed above, fix them FIRST. Read the failed
   step's log carefully, locate the source of the failure (which test, which
   line, which assertion or exception), and apply the fix. Verify by
   re-running that specific test before moving on. Reviewer feedback can
   wait; tests blocking merge cannot.

1. For each reviewer comment, make the change the reviewer is asking for.
   Read the file at the indicated path + line BEFORE editing it.

2. If feedback is wrong, ambiguous, or would break things (contradicts
   another comment, scope-creeps outside the PR, asks for a fix that fails
   tests), make your best-effort interpretation. Note the reasoning in your
   final summary — don't silently ignore it.

3. After ALL fixes (both test failures and reviewer feedback), run the full
   validation suite. Every command must exit 0:
       PYTHONPATH=src ruff check src/
       PYTHONPATH=src pytest tests/unit/ -v
       DATABASE_URL=postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db PYTHONPATH=src pytest tests/integration/ -v
   If a fix breaks tests, refine it — don't revert. If you genuinely cannot
   make a fix work, skip it (explicitly noted in your summary) rather than
   leaving broken code.

4. Do NOT run `git commit`, `git push`, `git add`, `git stash`, `git reset`,
   or modify `.git/`. Leave changes as unstaged edits — the workflow stages,
   commits, and pushes after you finish.

5. Do NOT modify `.github/workflows/`, `scripts/ci/`, or `.plans/`.

6. Stop when every CI failure is fixed, every actionable reviewer item is
   addressed, and all three checks are green. Print a numbered summary
   mapping each item to one of:
       - "FIXED: <one-line description of change>"
       - "SKIPPED: <reason>"  (only when you genuinely couldn't fix it)
   Group CI failures separately from reviewer feedback in your summary.
"""


def stream_claude(cmd: list[str], prompt: str, timeout: int) -> int | None:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    stdout_fd = proc.stdout.fileno()
    stderr_fd = proc.stderr.fileno()
    streams = {
        stdout_fd: (proc.stdout, sys.stdout),
        stderr_fd: (proc.stderr, sys.stderr),
    }
    open_fds = {stdout_fd, stderr_fd}
    start = time.monotonic()
    while open_fds:
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            proc.kill()
            return None
        ready, _, _ = select.select(list(open_fds), [], [], min(1.0, remaining))
        if not ready:
            if proc.poll() is not None:
                pass
            continue
        for fd in ready:
            stream, out = streams[fd]
            line = stream.readline()
            if not line:
                open_fds.discard(fd)
                continue
            out.write(line)
            out.flush()
    try:
        proc.wait(timeout=max(1, timeout - (time.monotonic() - start)))
    except subprocess.TimeoutExpired:
        proc.kill()
        return None
    return proc.returncode


def main() -> int:
    pr_number = os.environ.get("PR_NUMBER", "").strip()
    head_ref = os.environ.get("HEAD_REF", "").strip() or "unknown"
    if not pr_number:
        log("missing_env PR_NUMBER")
        return 1

    repo = infer_repo()
    if not repo:
        log("missing_GITHUB_REPOSITORY_and_remote_inference_failed")
        return 1

    log(f"repo={repo} pr={pr_number} head_ref={head_ref}")

    try:
        pr_n = int(pr_number)
    except ValueError:
        log(f"invalid_PR_NUMBER={pr_number}")
        return 1

    threads = fetch_review_threads(repo, pr_n)
    issue_comments = fetch_issue_comments(repo, pr_n)
    log(f"unresolved_threads={len(threads)} conversation_comments={len(issue_comments)}")

    items = build_actionable_feedback(threads, issue_comments)
    log(f"actionable_items={len(items)}")

    # Load CI failure dump (written by fetch_pr_test_failures.py earlier in
    # the workflow). Path is configurable via env so this script doesn't
    # hardcode /tmp; absent file means no current failures.
    failures_md = ""
    failures_path = os.environ.get("PR_FAILURES_FILE", "").strip()
    if failures_path and os.path.exists(failures_path):
        try:
            with open(failures_path, encoding="utf-8") as f:
                failures_md = f.read().strip()
            log(f"loaded_failures path={failures_path} bytes={len(failures_md)}")
        except OSError as e:
            log(f"failures_read_failed path={failures_path} err={e}")
    else:
        log(f"no_failures_file path={failures_path or '(unset)'}")

    if not items and not failures_md:
        log("no_actionable_feedback_and_no_failures — exiting cleanly")
        return 0

    feedback_md = format_feedback_md(items) if items else "(no unresolved reviewer comments)"
    prompt = build_prompt(pr_number, head_ref, feedback_md, failures_md)

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "2400"))  # 40 min
    max_turns = os.environ.get("CLAUDE_MAX_TURNS", "150")
    cmd = [
        "claude", "-p",
        "--model", model,
        "--max-turns", max_turns,
        "--output-format", "json",
        "--permission-mode", "bypassPermissions",
    ]
    log(f"invoking_claude model={model} max_turns={max_turns} timeout={timeout}s")

    try:
        rc = stream_claude(cmd, prompt, timeout)
    except OSError as e:
        log(f"claude_not_runnable: {e}")
        return 1

    if rc is None:
        log("claude_timed_out")
        return 1
    if rc != 0:
        log(f"claude_failed rc={rc}")
        return rc
    log("claude_finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
