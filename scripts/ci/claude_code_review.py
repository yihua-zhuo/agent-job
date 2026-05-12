#!/usr/bin/env python3
"""Claude-powered code review: runs file-by-file review and posts inline GitHub PR comments."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from json import JSONDecoder
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(message: str) -> None:
    print(f"[code-review] {message}", flush=True)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewIssue:
    """A single issue found during a file review."""
    file: str
    line: int | str          # line number in the *new* file, or "" if unknown
    severity: str            # "critical" | "warning" | "info"
    message: str
    side: str = "RIGHT"      # GitHub diff side: "RIGHT" (new) or "LEFT" (old)

    @property
    def is_critical(self) -> bool:
        return self.severity == "critical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "msg": self.message,
        }


@dataclass
class FileReview:
    """Result of reviewing a single file."""
    file: str
    returncode: int | None
    output: str
    parsed: dict[str, Any] | None

    @property
    def issues(self) -> list[ReviewIssue]:
        if not self.parsed:
            return []
        raw_issues = self.parsed.get("issues") or []
        results: list[ReviewIssue] = []
        for issue in raw_issues:
            if not isinstance(issue, dict):
                continue
            results.append(ReviewIssue(
                file=self.parsed.get("filename") or self.file,
                line=issue.get("line", ""),
                severity=issue.get("severity", "warning"),
                message=issue.get("message", ""),
            ))
        return results

    @property
    def summary(self) -> str:
        if self.parsed:
            return self.parsed.get("summary", "")
        return self.output.strip()


@dataclass(frozen=True)
class ReviewConfig:
    """All runtime configuration, loaded from environment variables."""
    diff_path: str
    output_path: str
    remote: str
    base_ref: str
    head_ref: str
    model: str
    batch_size: int = 4

    @classmethod
    def from_env(cls) -> ReviewConfig:
        return cls(
            diff_path=os.environ.get("DIFF_FILE", "/tmp/pr-diff.txt"),
            output_path=os.environ.get(
                "CODE_REVIEW_RESULT_PATH",
                os.environ.get("CLAUDE_OUTPUT_PATH", "shared-memory/results/code-review-result.json"),
            ),
            remote=os.environ.get("DIFF_REMOTE", "origin"),
            base_ref=os.environ.get("DIFF_BASE_REF", "master"),
            head_ref=os.environ.get("DIFF_HEAD_REF", "develop"),
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            batch_size=int(os.environ.get("REVIEW_BATCH_SIZE", "5")),
        )


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

class Git:
    """Thin wrapper around git CLI commands."""

    def __init__(self, remote: str = "origin") -> None:
        self.remote = remote

    # ------------------------------------------------------------------
    # Low-level execution
    # ------------------------------------------------------------------

    def run(self, args: list[str], check: bool = True) -> str:
        completed = subprocess.run(args, check=check, capture_output=True, text=True)
        return completed.stdout

    def run_safe(self, args: list[str]) -> str | None:
        """Return stdout on success, None on failure."""
        try:
            return self.run(args, check=True)
        except subprocess.CalledProcessError:
            return None

    # ------------------------------------------------------------------
    # Repository info
    # ------------------------------------------------------------------

    def remote_url(self, remote: str | None = None) -> str | None:
        return self.run_safe(["git", "remote", "get-url", remote or self.remote])

    def infer_github_repo(self, remote: str | None = None) -> str | None:
        """Derive '<owner>/<repo>' from the remote URL, or return None."""
        url = self.remote_url(remote)
        if not url:
            return None
        url = url.strip()
        if url.startswith("git@github.com:"):
            path = url.removeprefix("git@github.com:")
        elif url.startswith(("https://github.com/", "http://github.com/")):
            path = urlparse(url).path.lstrip("/")
        else:
            return None
        path = path.removesuffix(".git")
        return path or None

    def current_head(self) -> str:
        return self.run(["git", "rev-parse", "HEAD"]).strip()

    def revision_exists(self, revision: str) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", revision],
            capture_output=True, text=True, check=False,
        )
        return result.returncode == 0

    def resolve_revision(self, revision: str, remote: str | None = None) -> str:
        """Resolve a branch name or commit hash, trying remote-qualified forms first."""
        remote = remote or self.remote
        is_hash = bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", revision))

        candidates: list[str] = [revision] if is_hash else [f"{remote}/{revision}", revision]
        if revision == "main":
            candidates += [f"{remote}/master", "master"]
        elif revision == "master":
            candidates += [f"{remote}/main", "main"]

        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if self.revision_exists(candidate):
                return candidate

        raise ValueError(f"Unable to resolve git revision: {revision!r}")

    def fetch(self, *refs: str) -> None:
        if refs:
            self.run(["git", "fetch", "--quiet", "--no-write-fetch-head", self.remote, *refs])

    def commit_hash(self, revision: str) -> str:
        return self.run(["git", "log", "-1", "--format=%H", revision]).strip()

    def changed_files(self, base: str, head: str) -> list[str]:
        output = self.run([
            "git", "diff", base, head,
            "--name-only", "--diff-filter=ACMRTUX",
        ])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def current_branch(self) -> str:
        branch = (
            os.environ.get("GITHUB_HEAD_REF")
            or os.environ.get("GITHUB_REF_NAME")
        )
        if not branch:
            ref = os.environ.get("GITHUB_REF", "")
            branch = ref.removeprefix("refs/heads/")
        if not branch:
            branch = self.run_safe(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or ""
        return branch.strip()

    def diff_for_file(self, base: str, head: str, filepath: str) -> str:
        """Return the unified diff for a single file between two refs."""
        return self.run_safe(["git", "diff", base, head, "--", filepath]) or ""


# ---------------------------------------------------------------------------
# GitHub API client
# ---------------------------------------------------------------------------

class GitHubClient:
    """GitHub REST API client focused on PR comments and reviews."""

    API_BASE = "https://api.github.com"
    REVIEW_MARKER = "<!-- agent-job-code-review-result -->"

    def __init__(self, token: str, repo: str) -> None:
        self.token = token
        self.repo = repo

    # ------------------------------------------------------------------
    # Generic request helper
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.API_BASE}/repos/{self.repo}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        body = json.dumps(payload).encode() if payload is not None else None
        req = Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urlopen(req, timeout=20) as response:
            text = response.read().decode()
        return json.loads(text) if text else None

    def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", path, payload=payload)

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("PATCH", path, payload=payload)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    # ------------------------------------------------------------------
    # PR discovery
    # ------------------------------------------------------------------

    def pr_number_from_event(self) -> int | None:
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path or not os.path.exists(event_path):
            return None
        try:
            with open(event_path, encoding="utf-8") as fh:
                event = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None
        top_level = event.get("number")
        if top_level:
            return int(top_level)
        pr = event.get("pull_request") or {}
        number = pr.get("number")
        return int(number) if number else None

    def pr_number_from_branch(self, branch: str) -> int | None:
        owner = self.repo.split("/", 1)[0]
        pulls = self.get("/pulls", {"state": "open", "head": f"{owner}:{branch}"}) or []
        if not pulls:
            log(f"pr_comment_no_open_pr_for_branch={branch}")
            return None
        return int(pulls[0]["number"])

    def resolve_pr_number(self, branch: str) -> int | None:
        return self.pr_number_from_event() or self.pr_number_from_branch(branch)

    # ------------------------------------------------------------------
    # PR summary comment (top-level, upserted)
    # ------------------------------------------------------------------

    def upsert_summary_comment(self, pr_number: int, body: str) -> None:
        comments = self.get(f"/issues/{pr_number}/comments") or []
        existing = next(
            (c for c in comments if self.REVIEW_MARKER in c.get("body", "")), None
        )
        if existing:
            self.patch(f"/issues/comments/{existing['id']}", {"body": body})
            log(f"summary_comment_updated=pr_{pr_number}")
        else:
            self.post(f"/issues/{pr_number}/comments", {"body": body})
            log(f"summary_comment_created=pr_{pr_number}")

    # ------------------------------------------------------------------
    # PR inline review comments (line-level, CodeRabbit-style)
    # ------------------------------------------------------------------

    def get_pr_head_sha(self, pr_number: int) -> str | None:
        pr = self.get(f"/pulls/{pr_number}") or {}
        return pr.get("head", {}).get("sha")

    def dismiss_previous_review_comments(self, pr_number: int) -> None:
        """Delete all previous bot review comments to avoid duplication on re-run."""
        comments = self.get(f"/pulls/{pr_number}/comments") or []
        for comment in comments:
            if self.REVIEW_MARKER in (comment.get("body") or ""):
                try:
                    self.delete(f"/pulls/comments/{comment['id']}")
                except Exception:  # best-effort cleanup; never block the review
                    pass

    def post_review_with_inline_comments(
        self,
        pr_number: int,
        commit_sha: str,
        issues: list[ReviewIssue],
        summary_body: str,
    ) -> None:
        """
        Create a single PR review containing inline comments for every issue
        that has a valid line number, plus the summary as the review body.

        Uses the Pull Requests Reviews API:
        POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
        """
        inline_comments: list[dict[str, Any]] = []
        for issue in issues:
            line = issue.line
            # Only attach inline comments when we have a concrete line number
            if not line or not str(line).strip().isdigit():
                continue
            label = _severity_emoji(issue.severity)
            body = (
                f"{self.REVIEW_MARKER}\n"
                f"{label} **{issue.severity.capitalize()}**\n\n"
                f"{issue.message}"
            )
            inline_comments.append({
                "path": issue.file,
                "line": int(line),
                "side": issue.side,
                "body": body,
            })

        review_event = "REQUEST_CHANGES" if any(i.is_critical for i in issues) else "COMMENT"

        payload: dict[str, Any] = {
            "commit_id": commit_sha,
            "body": summary_body,
            "event": review_event,
            "comments": inline_comments,
        }
        self.post(f"/pulls/{pr_number}/reviews", payload)
        log(f"inline_review_posted=pr_{pr_number} inline_comments={len(inline_comments)} event={review_event}")


# ---------------------------------------------------------------------------
# JSON / output parsing helpers
# ---------------------------------------------------------------------------

def strip_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from arbitrary Claude output."""
    text = strip_fence(text)
    decoder = JSONDecoder()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, str):
            nested = extract_json_object(result)
            if nested is not None:
                return nested
        return data

    if isinstance(data, list):
        for item in reversed(data):
            if not isinstance(item, dict):
                continue
            result = item.get("result")
            if isinstance(result, str):
                nested = extract_json_object(result)
                if nested is not None:
                    return nested
            message = item.get("message")
            if isinstance(message, dict):
                for content in reversed(message.get("content") or []):
                    if not isinstance(content, dict):
                        continue
                    text_value = content.get("text")
                    if isinstance(text_value, str):
                        nested = extract_json_object(text_value)
                        if nested is not None:
                            return nested
        return None

    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj

    return None


