#!/usr/bin/env python3
"""Post inline PR review comments from a code-review-result.json file.

Reads the JSON produced by `run_claude_code_review.py`, finds the open PR
for the current event/branch, and creates a single GitHub PR review with
one inline comment per issue (critical + suggestions). Issues missing a
file/line — or whose line lies outside the PR diff — are folded into the
review's summary body so nothing is silently dropped.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


SUMMARY_MARKER = "<!-- agent-job-code-review-line-comments -->"
INLINE_MARKER = "<!-- agent-job-code-review-inline -->"


def log(message: str) -> None:
    print(f"[pr-line-comments] {message}", flush=True)


def github_api(
    repo: str,
    token: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    url = f"https://api.github.com/repos/{repo}{path}"
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=20) as response:
        text = response.read().decode()
    return json.loads(text) if text else None


def github_api_paged(
    repo: str,
    token: str,
    path: str,
    per_page: int = 100,
) -> list[Any]:
    """GET all pages of a list endpoint. Stops when a short page is returned."""
    items: list[Any] = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        page_path = f"{path}{sep}per_page={per_page}&page={page}"
        chunk = github_api(repo, token, "GET", page_path)
        if not isinstance(chunk, list) or not chunk:
            break
        items.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1
    return items


def github_graphql(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    """POST a GraphQL request to api.github.com/graphql."""
    body = json.dumps({"query": query, "variables": variables}).encode()
    request = Request(
        "https://api.github.com/graphql",
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=20) as response:
        text = response.read().decode()
    payload = json.loads(text) if text else {}
    if isinstance(payload, dict) and payload.get("errors"):
        raise RuntimeError(f"graphql_errors: {payload['errors']}")
    return payload


REVIEW_THREADS_QUERY = """
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
          comments(first: 5) {
            nodes { id body }
          }
        }
      }
    }
  }
}
"""

RESOLVE_THREAD_MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""


def fetch_review_threads(repo: str, token: str, pr_number: int) -> list[dict[str, Any]]:
    """Return all review threads on the PR (paginated, includes resolved ones)."""
    owner, name = repo.split("/", 1)
    threads: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        result = github_graphql(
            token,
            REVIEW_THREADS_QUERY,
            {"owner": owner, "repo": name, "number": pr_number, "cursor": cursor},
        )
        page = result["data"]["repository"]["pullRequest"]["reviewThreads"]
        threads.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return threads


def resolve_thread(token: str, thread_id: str) -> None:
    github_graphql(token, RESOLVE_THREAD_MUTATION, {"threadId": thread_id})


def infer_repo(remote: str = "origin") -> str | None:
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", remote],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    if url.startswith("git@github.com:"):
        path = url.removeprefix("git@github.com:")
    elif url.startswith(("https://github.com/", "http://github.com/")):
        path = urlparse(url).path.lstrip("/")
    else:
        return None
    if path.endswith(".git"):
        path = path[:-4]
    return path or None


def event_pr_number() -> int | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        return None
    try:
        with open(event_path, encoding="utf-8") as f:
            event = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    top = event.get("number")
    if top:
        return int(top)
    pr = event.get("pull_request") or {}
    n = pr.get("number")
    return int(n) if n else None


def branch_pr_number(repo: str, token: str) -> int | None:
    branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
    if not branch:
        branch = os.environ.get("GITHUB_REF", "").removeprefix("refs/heads/")
    if not branch:
        try:
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            branch = ""
    if not branch:
        return None
    owner = repo.split("/", 1)[0]
    query = urlencode({"state": "open", "head": f"{owner}:{branch}"})
    pulls = github_api(repo, token, "GET", f"/pulls?{query}") or []
    if not pulls:
        log(f"no_open_pr_for_branch={branch}")
        return None
    return int(pulls[0]["number"])


def build_comments(
    result: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Split issues into inline comments (with a path+line) vs. leftover body lines."""
    inline: list[dict[str, Any]] = []
    leftover: list[str] = []

    items: list[tuple[str, dict[str, Any]]] = []
    for issue in result.get("critical_issues") or []:
        items.append(("critical", issue))
    for issue in result.get("suggestions") or []:
        items.append(("suggestion", issue))

    for kind, issue in items:
        path = issue.get("file")
        line_raw = issue.get("line")
        msg = (issue.get("msg") or "").strip()
        suggestion = (issue.get("suggestion") or "").strip()
        severity = (issue.get("severity") or kind).upper()

        header = f"**{severity}** ({kind})"
        parts = [header]
        if msg:
            parts.append(f"**Issue:** {msg}")
        if suggestion:
            parts.append(f"**Suggestion:** {suggestion}")
        body = "\n\n".join(parts)

        try:
            line_int = int(line_raw)
        except (TypeError, ValueError):
            line_int = 0

        if path and line_int > 0:
            inline.append(
                {
                    "path": path,
                    "line": line_int,
                    "side": "RIGHT",
                    "body": f"{INLINE_MARKER}\n{body}",
                }
            )
        else:
            label = f"`{path}`" if path else "(no file)"
            leftover.append(f"- {label}: {msg or '(no message)'}")

    return inline, leftover


