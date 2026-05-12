#!/usr/bin/env python3
"""Run Claude code review file by file and capture an aggregate result."""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def log(message: str) -> None:
    print(f"[code-review] {message}", flush=True)


def run_git_command(args: list[str]) -> str:
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        log(f"git_command_failed cmd={' '.join(args)} rc={completed.returncode} stderr={stderr}")
        raise subprocess.CalledProcessError(
            completed.returncode, args, completed.stdout, completed.stderr
        )
    return completed.stdout


def commit_is_walkable(revision: str) -> bool:
    """`git log` can actually walk this revision (i.e. it's a real commit in the local object DB)."""
    completed = subprocess.run(
        ["git", "log", "-1", "--format=%H", revision],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def infer_github_repository(remote: str) -> str | None:
    try:
        remote_url = run_git_command(["git", "remote", "get-url", remote]).strip()
    except subprocess.CalledProcessError:
        return None

    if remote_url.startswith("git@github.com:"):
        path = remote_url.removeprefix("git@github.com:")
    elif remote_url.startswith("https://github.com/") or remote_url.startswith("http://github.com/"):
        path = urlparse(remote_url).path.lstrip("/")
    else:
        return None

    if path.endswith(".git"):
        path = path[:-4]
    return path or None


def revision_exists(revision: str) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", revision],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def is_commit_hash(revision: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", revision))


