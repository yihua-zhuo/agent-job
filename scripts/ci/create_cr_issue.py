#!/usr/bin/env python3
"""Track Claude code-review critical findings via a single GitHub Issue.

Mirrors create_doc_sync_issue.py:
- On `fail` with critical issues → update an existing open `code-review-critical`
  issue, or create one if none exists. One persistent tracking issue per repo,
  not one issue per failing run.
- On `pass` (or no critical) → close the existing tracking issue with a short
  resolution comment.

Called by pipeline-code-review.yml.
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any


LABEL = "code-review-critical"
EXTRA_LABELS = ("pipeline", "code-review", "automated")
TITLE = "🔴 Code Review Critical Findings"


def log(msg: str) -> None:
    print(f"[code-review-issue] {msg}", flush=True)


def run_gh(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
        input=stdin,
    )


def ensure_labels() -> None:
    for lbl in (LABEL, *EXTRA_LABELS):
        result = run_gh(["label", "create", lbl, "--force"])
        log(f"label={lbl} rc={result.returncode}")


def find_open_issue() -> dict[str, Any] | None:
    result = run_gh(
        [
            "issue", "list",
            "--label", LABEL,
            "--state", "open",
            "--json", "number,title,body",
            "--limit", "1",
        ]
    )
    if result.returncode != 0:
        log(f"list_failed rc={result.returncode} stderr={result.stderr.strip()}")
        return None
    try:
        issues = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
    return issues[0] if issues else None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _issue_fields(issue: Any) -> dict[str, str]:
    if isinstance(issue, dict):
        msg = (
            issue.get('msg')
            or issue.get('message')
            or issue.get('issue')
            or issue.get('description')
            or str(issue)
        )
        return {
            'dim': issue.get('dim') or issue.get('category') or 'critical',
            'line': str(issue.get('line', '')),
            'file': issue.get('file', ''),
            'msg': msg,
        }
    return {'dim': 'critical', 'line': '', 'file': '', 'msg': str(issue)}


def format_body(critical: list[dict], warnings: list[dict], run_id: str) -> str:
    now = datetime.now(UTC).isoformat()

    critical_md: list[str] = []
    for i, c in enumerate(critical, 1):
        loc_parts = []
        if c['file']:
            loc_parts.append(f"`{c['file']}`")
        if c['line']:
            loc_parts.append(f"line {c['line']}")
        loc = " ".join(loc_parts) or "N/A"
        critical_md.append(f"{i}. **[{c['dim'].upper()}]** {c['msg']} (at {loc})")

    MAX_WARNINGS = 5
    shown = warnings[:MAX_WARNINGS]
    omitted = len(warnings) - len(shown)
    warnings_md = "\n".join(f"- {w['msg']}" for w in shown) if shown else "None"
    if omitted > 0:
        warnings_md += f"\n- _…and {omitted} more warning(s) not shown_"

    return (
        f"**Pipeline Stage:** code-review\n"
        f"**Status:** FAIL — {len(critical)} critical issue(s) found\n"
        f"**Last checked:** {now}\n\n"
        f"## Critical Issues\n"
        f"{chr(10).join(critical_md)}\n\n"
        f"## Warnings\n"
        f"{warnings_md}\n\n"
        f"_See pipeline run: {run_id}_"
    )


def create_or_update(body: str) -> int:
    existing = find_open_issue()
    if existing:
        number = existing["number"]
        log(f"updating_existing_issue=#{number}")
        # Use --body-file - so a long body doesn't hit ARG_MAX via shell args.
        result = run_gh(["issue", "edit", str(number), "--body-file", "-"], stdin=body)
        if result.returncode != 0:
            log(f"edit_failed rc={result.returncode} stderr={result.stderr.strip()}")
            return 1
        log(f"issue_updated=#{number}")
        return 0

    log("creating_new_issue")
    cmd = ["issue", "create", "--title", TITLE, "--body-file", "-"]
    for lbl in (LABEL, *EXTRA_LABELS):
        cmd += ["--label", lbl]
    result = run_gh(cmd, stdin=body)
    if result.returncode != 0:
        log(f"create_failed rc={result.returncode} stderr={result.stderr.strip()}")
        return 1
    log(f"issue_created url={result.stdout.strip()}")
    return 0


def close_resolved() -> int:
    existing = find_open_issue()
    if not existing:
        log("no_open_issue_to_close")
        return 0
    number = existing["number"]
    log(f"closing_resolved_issue=#{number}")
    result = run_gh(
        [
            "issue", "close", str(number),
            "--comment", "Code-review critical findings no longer detected — closing automatically.",
        ]
    )
    if result.returncode != 0:
        log(f"close_failed rc={result.returncode} stderr={result.stderr.strip()}")
        return 1
    return 0


def main() -> int:
    path = os.environ.get('ARTIFACT_PATH', 'artifacts/code-review-result.json')
    log(f"artifact_path={path}")
    if not os.path.exists(path):
        log("missing_artifact — nothing to do")
        return 0
    log(f"artifact_bytes={os.path.getsize(path)}")

    with open(path) as f:
        data = json.load(f)

    status = data.get('status') or ('fail' if data.get('verdict') == 'fail' else '')
    llm_parsed = data.get('details', {}).get('llm_parsed', {})
    critical = [_issue_fields(c) for c in _as_list(llm_parsed.get('critical') or data.get('critical_issues'))]
    warnings = [_issue_fields(w) for w in _as_list(llm_parsed.get('warnings') or data.get('suggestions'))]
    log(f"status={status} critical={len(critical)} warnings={len(warnings)}")

    ensure_labels()

    if status == 'fail' and critical:
        run_id = os.environ.get('GITHUB_RUN_ID', 'N/A')
        return create_or_update(format_body(critical, warnings, run_id))

    return close_resolved()


if __name__ == "__main__":
    sys.exit(main())
