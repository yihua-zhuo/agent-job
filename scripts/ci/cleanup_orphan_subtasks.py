#!/usr/bin/env python3
"""One-shot cleanup: remove subtasks that have no inter-sibling dependency
links, and un-split their parent issues so the validator can re-split them.

Older runs of validate_open_issues.py created subtasks with only a
"Subtask of #N" header in the body — no "Depends on #M" chain between
siblings. That meant subtasks #2..N were never blocked on #1 closing,
breaking the implementation order the splitter prompt asks Claude to produce.

This script:
  1. Lists every issue that says "Subtask of #N" in its body, grouping by N.
  2. For each open parent with the `split` label, checks whether ANY of its
     siblings reference another sibling via "Depends on #M". If yes, the
     chain is intact — leave it alone. If no, the chain is broken.
  3. For broken chains: deletes all OPEN sibling subtasks and removes the
     `split` label from the parent. The parent will be re-evaluated on the
     next validate-open-issues tick and re-split with proper chaining.

Requires `gh` CLI authenticated with a token that has `delete_issue` scope.
"""

import json
import re
import subprocess
import sys
from typing import Any

LABEL_SPLIT = "split"
SUBTASK_OF_PATTERN = re.compile(r"(?i)Subtask of\s*#(\d+)")
DEPENDS_ON_PATTERN = re.compile(r"(?i)(?:depends on|blocked by)\s*:?\s*#(\d+)")


def log(msg: str) -> None:
    print(f"[cleanup-subtasks] {msg}", flush=True)


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    # Force UTF-8 — Windows' default cp1252 chokes on emoji / non-ASCII in
    # issue bodies (gh always emits UTF-8 regardless of console code page).
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def parse_issue_list(result: subprocess.CompletedProcess[str], context: str) -> list[dict[str, Any]]:
    if result.returncode != 0:
        log(f"list_failed context={context} rc={result.returncode} stderr={result.stderr.strip()}")
        return []
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        log(f"json_decode_failed context={context}")
        return []


def list_subtask_issues() -> list[dict[str, Any]]:
    """Issues whose body says they are a subtask of another issue."""
    result = run_gh([
        "issue", "list",
        "--state", "all",
        "--search", 'type:issue "Subtask of" in:body',
        "--json", "number,title,body,labels,state",
        "--limit", "1000",
    ])
    return parse_issue_list(result, "subtasks")


def list_split_parent_issues() -> list[dict[str, Any]]:
    """Open issues carrying the split label."""
    result = run_gh([
        "issue", "list",
        "--state", "open",
        "--search", f"state:open type:issue label:{LABEL_SPLIT}",
        "--json", "number,title,labels,state",
        "--limit", "1000",
    ])
    return parse_issue_list(result, "split_parents")


def parent_of(issue: dict[str, Any]) -> int | None:
    m = SUBTASK_OF_PATTERN.search(issue.get("body") or "")
    return int(m.group(1)) if m else None


def depends_on_in(body: str | None) -> list[int]:
    if not body:
        return []
    return [int(m.group(1)) for m in DEPENDS_ON_PATTERN.finditer(body)]


def delete_issue(number: int) -> bool:
    r = run_gh(["issue", "delete", str(number), "--yes"])
    if r.returncode != 0:
        log(f"delete_failed issue=#{number} stderr={r.stderr.strip()}")
        return False
    return True


def remove_split_label(number: int) -> bool:
    r = run_gh(["issue", "edit", str(number), "--remove-label", LABEL_SPLIT])
    if r.returncode != 0:
        log(f"label_remove_failed issue=#{number} stderr={r.stderr.strip()}")
        return False
    return True


def main() -> int:
    subtask_issues = list_subtask_issues()
    split_parents = list_split_parent_issues()
    log(f"subtask_issues_total={len(subtask_issues)}")

    # Group every "Subtask of #N" issue under its parent — include closed
    # ones so a partly-completed chain (one sibling closed) is still
    # recognised as chained via the remaining open siblings' references.
    children_by_parent: dict[int, list[dict[str, Any]]] = {}
    for issue in subtask_issues:
        parent = parent_of(issue)
        if parent is not None:
            children_by_parent.setdefault(parent, []).append(issue)

    log(f"split_parents_open={len(split_parents)}")

    cleaned = 0
    for parent in split_parents:
        parent_number = parent["number"]
        children = children_by_parent.get(parent_number, [])
        if not children:
            log(f"no_children parent=#{parent_number}")
            continue

        sibling_numbers = {c["number"] for c in children}
        any_chained = any(
            n in sibling_numbers
            for c in children
            for n in depends_on_in(c.get("body"))
        )
        if any_chained:
            log(f"chain_ok parent=#{parent_number} children={sorted(sibling_numbers)}")
            continue

        closed_children = [
            c for c in children if (c.get("state") or "").upper() == "CLOSED"
        ]
        if closed_children:
            log(
                f"skip_closed_children parent=#{parent_number} "
                f"closed={sorted(c['number'] for c in closed_children)}"
            )
            continue

        open_children = [
            c for c in children if (c.get("state") or "").upper() == "OPEN"
        ]
        log(
            f"broken_chain parent=#{parent_number} "
            f"all_children={sorted(sibling_numbers)} "
            f"deleting_open={sorted(c['number'] for c in open_children)}"
        )

        deleted: list[int] = []
        for child in open_children:
            n = child["number"]
            if delete_issue(n):
                deleted.append(n)

        all_deleted = len(deleted) == len(open_children)
        ok = remove_split_label(parent_number) if all_deleted else False
        log(f"cleaned parent=#{parent_number} deleted={deleted} label_removed={ok}")
        if deleted or ok:
            cleaned += 1

    log(f"done cleaned_parents={cleaned}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
