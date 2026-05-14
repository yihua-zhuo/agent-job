#!/usr/bin/env python3
"""Remove triage labels (`ready`, `needs-clarification`) from all open issues.

Resets the issue-validator's state — after this runs, the next
monitor-issues tick will re-validate every issue from scratch.

Usage:
    python3 scripts/ci/clear_triage_labels.py
    python3 scripts/ci/clear_triage_labels.py --dry-run
    python3 scripts/ci/clear_triage_labels.py --labels ready,needs-clarification,split

Requires `gh` to be installed and authenticated.
"""

import argparse
import json
import subprocess
import sys


DEFAULT_LABELS = ("ready", "needs-clarification")


def log(msg: str) -> None:
    print(f"[clear-labels] {msg}", flush=True)


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def list_open_with_any_label(labels: list[str]) -> list[dict]:
    """Return open issues that carry at least ONE of the given labels.

    gh issue list with multiple `--label` flags uses AND semantics, not OR,
    so we query each label separately and union the results client-side
    (deduping by issue number).
    """
    seen: dict[int, dict] = {}
    for label in labels:
        r = run_gh([
            "issue", "list",
            "--state", "open",
            "--label", label,
            "--json", "number,title,labels",
            "--limit", "500",
        ])
        if r.returncode != 0:
            log(f"list_failed label={label!r} stderr={r.stderr.strip()[:200]}")
            continue
        try:
            chunk = json.loads(r.stdout or "[]")
        except json.JSONDecodeError:
            log(f"json_decode_failed label={label!r}")
            continue
        for issue in chunk:
            seen[int(issue["number"])] = issue
    return list(seen.values())


def labels_on_issue(issue: dict) -> set[str]:
    return {(lbl.get("name") or "") for lbl in (issue.get("labels") or [])}


def remove_labels(number: int, labels_to_remove: list[str], dry_run: bool = False) -> bool:
    """Remove the given labels in one gh call (repeated --remove-label flags)."""
    if dry_run:
        return True
    args = ["issue", "edit", str(number)]
    for lbl in labels_to_remove:
        args.extend(["--remove-label", lbl])
    r = run_gh(args)
    if r.returncode != 0:
        log(f"remove_failed issue=#{number} labels={labels_to_remove} stderr={r.stderr.strip()[:200]}")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strip triage labels (default: ready + needs-clarification) from every open issue.",
    )
    parser.add_argument(
        "--labels",
        default=",".join(DEFAULT_LABELS),
        help=f"Comma-separated label names to strip. Default: {','.join(DEFAULT_LABELS)}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be removed without making any changes.",
    )
    args = parser.parse_args()

    targets = {lbl.strip() for lbl in args.labels.split(",") if lbl.strip()}
    if not targets:
        log("no labels specified")
        return 1

    log(f"target_labels={sorted(targets)} dry_run={args.dry_run}")

    issues = list_open_with_any_label(sorted(targets))
    log(f"open_issues_with_any_target_label={len(issues)}")

    if not issues:
        log("nothing to do")
        return 0

    rows: list[tuple[int, list[str], str, str]] = []
    for issue in issues:
        number = int(issue["number"])
        present = sorted(labels_on_issue(issue) & targets)
        if not present:
            # Shouldn't happen given how we listed them, but be defensive.
            continue
        ok = remove_labels(number, present, dry_run=args.dry_run)
        status = "OK" if ok else "FAIL"
        rows.append((number, present, status, (issue.get("title") or "")[:60]))
        verb = "DRY-RUN" if args.dry_run else ("REMOVED" if ok else "FAILED")
        log(f"{verb} issue=#{number} labels={present}")

    # Summary table
    print()
    print(f"{'ISSUE':>6}  {'LABELS REMOVED':<35}  {'STATUS':<7}  TITLE")
    print("-" * 120)
    for number, labels, status, title in rows:
        print(f"{number:>6}  {', '.join(labels):<35}  {status:<7}  {title}")

    ok_count = sum(1 for r in rows if r[2] == "OK")
    fail_count = sum(1 for r in rows if r[2] == "FAIL")
    print()
    print(
        f"summary: affected={ok_count} failures={fail_count}"
        + (" (dry-run, no changes applied)" if args.dry_run else "")
    )
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
