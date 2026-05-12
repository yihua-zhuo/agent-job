#!/usr/bin/env python3
"""Local CLI: list `ready` issues and dispatch the auto-implement workflow.

Usage:
    python scripts/dev/trigger_implement.py                # interactive picker
    python scripts/dev/trigger_implement.py --issue 273    # skip picker
    python scripts/dev/trigger_implement.py --list         # just list, no dispatch
    python scripts/dev/trigger_implement.py --ref master   # ref the workflow runs on

Auth: reads GH_TOKEN or GITHUB_TOKEN from env. The token needs `repo` scope
(or `actions:write` + `issues:read` on a fine-grained PAT).

Repo: auto-detected from `git remote get-url origin`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any


# Issue titles contain em-dashes etc. — Windows' default cp1252 console mangles them.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


WORKFLOW_FILE = "implement-ready-issues.yml"
LABEL_READY = "ready"
LABEL_WIP = "wip"


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def detect_repo() -> tuple[str, str]:
    r = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        die("not in a git repo or no `origin` remote configured")
    url = r.stdout.strip()
    # Match both https://github.com/owner/repo(.git) and git@github.com:owner/repo(.git)
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        die(f"could not parse owner/repo from origin url: {url}")
    return m.group(1), m.group(2)


def get_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        die("GH_TOKEN (or GITHUB_TOKEN) not set in environment")
    return token


def api(method: str, path: str, token: str, body: dict[str, Any] | None = None) -> tuple[int, bytes]:
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, method=method, data=data)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def list_ready(owner: str, repo: str, token: str) -> list[dict[str, Any]]:
    # Filter server-side: open + labelled ready. Pagination capped at 100 —
    # any healthy backlog stays well under that.
    status, raw = api(
        "GET",
        f"/repos/{owner}/{repo}/issues?state=open&labels={LABEL_READY}&per_page=100",
        token,
    )
    if status != 200:
        die(f"list issues failed: HTTP {status}: {raw.decode('utf-8', 'replace')[:300]}")
    issues = json.loads(raw)
    # /issues includes PRs; exclude them. Also drop anything already claimed.
    out = []
    for i in issues:
        if "pull_request" in i:
            continue
        names = {(lbl.get("name") or "") for lbl in (i.get("labels") or [])}
        if LABEL_WIP in names:
            continue
        out.append(i)
    # Oldest-first to match the workflow's FIFO behavior.
    out.sort(key=lambda i: i["number"])
    return out


def print_table(issues: list[dict[str, Any]]) -> None:
    if not issues:
        print("(no ready issues — nothing to dispatch)")
        return
    width = max(len(str(i["number"])) for i in issues)
    for idx, i in enumerate(issues, start=1):
        num = str(i["number"]).rjust(width)
        title = (i.get("title") or "").strip()
        print(f"  [{idx:>2}] #{num}  {title}")


def pick(issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not issues:
        return None
    while True:
        raw = input("Pick an issue (index or #number, blank to abort): ").strip()
        if not raw:
            return None
        if raw.startswith("#"):
            raw = raw[1:]
        if not raw.isdigit():
            print("  enter a number")
            continue
        n = int(raw)
        # First try as 1-based index, then as raw issue number.
        if 1 <= n <= len(issues):
            return issues[n - 1]
        for i in issues:
            if i["number"] == n:
                return i
        print(f"  no ready issue matches {n}")


def dispatch(owner: str, repo: str, token: str, ref: str, issue_number: int) -> None:
    path = f"/repos/{owner}/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    body = {"ref": ref, "inputs": {"issue_number": str(issue_number)}}
    status, raw = api("POST", path, token, body)
    # GitHub returns 204 No Content on success.
    if status == 204:
        print(f"dispatched: issue #{issue_number} on ref={ref}")
        print(f"  https://github.com/{owner}/{repo}/actions/workflows/{WORKFLOW_FILE}")
        return
    die(f"dispatch failed: HTTP {status}: {raw.decode('utf-8', 'replace')[:300]}")


def main() -> int:
    p = argparse.ArgumentParser(description="Pick a ready issue and trigger the implement workflow.")
    p.add_argument("--issue", type=int, help="Issue number to dispatch (skips the picker).")
    p.add_argument("--ref", default="master", help="Branch the workflow runs on (default: master).")
    p.add_argument("--list", action="store_true", help="List ready issues and exit.")
    p.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    args = p.parse_args()

    owner, repo = detect_repo()
    token = get_token()

    issues = list_ready(owner, repo, token)
    print(f"ready issues in {owner}/{repo}: {len(issues)}")
    print_table(issues)

    if args.list:
        return 0

    if args.issue is not None:
        chosen = next((i for i in issues if i["number"] == args.issue), None)
        if chosen is None:
            # Allow targeting an issue that isn't currently in the listed set
            # (e.g. it's labeled `wip` already, or the local view is stale).
            # The workflow will validate again server-side.
            print(f"warning: #{args.issue} not in current ready-list snapshot; dispatching anyway")
            chosen = {"number": args.issue, "title": "(not in current snapshot)"}
    else:
        chosen = pick(issues)
        if chosen is None:
            print("aborted")
            return 0

    print(f"selected: #{chosen['number']}  {(chosen.get('title') or '').strip()}")
    if not args.yes:
        confirm = input(f"Dispatch '{WORKFLOW_FILE}' for #{chosen['number']} on ref={args.ref}? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("aborted")
            return 0

    dispatch(owner, repo, token, args.ref, chosen["number"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
