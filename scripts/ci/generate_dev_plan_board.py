#!/usr/bin/env python3
"""Author a dev-plan board document for a `ready` GitHub issue.

Called from `validate_open_issues.py` after Claude returns verdict=ready. The
function loads `docs/dev-plan/_template-medium.md` as the format contract and
asks Claude to produce a populated board for the issue. The result is written
to `docs/dev-plan/issues/<N>-<slug>.md`, committed, and pushed.

Side effects (gated by env vars so test runs are non-destructive):

  DEV_PLAN_DRY_RUN=1     — write the board to /tmp instead of docs/dev-plan,
                           skip the git commit + push.
  DEV_PLAN_NO_PUSH=1     — write and commit, but don't push.

When neither is set, the script writes to disk, commits with a deterministic
message, and pushes to `origin/master`. The caller (the monitor-issues
workflow) is responsible for providing a checkout with a writeable token.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEV_PLAN_ROOT = Path("docs/dev-plan")
TEMPLATE_MEDIUM = DEV_PLAN_ROOT / "_template-medium.md"
ISSUES_DIR = DEV_PLAN_ROOT / "issues"
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
# Max chars in the slug component of the filename. Keeps paths reasonable
# when an issue title is very long.
SLUG_MAX_LEN = 60


def log(msg: str) -> None:
    print(f"[dev-plan-gen] {msg}", flush=True)


@dataclass(frozen=True)
class GeneratedBoard:
    issue_number: int
    path: Path
    committed: bool
    pushed: bool


def slugify(text: str) -> str:
    s = SLUG_PATTERN.sub("-", (text or "").lower()).strip("-")
    return s[:SLUG_MAX_LEN] or "untitled"


def board_path_for(issue_number: int, title: str) -> Path:
    return ISSUES_DIR / f"{issue_number:04d}-{slugify(title)}.md"


def board_already_exists(issue_number: int) -> Path | None:
    """Return the existing board path for an issue if one is already on disk.

    Match on the `{issue_number:04d}-` prefix so slug changes (issue
    title edits) don't produce a second board file.
    """
    if not ISSUES_DIR.exists():
        return None
    prefix = f"{issue_number:04d}-"
    for p in ISSUES_DIR.iterdir():
        if p.is_file() and p.name.startswith(prefix) and p.suffix == ".md":
            return p
    return None


def load_template() -> str:
    if not TEMPLATE_MEDIUM.exists():
        raise FileNotFoundError(f"template not found: {TEMPLATE_MEDIUM}")
    return TEMPLATE_MEDIUM.read_text(encoding="utf-8")


def build_prompt(issue: dict[str, Any], template_text: str, board_relpath: str) -> str:
    title = issue.get("title") or "(no title)"
    body = (issue.get("body") or "(no body)").strip()
    number = issue.get("number")
    return f"""You are authoring a dev-plan board document for GitHub issue #{number} in this repo.

The document MUST follow EXACTLY the structure of `docs/dev-plan/_template-medium.md`. The template is reproduced verbatim between the markers below. Treat every section heading, the metadata table, and the §1-§8 outline as MANDATORY. Section headings (e.g. "## 1. 目标与背景", "### 1.1 为什么做") and the metadata table format are part of the contract — do NOT translate them, do NOT renumber them.

Constraints you MUST honour (these come from `docs/dev-plan/README.md` §2):
- Delete EVERY `<!-- ... -->` comment from the template before emitting.
- Fill EVERY section. If you genuinely have no information for a sub-section, write `TBD - 待补充：<具体什么内容>` instead of leaving it blank.
- Section headings stay in Chinese. The PROSE inside each section should match the language of the issue body — if the issue body is English, write the section content in English; if Chinese, write it in Chinese.
- Code references use the form ``[`path`](../../path) L{{start}}-L{{end}}`` and include a 5-15 line code block. If the repository has no existing code for this issue (greenfield), write `N/A — 新建模块` in §2.1.
- Acceptance criteria in §1.4 must be numeric / verifiable, not vague.
- §3 "涉及文件清单" must clearly separate `要改` (modify existing) from `要建` (create new) — both lists may be empty but the headings must be present.
- §5 "实施步骤" must be machine-actionable: each step is either a shell command, a code diff, or "在 `foo.py` 第 N 行后插入 X". No "optimize the foo module" wording.
- §6 "验证" gives exact commands AND expected output (e.g. `pytest tests/unit/test_x.py -v` → `3 passed`).
- §7 "测试用例" lists at least 3 cases: 1 happy path + 1 boundary + 1 error.