def extract_json_list(text: str) -> list[dict[str, Any]] | None:
    """Extract a top-level JSON array from Claude output (for batch reviews)."""
    try:
        candidate = json.loads(strip_fence(text))
        if isinstance(candidate, list):
            return candidate
    except json.JSONDecodeError:
        pass
    return None


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _file_review_prompt(filename: str) -> str:
    return (
        f"Please read the file at path '{filename}' and review its contents.\n"
        "Respond with JSON only, in exactly this shape:\n"
        "{\n"
        f'  "filename": "{filename}",\n'
        '  "issues": [\n'
        "    {\n"
        '      "line": <integer line number, or null if not applicable>,\n'
        '      "severity": "critical|warning|info",\n'
        '      "message": "concise issue description"\n'
        "    }\n"
        "  ],\n"
        '  "summary": "short overall summary"\n'
        "}\n"
    )


def _batch_review_prompt(filenames: list[str]) -> str:
    files_list = "\n".join(f"- {f}" for f in filenames)
    return (
        "Please read and review each of the following files:\n"
        f"{files_list}\n\n"
        "Respond with a JSON array only — one object per file, in exactly this shape:\n"
        "[\n"
        "  {\n"
        '    "filename": "<path>",\n'
        '    "issues": [\n'
        "      {\n"
        '        "line": <integer line number, or null if not applicable>,\n'
        '        "severity": "critical|warning|info",\n'
        '        "message": "concise issue description"\n'
        "      }\n"
        "    ],\n"
        '    "summary": "short overall summary"\n'
        "  }\n"
        "]\n"
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _severity_emoji(severity: str) -> str:
    return {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "⚪")


def _format_summary_comment(
    status: str,
    critical: list[ReviewIssue],
    warnings: list[ReviewIssue],
    summary: str,
    reviewed_files: list[str],
) -> str:
    status_icon = "✅" if status == "pass" else "❌"
    lines = [
        "<!-- agent-job-code-review-result -->",
        "## 🤖 Claude Code Review",
        "",
        f"**Status:** {status_icon} `{status}`  ",
        f"**Files reviewed:** {len(reviewed_files)}  ",
        f"**Critical issues:** {len(critical)}  ",
        f"**Warnings:** {len(warnings)}  ",
    ]
    if summary:
        lines += ["", f"**Summary:** {summary}"]

    if critical:
        lines += ["", "### 🔴 Critical Issues"]
        for idx, issue in enumerate(critical[:10], 1):
            line_ref = f" (line {issue.line})" if issue.line else ""
            lines.append(f"{idx}. `{issue.file}`{line_ref} — {issue.message}")
        if len(critical) > 10:
            lines.append(f"_…and {len(critical) - 10} more critical issues (see inline comments)_")

    if warnings:
        lines += ["", "<details>", "<summary>🟡 Warnings</summary>", ""]
        for idx, issue in enumerate(warnings[:20], 1):
            line_ref = f" (line {issue.line})" if issue.line else ""
            lines.append(f"{idx}. `{issue.file}`{line_ref} — {issue.message}")
        if len(warnings) > 20:
            lines.append(f"_…and {len(warnings) - 20} more warnings (see inline comments)_")
        lines += ["", "</details>"]

    lines += [
        "",
        "---",
        "_Review powered by [Claude](https://claude.ai) · inline comments show exact locations_",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude runner
# ---------------------------------------------------------------------------

class ClaudeRunner:
    """Executes the `claude` CLI and parses its JSON output."""

    def __init__(self, model: str) -> None:
        self.model = model

    def _base_command(self) -> list[str]:
        return [
            "claude", "-p",
            "--model", self.model,
            "--max-turns", "100",
            "--output-format", "json",
        ]

    def _invoke(self, prompt: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self._base_command(),
            input=prompt,
            capture_output=True,
            text=True,
            check=False,
        )

    def review_file(self, filename: str) -> FileReview:
        log(f"reviewing_file={filename}")
        try:
            completed = self._invoke(_file_review_prompt(filename))
        except OSError as exc:
            log(f"failed_to_start={exc}")
            return FileReview(file=filename, returncode=None, output=str(exc), parsed=None)

        output = (completed.stdout or "") + (completed.stderr or "")
        _stream_output(output)
        log(f"file_returncode={completed.returncode} bytes={len(output.encode())}")

        parsed = extract_json_object(completed.stdout) if completed.stdout else None
        return FileReview(file=filename, returncode=completed.returncode, output=output, parsed=parsed)

    def review_batch(self, filenames: list[str]) -> list[FileReview]:
        log(f"reviewing_batch={filenames}")
        try:
            completed = self._invoke(_batch_review_prompt(filenames))
        except OSError as exc:
            log(f"failed_to_start={exc}")
            return [FileReview(file=f, returncode=None, output=str(exc), parsed=None) for f in filenames]

        output = (completed.stdout or "") + (completed.stderr or "")
        _stream_output(output)
        log(f"batch_returncode={completed.returncode} bytes={len(output.encode())}")

        parsed_list: list[dict[str, Any]] | None = None
        if completed.stdout:
            parsed_list = extract_json_list(completed.stdout)
            if parsed_list is None:
                raw = extract_json_object(completed.stdout)
                if isinstance(raw, dict):
                    parsed_list = [raw]

        by_file: dict[str, dict[str, Any]] = {}
        if parsed_list:
            for item in parsed_list:
                if isinstance(item, dict) and item.get("filename"):
                    by_file[item["filename"]] = item

        return [
            FileReview(
                file=f,
                returncode=completed.returncode,
                output=output,
                parsed=by_file.get(f),
            )
            for f in filenames
        ]


def _stream_output(output: str) -> None:
    if output:
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class CodeReviewOrchestrator:
    """
    Ties together Git, ClaudeRunner and GitHubClient to perform a full
    PR code review with inline line-level comments.
    """

    def __init__(self, config: ReviewConfig) -> None:
        self.config = config
        self.git = Git(remote=config.remote)
        self.claude = ClaudeRunner(model=config.model)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _qualified_base(self) -> str:
        return f"{self.config.remote}/{self.config.base_ref}"

    @property
    def _qualified_head(self) -> str:
        return f"{self.config.remote}/{self.config.head_ref}"

    def _log_config(self) -> None:
        log(f"diff_path={self.config.diff_path}")
        log(f"output_path={self.config.output_path}")
        log(f"remote={self.config.remote}")
        log(f"base_ref={self.config.base_ref}")
        log(f"head_ref={self.config.head_ref}")
        log(f"model={self.config.model}")
        log(f"batch_size={self.config.batch_size}")

    def _fetch_refs(self) -> tuple[str, str]:
        """Fetch remote refs and return (resolved_head_sha, resolved_base_sha)."""
        log(f"fetching_refs remote={self.config.remote} base={self.config.base_ref} head={self.config.head_ref}")
        refs_to_fetch = [
            r for r in (self.config.base_ref, self.config.head_ref)
            if not re.fullmatch(r"[0-9a-fA-F]{7,40}", r)
        ]
        if refs_to_fetch:
            self.git.fetch(*refs_to_fetch)

        resolved_head = self.git.current_head()
        resolved_base_ref = self.git.resolve_revision(self.config.base_ref)
        resolved_base = self.git.commit_hash(resolved_base_ref)
        return resolved_head, resolved_base

    def _collect_all_issues(self, file_reviews: list[FileReview]) -> tuple[list[ReviewIssue], list[ReviewIssue]]:
        critical: list[ReviewIssue] = []
        warnings: list[ReviewIssue] = []
        for fr in file_reviews:
            for issue in fr.issues:
                (critical if issue.is_critical else warnings).append(issue)
            # If no structured issues were parsed, surface the summary as an info warning
            if not fr.issues and fr.summary:
                warnings.append(ReviewIssue(
                    file=fr.file, line="", severity="info", message=fr.summary,
                ))
        return critical, warnings

    def _build_result(
        self,
        head: str,
        base: str,
        files: list[str],
        file_reviews: list[FileReview],
        critical: list[ReviewIssue],
        warnings: list[ReviewIssue],
    ) -> dict[str, Any]:
        summary = f"Reviewed {len(files)} file(s) between {self._qualified_base} and {self._qualified_head}."
        status = "fail" if critical else "pass"
        return {
            "status": status,
            "verdict": status,
            "summary": summary,
            "critical_issues": [i.to_dict() for i in critical],
            "suggestions": [i.to_dict() for i in warnings],
            "details": {
                "llm_parsed": {
                    "verdict": status,
                    "critical": [i.to_dict() for i in critical],
                    "warnings": [i.to_dict() for i in warnings],
                    "summary": summary,
                },
                "reviewed_refs": {
                    "base": base,
                    "head": head,
                    "base_label": self._qualified_base,
                    "head_label": self._qualified_head,
                },
                "reviewed_files": files,
                "per_file_reviews": [
                    {
                        "file": fr.file,
                        "returncode": fr.returncode,
                        "summary": fr.summary,
                        "issues": [i.to_dict() for i in fr.issues],
                    }
                    for fr in file_reviews
                ],
            },
        }

    def _write_result(self, result: dict[str, Any]) -> None:
        out = Path(self.config.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        log(f"wrote_output_path={self.config.output_path}")

    def _should_require_pr_comment(self) -> bool:
        return os.environ.get("GITHUB_EVENT_NAME") == "pull_request"

    # ------------------------------------------------------------------
    # GitHub integration
    # ------------------------------------------------------------------

    def _build_github_client(self) -> GitHubClient | None:
        token = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPOSITORY") or self.git.infer_github_repo()
        if not token:
            log("pr_comment_skipped=missing_GITHUB_TOKEN")
            return None
        if not repo:
            log("pr_comment_skipped=missing_GITHUB_REPOSITORY_and_remote_inference_failed")
            return None
        return GitHubClient(token=token, repo=repo)

    def _post_pr_feedback(
        self,
        critical: list[ReviewIssue],
        warnings: list[ReviewIssue],
        result: dict[str, Any],
        files: list[str],
    ) -> bool:
        client = self._build_github_client()
        if client is None:
            return False

        branch = self.git.current_branch()
        try:
            pr_number = client.resolve_pr_number(branch)
            if not pr_number:
                log("pr_comment_skipped=no_pr_number")
                return False

            commit_sha = client.get_pr_head_sha(pr_number)
            if not commit_sha:
                log("pr_inline_skipped=could_not_resolve_head_sha")
                commit_sha = ""

            status = result.get("status", "unknown")
            summary = result.get("summary", "")
            summary_body = _format_summary_comment(status, critical, warnings, summary, files)

            # 1. Upsert the top-level summary comment
            client.upsert_summary_comment(pr_number, summary_body)

            # 2. Post inline review with per-line comments (CodeRabbit-style)
            if commit_sha:
                all_issues = critical + warnings
                client.dismiss_previous_review_comments(pr_number)
                client.post_review_with_inline_comments(
                    pr_number=pr_number,
                    commit_sha=commit_sha,
                    issues=all_issues,
                    summary_body=summary_body,
                )
            return True

        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            log(f"pr_comment_failed={type(exc).__name__}: {exc}")
            return False

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        self._log_config()

        head, base = self._fetch_refs()
        log(f"head={head}")
        log(f"base={base}")

        # Collect changed files and write the diff list
        files = self.git.changed_files(base, head)
        log(f"changed_files={len(files)}")
        diff_path = Path(self.config.diff_path)
        diff_path.write_text("\n".join(files) + ("\n" if files else ""), encoding="utf-8")

        if not files:
            log("no_changed_files=skipping_review")
            result = self._build_result(head, base, [], [], [], [])
            self._write_result(result)
            return

        # Run reviews in batches
        file_reviews: list[FileReview] = []
        for batch_start in range(0, len(files), self.config.batch_size):
            batch = files[batch_start: batch_start + self.config.batch_size]
            log(f"batch={batch_start // self.config.batch_size + 1} files={batch}")
            file_reviews.extend(self.claude.review_batch(batch))

        critical, warnings = self._collect_all_issues(file_reviews)
        result = self._build_result(head, base, files, file_reviews, critical, warnings)
        self._write_result(result)

        comment_written = self._post_pr_feedback(critical, warnings, result, files)
        if self._should_require_pr_comment() and not comment_written:
            raise RuntimeError("PR comment was not created or updated.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    CodeReviewOrchestrator(ReviewConfig.from_env()).run()


if __name__ == "__main__":
    main()