def strip_fence(text: str) -> str:
    text = text.strip()
    # Sometimes the model emits a bare "json" language label without backticks.
    text = re.sub(r"^json\s*\n", "", text, count=1)
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_json_list(text: str) -> list[Any] | None:
    """Find a JSON array inside Claude's output (possibly wrapped in --output-format json)."""
    text = strip_fence(text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # Claude Code wrapper: {type:"result", result:"<string containing the real payload>"}
        result = data.get("result")
        if isinstance(result, str):
            nested = extract_json_list(result)
            if nested is not None:
                return nested
        # Streaming/assistant-message wrappers: {message:{content:[{text:"..."}]}}
        message = data.get("message")
        if isinstance(message, dict):
            for content in message.get("content") or []:
                if isinstance(content, dict):
                    text_value = content.get("text")
                    if isinstance(text_value, str):
                        nested = extract_json_list(text_value)
                        if nested is not None:
                            return nested

    # Last resort: scan for an opening bracket and try raw_decode there.
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "[":
            continue
        try:
            data, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            return data

    return None


def extract_json_object(text: str) -> dict[str, Any] | None:
    text = strip_fence(text)

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

    # FIX #2: instantiate JSONDecoder lazily, only when needed for the fallback scan
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data

    return None


def load_guidelines() -> str:
    """Load project-specific review guidelines from a Markdown file.

    Path is configurable via `CODE_REVIEW_GUIDELINES_PATH` (default
    `codereview.md` at the repo root). Returns an empty string if the file
    isn't present so reviews still work in repos that haven't added one.
    """
    path = os.environ.get("CODE_REVIEW_GUIDELINES_PATH", "codereview.md")
    p = Path(path)
    if not p.exists():
        log(f"guidelines_not_found path={path}")
        return ""
    try:
        text = p.read_text(encoding="utf-8").strip()
    except OSError as e:
        log(f"guidelines_read_failed path={path} err={e}")
        return ""
    log(f"guidelines_loaded path={path} bytes={len(text)}")
    return text


def _guideline_block(guidelines: str) -> str:
    """Render the guidelines section that prepends each review prompt."""
    if not guidelines:
        return ""
    return (
        "Use the following project review guidelines as your evaluation criteria. "
        "Flag issues that violate these rules; cite the rule number in `message` "
        "when applicable. Treat unlisted concerns with lower priority.\n\n"
        "----- REVIEW GUIDELINES -----\n"
        f"{guidelines}\n"
        "----- END GUIDELINES -----\n\n"
    )


def build_file_review_prompt(filename: str, guidelines: str = "") -> str:
    return (
        f"{_guideline_block(guidelines)}"
        f"Please read the file at path '{filename}' and review its contents.\n"
        "Respond with JSON only, no prose, no markdown fence. Exact shape:\n"
        "{\n"
        '  "filename": "' + filename + '",\n'
        '  "issues": [\n'
        "    {\n"
        '      "line": 0,\n'
        '      "severity": "critical|warning|info",\n'
        '      "message": "what is wrong, in one sentence",\n'
        '      "suggestion": "concrete fix — code snippet or a one-line action"\n'
        "    }\n"
        "  ],\n"
        '  "summary": "one short sentence covering the whole file"\n'
        "}\n"
    )


def build_batch_review_prompt(filenames: list[str], guidelines: str = "") -> str:
    """Build a prompt that asks Claude to review multiple files in one pass."""
    files_list = "\n".join(f"- {f}" for f in filenames)
    return (
        f"{_guideline_block(guidelines)}"
        "Please read and review each of the following files:\n"
        f"{files_list}\n\n"
        "Respond with a JSON array only — no prose, no markdown fence. "
        "One object per file, in exactly this shape:\n"
        "[\n"
        "  {\n"
        '    "filename": "<path>",\n'
        '    "issues": [\n'
        "      {\n"
        '        "line": 0,\n'
        '        "severity": "critical|warning|info",\n'
        '        "message": "what is wrong, in one sentence",\n'
        '        "suggestion": "concrete fix — code snippet or a one-line action"\n'
        "      }\n"
        "    ],\n"
        '    "summary": "one short sentence covering the whole file"\n'
        "  }\n"
        "]\n"
    )


@dataclass(frozen=True)
class ReviewConfig:
    diff_path: str
    output_path: str
    remote: str
    base_ref: str
    head_ref: str
    model: str

    @classmethod
    def from_env(cls) -> "ReviewConfig":
        return cls(
            diff_path=os.environ.get("DIFF_FILE", "/tmp/pr-diff.txt"),
            output_path=os.environ.get(
                "CODE_REVIEW_RESULT_PATH",
                os.environ.get("CLAUDE_OUTPUT_PATH", "shared-memory/results/code-review-result.json"),
            ),
            remote=os.environ.get("DIFF_REMOTE", "origin"),
            base_ref=os.environ.get("DIFF_BASE_REF", "master"),
            head_ref=os.environ.get("DIFF_HEAD_REF", "develop"),
            # FIX #9: corrected model string
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        )


class ClaudeCodeReviewRunner:
    def __init__(self, config: ReviewConfig) -> None:
        self.config = config
        # Loaded once per run; appended to every per-file/batch prompt so
        # Claude evaluates against the project's checklist consistently.
        self._guidelines: str = load_guidelines()

    @property
    def qualified_base(self) -> str:
        return f"{self.config.remote}/{self.config.base_ref}"

    @property
    def qualified_head(self) -> str:
        return f"{self.config.remote}/{self.config.head_ref}"

    def resolve_revision(self, revision: str) -> str:
        candidates = [revision]
        if not is_commit_hash(revision):
            candidates = [f"{self.config.remote}/{revision}", revision]

        # FIX #5: handle both "main" -> "master" and "master" -> "main" fallbacks
        if revision == "main":
            candidates.extend([f"{self.config.remote}/master", "master"])
        elif revision == "master":
            candidates.extend([f"{self.config.remote}/main", "main"])

        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if revision_exists(candidate):
                return candidate

        raise ValueError(f"Unable to resolve git revision: {revision}")

    def log_config(self) -> None:
        log(f"diff_path={self.config.diff_path}")
        log(f"output_path={self.config.output_path}")
        log(f"remote={self.config.remote}")
        log(f"base_ref={self.config.base_ref}")
        log(f"head_ref={self.config.head_ref}")
        log(f"model={self.config.model}")

    def current_head(self) -> str:
        return run_git_command(["git", "rev-parse", "HEAD"]).strip()

    def fetch_refs(self) -> tuple[str, str]:
        log(
            "fetching_refs "
            f"remote={self.config.remote} base_ref={self.config.base_ref} head_ref={self.config.head_ref}"
        )
        refs_to_fetch = []
        for revision in (self.config.base_ref, self.config.head_ref):
            if not is_commit_hash(revision):
                refs_to_fetch.append(revision)

        if refs_to_fetch:
            run_git_command(
                [
                    "git",
                    "fetch",
                    "--quiet",
                    "--no-write-fetch-head",
                    self.config.remote,
                    *refs_to_fetch,
                ]
            )

        resolved_head = self.current_head()
        resolved_base = self.resolve_base_with_fallback()
        head = resolved_head
        base = run_git_command(["git", "log", "-1", "--format=%H", resolved_base]).strip()
        return head, base

    def resolve_base_with_fallback(self) -> str:
        """Resolve base_ref, then verify it's actually walkable.

        rev-parse can succeed for a SHA that git log can't walk — e.g. a
        force-pushed-away orphan, an all-zero SHA on a new branch, or an
        object that isn't a commit. In those cases, fall back to the head's
        parent, then to origin/master, so push-event diffs stay meaningful.
        """
        resolved_base = self.resolve_revision(self.config.base_ref)
        if commit_is_walkable(resolved_base):
            return resolved_base

        log(f"base_unwalkable={resolved_base} attempting_fallback")
        for fallback in ("HEAD~1", f"{self.config.remote}/master", f"{self.config.remote}/main"):
            if commit_is_walkable(fallback):
                log(f"base_fallback_chosen={fallback}")
                return fallback
        raise RuntimeError(f"Unable to find a walkable base ref; tried {resolved_base}, HEAD~1, master, main")

    def list_changed_files(self) -> list[str]:
        resolved_base = self.resolve_base_with_fallback()
        resolved_head = self.current_head()
        log(f"diff_head={resolved_head}")
        output = run_git_command(
            [
                "git",
                "diff",
                # FIX #3: correct argument order — base first, then head
                resolved_base,
                resolved_head,
                "--name-only",
                # FIX #4: removed invalid 'B' filter character
                "--diff-filter=ACMRTUX",
            ]
        )
        files = [line.strip() for line in output.splitlines() if line.strip()]
        Path(self.config.diff_path).write_text("\n".join(files) + ("\n" if files else ""), encoding="utf-8")
        return files

    def build_command(self) -> list[str]:
        return [
            "claude",
            "-p",
            "--model",
            self.config.model,
            "--max-turns",
            "100",
            "--output-format",
            "json",
        ]

    def run_file_review(self, filename: str) -> dict[str, Any]:
        cmd = self.build_command()
        prompt = build_file_review_prompt(filename, guidelines=self._guidelines)
        log(f"reviewing_file={filename}")
        log(f"command={' '.join(cmd)}")
        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as e:
            message = str(e)
            log(f"failed_to_start={e}")
            return {
                "file": filename,
                "returncode": None,
                "output": message,
                "parsed": None,
            }

        output = (completed.stdout or "") + (completed.stderr or "")
        log(f"file_returncode={completed.returncode}")
        log(f"file_output_bytes={len(output.encode())}")
        if output:
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")

        parsed = None
        if completed.stdout:
            parsed = extract_json_object(completed.stdout)

        return {
            "file": filename,
            "returncode": completed.returncode,
            "output": output,
            "parsed": parsed,
        }

    def run_batch_review(self, filenames: list[str]) -> list[dict[str, Any]]:
        """Review a batch of files in a single Claude invocation and return one result per file."""
        cmd = self.build_command()
        prompt = build_batch_review_prompt(filenames, guidelines=self._guidelines)
        log(f"reviewing_batch={filenames}")
        log(f"command={' '.join(cmd)}")
        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as e:
            log(f"failed_to_start={e}")
            return [
                {"file": f, "returncode": None, "output": str(e), "parsed": None}
                for f in filenames
            ]

        output = (completed.stdout or "") + (completed.stderr or "")
        log(f"batch_returncode={completed.returncode}")
        log(f"batch_output_bytes={len(output.encode())}")
        if output:
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")

        # Try to parse the JSON array response and map back to per-file results.
        # Claude Code with --output-format json wraps the real reply in {result:"<str>"};
        # extract_json_list dives through that wrapper and any markdown fence.
        results: list[dict[str, Any]] = []
        parsed_list: list[dict[str, Any]] | None = None
        if completed.stdout:
            found = extract_json_list(completed.stdout)
            if isinstance(found, list):
                parsed_list = [item for item in found if isinstance(item, dict)]
            else:
                # Single-object fallback (e.g. batch of 1 where the model returned a dict)
                raw = extract_json_object(completed.stdout)
                if isinstance(raw, dict) and raw.get("filename"):
                    parsed_list = [raw]
            if parsed_list is None:
                log("batch_parse_failed=no_array_found")

        # Build a filename -> parsed map for quick lookup
        parsed_by_file: dict[str, dict[str, Any]] = {}
        if parsed_list:
            for item in parsed_list:
                if isinstance(item, dict) and item.get("filename"):
                    parsed_by_file[item["filename"]] = item

        for filename in filenames:
            parsed = parsed_by_file.get(filename)
            results.append({
                "file": filename,
                "returncode": completed.returncode,
                "output": output,
                "parsed": parsed,
            })

        return results

    def build_result(
        self,
        head: str,
        base: str,
        files: list[str],
        reviews: list[dict[str, Any]],
    ) -> dict[str, Any]:
        summary = f"Reviewed {len(files)} file(s) between {self.qualified_base} and {self.qualified_head}."
        critical = []
        warnings = []
        for review in reviews:
            parsed = review.get("parsed") or {}
            filename = parsed.get("filename") or review["file"]
            for issue in parsed.get("issues") or []:
                item = {
                    "file": filename,
                    "line": issue.get("line", ""),
                    "severity": issue.get("severity", "warning"),
                    "msg": issue.get("message", ""),
                    "suggestion": issue.get("suggestion", ""),
                }
                if item["severity"] == "critical":
                    critical.append(item)
                else:
                    warnings.append(item)

            # Only surface a file-level info note when we have a real model summary —
            # never dump the raw subprocess output (it's the Claude Code wrapper JSON
            # and pollutes PR comments with hundreds of lines of metadata).
            summary_text = (parsed.get("summary") or "").strip()
            if not parsed.get("issues") and summary_text:
                warnings.append(
                    {
                        "file": filename,
                        "line": "",
                        "severity": "info",
                        "msg": summary_text,
                    }
                )

        status = "fail" if critical else "pass"
        return {
            "status": status,
            "verdict": status,
            "critical_issues": critical,
            "suggestions": warnings,
            "summary": summary,
            "details": {
                "llm_parsed": {
                    "verdict": status,
                    "critical": critical,
                    "warnings": warnings,
                    "summary": summary,
                },
                "reviewed_refs": {
                    "base": base,
                    "head": head,
                    "base_label": self.qualified_base,
                    "head_label": self.qualified_head,
                },
                "reviewed_files": files,
                "per_file_reviews": reviews,
            },
        }

    def github_api(
        self,
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
        self,
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
            chunk = self.github_api(repo, token, "GET", page_path)
            if not isinstance(chunk, list) or not chunk:
                break
            items.extend(chunk)
            if len(chunk) < per_page:
                break
            page += 1
        return items

    def event_pr_number(self) -> int | None:
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path or not os.path.exists(event_path):
            return None
        try:
            with open(event_path, encoding="utf-8") as event_file:
                event = json.load(event_file)
        except (OSError, json.JSONDecodeError):
            return None
        top_level_number = event.get("number")
        if top_level_number:
            return int(top_level_number)
        pr = event.get("pull_request") or {}
        number = pr.get("number")
        return int(number) if number else None

    def branch_pr_number(self, repo: str, token: str) -> int | None:
        branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
        if not branch:
            ref = os.environ.get("GITHUB_REF", "")
            branch = ref.removeprefix("refs/heads/")
        if not branch:
            try:
                branch = run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
            except subprocess.CalledProcessError:
                branch = ""
        if not branch:
            return None

        owner = repo.split("/", 1)[0]
        query = urlencode({"state": "open", "head": f"{owner}:{branch}"})
        pulls = self.github_api(repo, token, "GET", f"/pulls?{query}") or []
        if not pulls:
            log(f"pr_comment_no_open_pr_for_branch={branch}")
            return None
        return int(pulls[0]["number"])

    def format_pr_comment(self, data: dict[str, Any]) -> str:
        llm_parsed = data.get("details", {}).get("llm_parsed", {})
        critical = llm_parsed.get("critical") or []
        warnings = llm_parsed.get("warnings") or []
        summary = llm_parsed.get("summary") or data.get("summary") or ""
        status = data.get("status", "unknown")

        lines = [
            "<!-- agent-job-code-review-result -->",
            "## Claude Code Review Result",
            "",
            f"**Status:** `{status}`",
            f"**Critical issues:** {len(critical)}",
            f"**Warnings:** {len(warnings)}",
        ]
        if summary:
            lines.extend(["", f"**Summary:** {summary}"])
        if critical:
            lines.append("")
            lines.append("### Critical Issues")
            # FIX #7: indicate when the list is truncated
            display = critical[:10]
            for idx, issue in enumerate(display, 1):
                lines.append(f"{idx}. {issue.get('msg') or str(issue)}")
            if len(critical) > 10:
                lines.append(f"_(showing 10 of {len(critical)} critical issues)_")
        return "\n".join(lines)

    def upsert_pr_comment(self, data: dict[str, Any]) -> bool:
        token = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPOSITORY") or infer_github_repository(self.config.remote)
        if not token:
            log("pr_comment_skipped=missing_GITHUB_TOKEN")
            return False
        if not repo:
            log("pr_comment_skipped=missing_GITHUB_REPOSITORY_and_remote_inference_failed")
            return False

        try:
            pr_number = self.event_pr_number() or self.branch_pr_number(repo, token)
            if not pr_number:
                log("pr_comment_skipped=no_pr_number")
                return False

            body = self.format_pr_comment(data)
            # Paginate — busy PRs exceed the 30-per-page default and our marker
            # would otherwise be missed, causing duplicate summary comments.
            comments = self.github_api_paged(repo, token, f"/issues/{pr_number}/comments")
            marker = "<!-- agent-job-code-review-result -->"
            existing = next((comment for comment in comments if marker in comment.get("body", "")), None)
            if existing:
                self.github_api(repo, token, "PATCH", f"/issues/comments/{existing['id']}", {"body": body})
                log(f"pr_comment_updated=pr_{pr_number}")
                return True
            else:
                self.github_api(repo, token, "POST", f"/issues/{pr_number}/comments", {"body": body})
                log(f"pr_comment_created=pr_{pr_number}")
                return True
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            log(f"pr_comment_failed={type(exc).__name__}: {exc}")
            return False

    def should_require_pr_comment(self) -> bool:
        return os.environ.get("GITHUB_EVENT_NAME") == "pull_request"

    def run(self) -> None:
        self.log_config()

        head, base = self.fetch_refs()
        log(f"head={head or '<empty>'}")
        log(f"base={base or '<empty>'}")

        files = self.list_changed_files()
        log(f"changed_files={len(files)}")

        # FIX #8: explicit early exit when there are no changed files
        if not files:
            log("no_changed_files=skipping_review")
            result = self.build_result(head, base, files, [])
            Path(self.config.output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(self.config.output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
            log(f"wrote_output_path={self.config.output_path}")
            return

        # Process files in batches of 4
        batch_size = 4
        reviews: list[dict[str, Any]] = []
        for i in range(0, len(files), batch_size):
            batch = files[i : i + batch_size]
            log(f"batch={i // batch_size + 1} files={batch}")
            reviews.extend(self.run_batch_review(batch))
        result = self.build_result(head, base, files, reviews)

        Path(self.config.output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.config.output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
        log(f"wrote_output_path={self.config.output_path}")
        comment_written = self.upsert_pr_comment(result)
        if self.should_require_pr_comment() and not comment_written:
            raise RuntimeError("PR comment was not created or updated.")


def main() -> None:
    ClaudeCodeReviewRunner(ReviewConfig.from_env()).run()


if __name__ == "__main__":
    main()
