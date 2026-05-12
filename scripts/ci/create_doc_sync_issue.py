#!/usr/bin/env python3
"""Create or update a GitHub Issue when the doc-sync check finds drift.

Reads the artifact produced by `run_claude_doc_sync_check.py`. If `status`
is "fail", it (re)uses a single open issue labelled `doc-sync` so the
nightly cron doesn't pile up one issue per day. If `status` is "pass",
any existing open doc-sync issue is closed with a short comment.
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any


LABEL = "doc-sync"
EXTRA_LABELS = ("pipeline", "automated")
TITLE = "📚 Documentation drift detected"


def log(msg: str) -> None:
    print(f"[doc-sync-issue] {msg}", flush=True)


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


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


def format_body(data: dict[str, Any], run_id: str) -> str:
    out_of_sync = data.get("out_of_sync") or []
    checked = data.get("checked_documents") or []
    summary = (data.get("summary") or "").strip()
    now = datetime.now(UTC).isoformat()

    sections = [
        "**Pipeline Stage:** doc-sync",
        f"**Status:** FAIL — {len(out_of_sync)} drift item(s) found",
        f"**Last checked:** {now}",
    ]
    if summary:
        sections.append(f"\n**Summary:** {summary}")

    lines = ["\n## Out-of-sync items\n"]
    for i, item in enumerate(out_of_sync, 1):
        if not isinstance(item, dict):
            lines.append(f"{i}. {item}")
            continue
        doc = item.get("doc_path") or "(unknown)"
        claim = item.get("claim") or ""
        reality = item.get("current_reality") or ""
        suggestion = item.get("suggested_update") or ""
        evidence = item.get("evidence") or []

        lines.append(f"### {i}. `{doc}`")
        if claim:
            lines.append(f"- **Claim:** {claim}")
        if reality:
            lines.append(f"- **Reality:** {reality}")
        if suggestion:
            lines.append(f"- **Suggested update:** {suggestion}")
        if evidence:
            ev_str = ", ".join(f"`{e}`" for e in evidence)
            lines.append(f"- **Evidence:** {ev_str}")
        lines.append("")

    if checked:
        lines.append("## Documents checked")
        lines.extend(f"- `{d}`" for d in checked)

    if run_id and run_id != "N/A":
        lines.append(f"\n_See pipeline run: {run_id}_")

    return "\n".join(sections + lines)


def create_or_update_issue(body: str) -> int:
    existing = find_open_issue()
    if existing:
        number = existing["number"]
        log(f"updating_existing_issue=#{number}")
        result = run_gh(["issue", "edit", str(number), "--body", body])
        if result.returncode != 0:
            log(f"edit_failed rc={result.returncode} stderr={result.stderr.strip()}")
            return 1
        log(f"issue_updated=#{number}")
        return 0

    log("creating_new_issue")
    cmd = ["issue", "create", "--title", TITLE, "--body", body]
    for lbl in (LABEL, *EXTRA_LABELS):
        cmd += ["--label", lbl]
    result = run_gh(cmd)
    if result.returncode != 0:
        log(f"create_failed rc={result.returncode} stderr={result.stderr.strip()}")
        return 1
    log(f"issue_created url={result.stdout.strip()}")
    return 0


def close_stale_issue() -> int:
    existing = find_open_issue()
    if not existing:
        log("no_open_issue_to_close")
        return 0
    number = existing["number"]
    log(f"closing_resolved_issue=#{number}")
    result = run_gh(
        [
            "issue", "close", str(number),
            "--comment", "Documentation drift no longer detected — closing automatically.",
        ]
    )
    if result.returncode != 0:
        log(f"close_failed rc={result.returncode} stderr={result.stderr.strip()}")
        return 1
    return 0


def main() -> int:
    path = os.environ.get("ARTIFACT_PATH", "artifacts/doc-sync-result.json")
    log(f"artifact_path={path}")
    if not os.path.exists(path):
        log("missing_artifact — nothing to do")
        return 0

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    status = data.get("status")
    out_of_sync = data.get("out_of_sync") or []
    log(f"status={status} drift_count={len(out_of_sync)}")

    ensure_labels()

    if status == "fail" and out_of_sync:
        run_id = os.environ.get("GITHUB_RUN_ID", "N/A")
        return create_or_update_issue(format_body(data, run_id))

    return close_stale_issue()


if __name__ == "__main__":
    sys.exit(main())