def build_review_body(
    result: dict[str, Any],
    inline_count: int,
    no_line: list[str],
    failed: list[str],
) -> str:
    summary = result.get("summary") or ""
    status = result.get("status", "unknown")
    lines = [
        SUMMARY_MARKER,
        "## Claude Code Review (inline)",
        "",
        f"**Status:** `{status}`",
        f"**Inline comments posted:** {inline_count}",
    ]
    if summary:
        lines.extend(["", f"**Summary:** {summary}"])
    if no_line:
        lines.extend(["", "### Issues without a usable file/line"])
        lines.extend(no_line)
    if failed:
        lines.extend(["", "### Issues that could not be posted inline"])
        lines.extend(failed)
    return "\n".join(lines)


def post_inline_comment(
    repo: str,
    token: str,
    pr_number: int,
    commit_sha: str,
    comment: dict[str, Any],
) -> tuple[bool, str]:
    """POST a single inline comment via /pulls/{pr}/comments. Returns (ok, detail)."""
    payload = {
        "body": comment["body"],
        "commit_id": commit_sha,
        "path": comment["path"],
        "line": comment["line"],
        "side": comment.get("side", "RIGHT"),
    }
    try:
        github_api(repo, token, "POST", f"/pulls/{pr_number}/comments", payload)
        return True, ""
    except HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        return False, f"HTTP {e.code}: {detail}"
    except (URLError, TimeoutError, OSError) as e:
        return False, f"{type(e).__name__}: {e}"


def upsert_summary_comment(
    repo: str,
    token: str,
    pr_number: int,
    body: str,
) -> bool:
    """Post or update a single top-level summary issue comment, keyed by SUMMARY_MARKER.

    Paginates through ALL existing issue comments — busy PRs frequently exceed
    the 30-per-page default, and a marker on page 2 would otherwise be missed,
    resulting in a duplicate summary comment on every run.
    """
    try:
        comments = github_api_paged(repo, token, f"/issues/{pr_number}/comments")
        existing = next((c for c in comments if SUMMARY_MARKER in (c.get("body") or "")), None)
        if existing:
            github_api(repo, token, "PATCH", f"/issues/comments/{existing['id']}", {"body": body})
            log(f"summary_comment_updated=pr_{pr_number} scanned={len(comments)}")
        else:
            github_api(repo, token, "POST", f"/issues/{pr_number}/comments", {"body": body})
            log(f"summary_comment_created=pr_{pr_number} scanned={len(comments)}")
        return True
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        log(f"summary_comment_failed={type(e).__name__}: {e}")
        return False


