#!/usr/bin/env python3
"""Local CLI: list `ready` issues and dispatch the auto-implement workflow.

Usage:
    python scripts/dev/trigger_implement.py                # interactive picker
    python scripts/dev/trigger_implement.py --issue 273    # skip picker
    python scripts/dev/trigger_implement.py --list         # just list, no dispatch
    python scripts/dev/trigger_implement.py --ref master   # ref the workflow runs on

Auth: loads .env, then reads GH_TOKEN, GITHUB_TOKEN, or .GITHUB_TOKEN. The
token needs `repo` scope (or `actions:write` + `issues:read` on a fine-grained
PAT).

Repo: auto-detected from `git remote get-url origin`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    from dotenv import dotenv_values, load_dotenv
except ImportError:  # pragma: no cover - dependency is declared; this keeps --help usable.
    dotenv_values = None
    load_dotenv = None


# Issue titles contain em-dashes etc. — Windows' default cp1252 console mangles them.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


WORKFLOW_FILE = "implement-ready-issues.yml"
LABEL_READY = "ready"
LABEL_WIP = "wip"
DOTENV_TOKEN_KEY = ".GITHUB_TOKEN"


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


def load_env(path: Path | None = None) -> None:
    """Load .env and map the project-specific .GITHUB_TOKEN key.

    python-dotenv can load regular names like GITHUB_TOKEN directly. The
    user's local file uses `.GITHUB_TOKEN`, which is not convenient to export
    from a shell, so map it into GITHUB_TOKEN only when no standard token is
    already present.
    """
    dotenv_path = path or (Path.cwd() / ".env")
    if load_dotenv is not None:
        load_dotenv(dotenv_path, override=False)

    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        return

    token = os.environ.get(DOTENV_TOKEN_KEY)
    if not token and dotenv_values is not None:
        token = (dotenv_values(dotenv_path) or {}).get(DOTENV_TOKEN_KEY)
    if not token:
        token = read_dotenv_key(dotenv_path, DOTENV_TOKEN_KEY)
    if token:
        os.environ["GITHUB_TOKEN"] = token


def read_dotenv_key(path: Path, key: str) -> str | None:
    """Small fallback for environments without python-dotenv installed."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        raw_key, raw_value = stripped.split("=", 1)
        if raw_key.strip() != key:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        return value
    return None


def get_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get(DOTENV_TOKEN_KEY)
    if not token:
        die("GH_TOKEN, GITHUB_TOKEN, or .GITHUB_TOKEN not set in environment/.env")
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
    except urllib.error.URLError as e:
        die(f"GitHub API request failed: {e.reason}")


def list_ready(owner: str, repo: str, token: str) -> list[dict[str, Any]]:
    # Filter server-side: open issues that are ready and not already claimed.
    query = f"repo:{owner}/{repo} is:issue is:open label:{LABEL_READY} -label:{LABEL_WIP}"
    encoded = urllib.parse.urlencode({"q": query, "per_page": "100"})
    status, raw = api(
        "GET",
        f"/search/issues?{encoded}",
        token,
    )
    if status != 200:
        die(f"list issues failed: HTTP {status}: {raw.decode('utf-8', 'replace')[:300]}")
    payload = json.loads(raw)
    out = payload.get("items") or []
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
    load_env()

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
