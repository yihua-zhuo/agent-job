#!/usr/bin/env python3
"""Parse Claude code-review output and save the structured result."""

import json
import os
from json import JSONDecoder
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def log(message: str) -> None:
    print(f"[code-review-parser] {message}", flush=True)


def _strip_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract JSON from Claude Code output.

    `claude --output-format json` returns an outer JSON object whose `result`
    field may itself be a JSON string. Older logs may contain plain text around
    the JSON. Handle both shapes.
    """
    text = _strip_fence(text)
    decoder = JSONDecoder()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, str):
            try:
                return _extract_json_object(result)
            except ValueError:
                pass
        return data

    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            result = data.get("result")
            if isinstance(result, str):
                try:
                    return _extract_json_object(result)
                except ValueError:
                    pass
            return data

    raise ValueError("No JSON object found in Claude output")


def _issue_dict(issue: Any, default_dim: str) -> dict[str, Any]:
    if isinstance(issue, dict):
        msg = issue.get("msg") or issue.get("message") or issue.get("issue") or issue.get("description") or str(issue)
        return {
            "dim": issue.get("dim") or issue.get("category") or default_dim,
            "line": issue.get("line", ""),
            "msg": msg,
        }
    return {"dim": default_dim, "line": "", "msg": str(issue)}


def _github_api(repo: str, token: str, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
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


def _event_pr_number() -> int | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        return None
    try:
        with open(event_path) as f:
            event = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    pr = event.get("pull_request") or {}
    number = pr.get("number")
    return int(number) if number else None


def _branch_pr_number(repo: str, token: str) -> int | None:
    branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME")
    if not branch:
        ref = os.environ.get("GITHUB_REF", "")
        branch = ref.removeprefix("refs/heads/")
    if not branch:
        return None

    owner = repo.split("/", 1)[0]
    query = urlencode({"state": "open", "head": f"{owner}:{branch}"})
    pulls = _github_api(repo, token, "GET", f"/pulls?{query}") or []
    if not pulls:
        log(f"pr_comment_no_open_pr_for_branch={branch}")
        return None
    return int(pulls[0]["number"])


def _format_pr_comment(data: dict[str, Any]) -> str:
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
        for idx, issue in enumerate(critical[:10], 1):
            msg = issue.get("msg") if isinstance(issue, dict) else str(issue)
            lines.append(f"{idx}. {msg}")
    return "\n".join(lines)


def _upsert_pr_comment(data: dict[str, Any]) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        log("pr_comment_skipped=missing_GITHUB_TOKEN_or_GITHUB_REPOSITORY")
        return

    try:
        pr_number = _event_pr_number() or _branch_pr_number(repo, token)
        if not pr_number:
            log("pr_comment_skipped=no_pr_number")
            return

        body = _format_pr_comment(data)
        comments = _github_api(repo, token, "GET", f"/issues/{pr_number}/comments") or []
        marker = "<!-- agent-job-code-review-result -->"
        existing = next((c for c in comments if marker in c.get("body", "")), None)
        if existing:
            _github_api(repo, token, "PATCH", f"/issues/comments/{existing['id']}", {"body": body})
            log(f"pr_comment_updated=pr_{pr_number}")
        else:
            _github_api(repo, token, "POST", f"/issues/{pr_number}/comments", {"body": body})
            log(f"pr_comment_created=pr_{pr_number}")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
        log(f"pr_comment_failed={type(e).__name__}: {e}")


def normalize_code_review_result(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize Claude's prompt schema into the pipeline envelope schema."""
    if "details" in data and "status" in data:
        return data

    verdict = data.get("verdict") or data.get("status")
    critical_raw = data.get("critical_issues") or data.get("critical") or []
    suggestions = data.get("suggestions") or data.get("warnings") or []
    summary = data.get("summary", "")

    if not isinstance(critical_raw, list):
        critical_raw = [critical_raw]
    if not isinstance(suggestions, list):
        suggestions = [suggestions]

    critical = [_issue_dict(issue, "critical") for issue in critical_raw]
    status = "fail" if verdict == "fail" or critical else "pass"

    return {
        "status": status,
        "verdict": verdict or status,
        "critical_issues": critical_raw,
        "suggestions": suggestions,
        "summary": summary,
        "details": {
            "llm_parsed": {
                "verdict": verdict or status,
                "critical": critical,
                "warnings": suggestions,
                "summary": summary,
            }
        },
    }


def main() -> None:
    input_path = os.environ.get("CLAUDE_OUTPUT_PATH", "/tmp/claude-output.txt")
    output_path = os.environ.get(
        "CODE_REVIEW_RESULT_PATH",
        "shared-memory/results/code-review-result.json",
    )

    with open(input_path) as f:
        text = f.read()

    log(f"input_path={input_path}")
    log(f"input_exists={os.path.exists(input_path)}")
    log(f"input_bytes={len(text.encode())}")
    log(f"output_path={output_path}")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    try:
        extracted = _extract_json_object(text)
        log(f"extracted_keys={sorted(extracted.keys())}")
        data = normalize_code_review_result(extracted)
        llm_parsed = data.get("details", {}).get("llm_parsed", {})
        log(f"normalized_status={data.get('status')}")
        log(f"critical_count={len(llm_parsed.get('critical') or [])}")
        log(f"warning_count={len(llm_parsed.get('warnings') or [])}")
    except Exception as e:
        log(f"parse_error={type(e).__name__}: {e}")
        data = {
            "status": "fail",
            "error": str(e),
            "raw": text[-500:],
            "details": {
                "llm_parsed": {
                    "critical": [
                        {
                            "dim": "pipeline",
                            "line": "",
                            "msg": f"Failed to parse Claude code-review output: {e}",
                        }
                    ],
                    "warnings": [],
                    "summary": "Code review output could not be parsed.",
                }
            },
        }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    log(f"wrote_result={output_path}")
    _upsert_pr_comment(data)


if __name__ == "__main__":
    main()
