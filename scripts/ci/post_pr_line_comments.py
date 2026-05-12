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


def dismiss_previous_inline_comments(
    repo: str,
    token: str,
    pr_number: int,
) -> int:
    """Delete prior inline review comments marked with INLINE_MARKER.

    Paginates through ALL PR review comments — without this, stale inline
    comments from earlier runs accumulate on every push (the 30-per-page
    default hides anything that drifted onto page 2+).

    Returns the number of comments deleted.
    """
    try:
        comments = github_api_paged(repo, token, f"/pulls/{pr_number}/comments")
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        log(f"dismiss_list_failed={type(e).__name__}: {e}")
        return 0

    stale = [c for c in comments if INLINE_MARKER in (c.get("body") or "")]
    deleted = 0
    for c in stale:
        try:
            github_api(repo, token, "DELETE", f"/pulls/comments/{c['id']}")
            deleted += 1
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            log(f"dismiss_delete_failed id={c.get('id')} err={type(e).__name__}: {e}")
    log(f"dismissed_inline_comments scanned={len(comments)} stale={len(stale)} deleted={deleted}")
    return deleted


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

    # Clear prior bot-authored inline comments so a re-run on the same PR
    # doesn't pile duplicates on top of (still-valid or now-stale) earlier comments.
    dismiss_previous_inline_comments(repo, token, pr_number)

    posted = 0
    failed: list[str] = []
    for comment in inline:
        ok, detail = post_inline_comment(repo, token, pr_number, commit_sha, comment)
        if ok:
            posted += 1
            log(f"inline_posted path={comment['path']} line={comment['line']}")
        else:
            failed.append(f"`{comment['path']}` L{comment['line']}: {comment['body']} — _{detail}_")
            log(f"inline_failed path={comment['path']} line={comment['line']} detail={detail}")

    body = build_review_body(result, posted, leftover, failed)
    summary_ok = upsert_summary_comment(repo, token, pr_number, body)
    log(f"done posted={posted} failed={len(failed)} leftover={len(leftover)} summary_ok={summary_ok}")
    return 0 if summary_ok or posted else 1


if __name__ == "__main__":
    sys.exit(main())
