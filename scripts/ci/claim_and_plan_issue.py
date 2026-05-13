#!/usr/bin/env python3
"""Stage 1 of the auto-implementation pipeline.

Picks one open issue labelled `ready` (and not `wip`), claims it by adding
the `wip` label, then asks Claude to write a Markdown implementation plan
to `.plans/issue-<N>.md`. Outputs issue_number, plan_path, branch via
GITHUB_OUTPUT so the surrounding workflow can drive subsequent steps.

Does NOT modify source code. Stage 2 (execute_implementation.py) reads
the plan file and does the actual work.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


LABEL_READY = "ready"
LABEL_WIP = "wip"


def log(msg: str) -> None:
    print(f"[claim-and-plan] {msg}", flush=True)


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def ensure_label() -> None:
    run_gh(["label", "create", LABEL_WIP, "--force"])


def list_ready_issues() -> list[dict[str, Any]]:
    # `gh issue list` returns newest-first; we pick the oldest in main(), so
    # the limit must be large enough that older ready issues don't starve
    # behind newer ones. gh paginates internally up to --limit; 1000 covers
    # any realistic backlog.
    r = run_gh(
        [
            "issue", "list",
            "--state", "open",
            "--label", LABEL_READY,
            "--json", "number,title,body,labels",
            "--limit", "1000",
        ]
    )
    if r.returncode != 0:
        log(f"list_failed rc={r.returncode} stderr={r.stderr.strip()}")
        return []
    try:
        return json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []


def fetch_issue(number: int) -> dict[str, Any] | None:
    r = run_gh(
        [
            "issue", "view", str(number),
            "--json", "number,title,body,labels,state",
        ]
    )
    if r.returncode != 0:
        log(f"fetch_failed issue=#{number} stderr={r.stderr.strip()}")
        return None
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None


def has_label(issue: dict[str, Any], name: str) -> bool:
    return any((lbl.get("name") or "") == name for lbl in (issue.get("labels") or []))


def claim_issue(number: int) -> bool:
    r = run_gh(["issue", "edit", str(number), "--add-label", LABEL_WIP])
    if r.returncode != 0:
        log(f"claim_failed issue=#{number} stderr={r.stderr.strip()}")
        return False
    log(f"claimed issue=#{number}")
    return True


def release_claim(number: int) -> None:
    run_gh(["issue", "edit", str(number), "--remove-label", LABEL_WIP])


def strip_md_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def call_claude_for_plan(issue: dict[str, Any]) -> tuple[str | None, str]:
    title = issue.get("title") or ""
    body = (issue.get("body") or "").strip()
    number = issue["number"]

    prompt = f"""You are writing an implementation plan for GitHub issue #{number}.

Title: {title}

Body:
{body}

Read whatever files you need from this repository to ground the plan in reality
(file paths, function names, existing patterns). Then return ONLY the Markdown
implementation plan — no JSON, no code fence wrapping, no commentary.

Use this structure exactly:

# Implementation Plan — Issue #{number}

## Goal
<one short paragraph stating what is being changed and why>

## Affected Files
- `path/to/file.py` — <what changes>
- `path/to/test.py` — <what changes>

## Implementation Steps
1. <concrete action-oriented step>
2. <concrete action-oriented step>

## Test Plan
- Unit tests in `tests/unit/`: <files to add/modify and what they cover>
- Integration tests in `tests/integration/`: <files to add/modify and what they cover>

## Acceptance Criteria
- <testable condition>
- <testable condition>

## Risks / Open Questions
- <only if there are real risks — otherwise omit this section entirely>

Be specific: real paths, real names. Do NOT modify any files; you are only planning.
"""
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "900"))
    cmd = [
        "claude", "-p",
        "--model", model,
        "--max-turns", "30",
        "--output-format", "json",
        # Same reason as in execute_implementation.py: headless -p defaults
        # to interactive permission prompts, but CI has no terminal — silent
        # denials cripple the run. Stage 1 only needs Read, but the prompt
        # gate applies uniformly, so bypass it here too.
        "--permission-mode", "bypassPermissions",
    ]
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "claude_timed_out"
    except OSError as e:
        return None, f"claude_not_runnable: {e}"

    if r.returncode != 0:
        return None, f"claude_rc={r.returncode} stderr={(r.stderr or '').strip()[:200]}"

    try:
        wrapper = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        # No wrapper — assume stdout is the plain plan
        return (r.stdout or "").strip() or None, ""

    if isinstance(wrapper, dict):
        result = wrapper.get("result")
        if isinstance(result, str) and result.strip():
            return result.strip(), ""
        msg = wrapper.get("message")
        if isinstance(msg, dict):
            for c in (msg.get("content") or []):
                if isinstance(c, dict) and isinstance(c.get("text"), str) and c["text"].strip():
                    return c["text"].strip(), ""

    return None, "no_plan_content_in_wrapper"


def write_outputs(**kwargs: str) -> None:
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        log("GITHUB_OUTPUT not set; outputs not written")
        return
    with open(out_path, "a", encoding="utf-8") as f:
        for k, v in kwargs.items():
            f.write(f"{k}={v}\n")


def select_issue() -> dict[str, Any] | None:
    # workflow_dispatch can target a specific issue via ISSUE_NUMBER. Validate
    # it's open, ready, and not already claimed before we proceed.
    targeted = (os.environ.get("ISSUE_NUMBER") or "").strip()
    if targeted:
        try:
            n = int(targeted)
        except ValueError:
            log(f"invalid_issue_number env_value={targeted!r}")
            return None
        issue = fetch_issue(n)
        if not issue:
            return None
        if (issue.get("state") or "").lower() != "open":
            log(f"targeted_issue_not_open issue=#{n} state={issue.get('state')!r}")
            return None
        if not has_label(issue, LABEL_READY):
            log(f"targeted_issue_not_ready issue=#{n}")
            return None
        if has_label(issue, LABEL_WIP):
            log(f"targeted_issue_already_wip issue=#{n}")
            return None
        log(f"selected_targeted issue=#{n}")
        return issue

    issues = list_ready_issues()
    log(f"ready_issues_total={len(issues)}")

    candidates = [i for i in issues if not has_label(i, LABEL_WIP)]
    log(f"candidates_after_filter={len(candidates)}")

    if not candidates:
        log("nothing_to_do")
        return None

    # gh issue list default sort is newest-first. Process oldest first (FIFO)
    # so issues don't starve waiting for a slot.
    return candidates[-1]


def main() -> int:
    ensure_label()

    issue = select_issue()
    if issue is None:
        write_outputs(issue_number="", plan_path="", branch="")
        return 0

    number = issue["number"]
    title = issue.get("title") or ""
    log(f"selected issue=#{number} title={title!r}")

    if not claim_issue(number):
        write_outputs(issue_number="", plan_path="", branch="")
        return 0

    plan, err = call_claude_for_plan(issue)
    if err or not plan:
        log(f"plan_failed issue=#{number} err={err or 'empty_plan'}")
        release_claim(number)
        write_outputs(issue_number="", plan_path="", branch="")
        return 0

    plan = strip_md_fence(plan)
    Path(".plans").mkdir(exist_ok=True)
    plan_path = f".plans/issue-{number}.md"
    Path(plan_path).write_text(plan.rstrip() + "\n", encoding="utf-8")
    log(f"plan_written path={plan_path} bytes={len(plan)}")

    branch = f"auto/issue-{number}"
    write_outputs(issue_number=str(number), plan_path=plan_path, branch=branch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