Project context you may use without further investigation (from this repo's CLAUDE.md):
- Stack: FastAPI + SQLAlchemy 2.x async + PostgreSQL (asyncpg).
- Multi-tenant: every SQL must `WHERE tenant_id = :tenant_id`.
- Service layer returns ORM objects + raises AppException subclasses; routers serialize.
- Tests split into `tests/unit/` (mock DB) and `tests/integration/` (real Postgres).
- Lint = ruff only.

The board will be written to `{board_relpath}`. Relative paths in the document should be computed against that location (so `../../src/...` reaches the source tree).

----- TEMPLATE (verbatim, structural contract) -----
{template_text}
----- END TEMPLATE -----

----- ISSUE -----
#{number}  {title}

{body}
----- END ISSUE -----

Respond with the COMPLETE board document, starting at the `# ` (H1) title line and ending at the last line of §8. No prose before or after. No markdown fence around the whole document. No `<!-- ... -->` comments anywhere in your output.

CRITICAL: Do NOT attempt to create or write any files yourself. Do NOT call any file/edit/write tools. Your one and only output is the markdown document, printed to stdout. The orchestrator script will persist it; trying to write it yourself will be blocked and produce a broken result.
"""


def call_claude_for_board(prompt: str) -> tuple[str, str]:
    """Run claude headlessly and return (board_markdown, error).

    Reuses the same CLI shape used by validate_open_issues.call_claude but
    with a longer timeout — board generation is a longer task than triage.
    """
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout = int(os.environ.get("DEV_PLAN_CLAUDE_TIMEOUT_SECONDS", "600"))
    cmd = [
        "claude", "-p",
        "--model", model,
        "--max-turns", "12",
        "--output-format", "text",
    ]
    try:
        result = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "", "claude_timed_out"
    except OSError as e:
        return "", f"claude_not_runnable: {e}"

    if result.returncode != 0:
        return "", f"claude_rc={result.returncode} stderr={(result.stderr or '').strip()[-200:]!r}"
    out = (result.stdout or "").strip()

    # Strip a fenced wrap if present (```markdown ... ```).
    if out.startswith("```"):
        lines = out.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        out = "\n".join(lines).strip()

    # Claude sometimes prepends a chatty preamble before the document
    # (e.g. "Here is the board:"), especially when its file-write attempt
    # was blocked. Chop everything before the first H1 line — that's the
    # real start of the document per the template.
    if not out.startswith("# "):
        idx = out.find("\n# ")
        if idx != -1:
            out = out[idx + 1 :].strip()

    # Strip a trailing tail-fence on the chopped doc as well (rare but possible).
    if out.endswith("```"):
        out = out.rsplit("\n```", 1)[0].rstrip()

    if not out.startswith("# "):
        return "", f"output_did_not_start_with_h1 head={out[:120]!r}"
    return out, ""


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def commit_and_push(path: Path, issue_number: int, push: bool) -> tuple[bool, bool]:
    """Stage the board, commit, push. Returns (committed, pushed)."""
    add = run_git(["add", str(path)])
    if add.returncode != 0:
        log(f"git_add_failed path={path} rc={add.returncode} stderr={add.stderr.strip()}")
        return False, False

    # If nothing changed (idempotent re-run), don't make an empty commit.
    diff = run_git(["diff", "--cached", "--quiet"])
    if diff.returncode == 0:
        log(f"no_changes_to_commit path={path}")
        return False, False

    msg = f"docs(dev-plan): board for issue #{issue_number}"
    commit = run_git(["commit", "-m", msg])
    if commit.returncode != 0:
        log(f"git_commit_failed rc={commit.returncode} stderr={commit.stderr.strip()}")
        return False, False

    if not push:
        return True, False

    push_r = run_git(["push", "origin", "HEAD:master"])
    if push_r.returncode != 0:
        log(f"git_push_failed rc={push_r.returncode} stderr={push_r.stderr.strip()[:200]}")
        return True, False

    return True, True


def generate_board(issue: dict[str, Any]) -> tuple[GeneratedBoard | None, str]:
    """Author + persist a dev-plan board for an issue.

    Returns (board, "") on success, (None, error) on failure. The caller (the
    validator) should treat failures as non-fatal — the issue is still marked
    ready, we just skip the board.
    """
    number = int(issue["number"])
    title = issue.get("title") or ""

    existing = board_already_exists(number)
    if existing is not None:
        log(f"board_already_exists issue=#{number} path={existing}")
        return GeneratedBoard(number, existing, committed=False, pushed=False), ""

    try:
        template_text = load_template()
    except FileNotFoundError as e:
        return None, str(e)

    dry_run = os.environ.get("DEV_PLAN_DRY_RUN") == "1"
    no_push = os.environ.get("DEV_PLAN_NO_PUSH") == "1"

    target = board_path_for(number, title)
    if dry_run:
        # Write to /tmp/ instead of touching the repo working tree.
        target = Path("/tmp") / target.name

    prompt = build_prompt(issue, template_text, target.as_posix())
    board, err = call_claude_for_board(prompt)
    if err:
        return None, err

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(board if board.endswith("\n") else board + "\n", encoding="utf-8")
    log(f"board_written issue=#{number} path={target} bytes={target.stat().st_size}")

    if dry_run:
        return GeneratedBoard(number, target, committed=False, pushed=False), ""

    committed, pushed = commit_and_push(target, number, push=not no_push)
    return GeneratedBoard(number, target, committed=committed, pushed=pushed), ""


def board_ref_for(board_path: Path) -> str:
    """The canonical `Dev-Plan: docs/dev-plan/...` reference string."""
    # Always emit the in-repo form so dev_plan_context.find_dev_plan_ref()
    # picks it up regardless of where the script ran from.
    rel = board_path.as_posix()
    if "docs/dev-plan/" in rel:
        rel = "docs/dev-plan/" + rel.split("docs/dev-plan/", 1)[1]
    return f"Dev-Plan: {rel}"


if __name__ == "__main__":
    # Allow standalone invocation for smoke testing:
    #   ISSUE_NUMBER=143 python3 scripts/ci/generate_dev_plan_board.py
    import json, sys  # noqa: E401
    n = os.environ.get("ISSUE_NUMBER")
    if not n:
        print("Set ISSUE_NUMBER=<n> and re-run.", file=sys.stderr)
        sys.exit(2)
    r = subprocess.run(
        ["gh", "issue", "view", n, "--json", "number,title,body"],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        print(f"gh failed: {r.stderr}", file=sys.stderr)
        sys.exit(1)
    issue = json.loads(r.stdout)
    board, err = generate_board(issue)
    if err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {board}")