def reconcile_review_threads(
    repo: str,
    token: str,
    pr_number: int,
    current_findings: set[tuple[str, int]],
) -> set[tuple[str, int]]:
    """Resolve bot-authored threads that no longer match current findings.

    Returns the set of (path, line) pairs that still have an OPEN bot-authored
    thread — callers should skip posting duplicates for those.

    A thread is resolved (via GraphQL `resolveReviewThread`) when:
      - it carries our INLINE_MARKER in any of its comments, AND
      - it is not already resolved, AND
      - either it's `isOutdated` (the line was rewritten by a later commit), or
        its (path, line) is no longer in `current_findings` (issue was fixed).

    Using "resolve" instead of "delete" preserves the review history in the PR
    UI — the comment stays visible but marked as resolved, so reviewers can
    trace which findings were addressed.
    """
    try:
        threads = fetch_review_threads(repo, token, pr_number)
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, KeyError) as e:
        log(f"reconcile_list_failed={type(e).__name__}: {e}")
        return set()

    kept_open: set[tuple[str, int]] = set()
    resolved_count = 0
    skipped_non_bot = 0

    for thread in threads:
        if thread.get("isResolved"):
            continue
        is_bot = any(
            INLINE_MARKER in (c.get("body") or "")
            for c in (thread.get("comments", {}).get("nodes") or [])
        )
        if not is_bot:
            skipped_non_bot += 1
            continue

        path = thread.get("path") or ""
        line = thread.get("line") or thread.get("originalLine") or 0
        try:
            line_int = int(line)
        except (TypeError, ValueError):
            line_int = 0

        is_outdated = bool(thread.get("isOutdated"))
        still_flagged = (path, line_int) in current_findings

        if is_outdated or not still_flagged:
            try:
                resolve_thread(token, thread["id"])
                resolved_count += 1
                reason = "outdated" if is_outdated else "fixed"
                log(f"resolved_thread path={path} line={line_int} reason={reason}")
            except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as e:
                log(f"resolve_failed thread={thread.get('id')} err={type(e).__name__}: {e}")
        else:
            kept_open.add((path, line_int))

    log(
        f"reconciled_threads scanned={len(threads)} "
        f"non_bot_skipped={skipped_non_bot} "
        f"resolved={resolved_count} "
        f"kept_open={len(kept_open)}"
    )
    return kept_open


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        log("missing_GITHUB_TOKEN")
        return 1

    repo = os.environ.get("GITHUB_REPOSITORY") or infer_repo()
    if not repo:
        log("missing_GITHUB_REPOSITORY_and_remote_inference_failed")
        return 1

    result_path = os.environ.get(
        "CODE_REVIEW_RESULT_PATH",
        "shared-memory/results/code-review-result.json",
    )
    if not Path(result_path).exists():
        log(f"missing_result_file={result_path}")
        return 1

    with open(result_path, encoding="utf-8") as f:
        result = json.load(f)

    pr_number = event_pr_number() or branch_pr_number(repo, token)
    if not pr_number:
        log("no_pr_number_found")
        return 0  # not fatal — push events without an open PR are valid

    pr = github_api(repo, token, "GET", f"/pulls/{pr_number}")
    commit_sha = (pr or {}).get("head", {}).get("sha")
    if not commit_sha:
        log(f"no_head_sha_for_pr={pr_number}")
        return 1

    inline, leftover = build_comments(result)
    log(f"pr={pr_number} commit={commit_sha} inline={len(inline)} leftover={len(leftover)}")

    # Build the set of (path, line) findings still active this run. Pass it to
    # reconcile_review_threads so it can resolve bot threads that were fixed
    # (no longer in this set) or outdated (line rewritten by a later commit),
    # while reporting back which (path, line) pairs already have an open bot
    # thread — those we skip to avoid duplicate comments.
    current_findings: set[tuple[str, int]] = {
        (c["path"], c["line"]) for c in inline
    }
    already_open = reconcile_review_threads(repo, token, pr_number, current_findings)

    to_post = [c for c in inline if (c["path"], c["line"]) not in already_open]
    log(f"to_post={len(to_post)} skipped_duplicates={len(inline) - len(to_post)}")

    posted = 0
    failed: list[str] = []
    for comment in to_post:
        ok, detail = post_inline_comment(repo, token, pr_number, commit_sha, comment)
        if ok:
            posted += 1
            log(f"inline_posted path={comment['path']} line={comment['line']}")
        else:
            failed.append(f"`{comment['path']}` L{comment['line']}: {comment['body']} — _{detail}_")
            log(f"inline_failed path={comment['path']} line={comment['line']} detail={detail}")

    active = posted + len(already_open)
    body = build_review_body(result, active, leftover, failed)
    summary_ok = upsert_summary_comment(repo, token, pr_number, body)
    log(
        f"done active={active} posted={posted} reused={len(already_open)} "
        f"failed={len(failed)} leftover={len(leftover)} summary_ok={summary_ok}"
    )
    return 0 if summary_ok or active else 1


if __name__ == "__main__":
    sys.exit(main())
