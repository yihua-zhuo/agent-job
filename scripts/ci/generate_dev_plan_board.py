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
# Legacy flat folder — pre-categories. New boards never land here, but
# board_already_exists() still scans it so older boards aren't re-generated.
LEGACY_ISSUES_DIR = DEV_PLAN_ROOT / "issues"
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
# Max chars in the slug component of the filename. Keeps paths reasonable
# when an issue title is very long.
SLUG_MAX_LEN = 60

# (code, short description used in the classifier prompt). Kept in sync with
# docs/dev-plan/README.md §1.2. Adding a category here without also creating
# the matching folder + README row will produce boards in a directory that
# verify-links can't find.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("00-foundations", "Database connection, auth middleware, Alembic migrations, base models, response envelopes"),
    ("10-customers",   "CustomerModel, contacts, segmentation, customer tags, CRM master objects"),
    ("20-sales",       "Opportunity, Pipeline, Stage, Kanban backend, Deal, Sales activity"),
    ("30-tickets",     "Ticket, SLA, Escalation, support conversations"),
    ("40-campaigns",   "Campaign, Notification, Email/SMS delivery, templates"),
    ("50-automation",  "AutomationRule, triggers, execution engine, rule evaluation, workflows"),
    ("60-analytics",   "ChurnPrediction, RFM, reports, BI, prediction models, KPI dashboards"),
    ("70-platform",    "Import/Export, RBAC, User mgmt, Settings, Audit log"),
    ("90-frontend",    "Vue/React components, drag-and-drop, routing, state mgmt, page layout"),
    ("99-misc",        "Fallback when no other category clearly fits"),
)
FALLBACK_CATEGORY = "99-misc"
VALID_CATEGORY_CODES = frozenset(code for code, _ in CATEGORIES)


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


def board_path_for(issue_number: int, title: str, category: str) -> Path:
    return DEV_PLAN_ROOT / category / f"{issue_number:04d}-{slugify(title)}.md"


def board_already_exists(issue_number: int) -> Path | None:
    """Return the existing board path for an issue if one is already on disk.

    Searches every category folder under docs/dev-plan/ plus the legacy
    `issues/` directory (pre-categories). Match on the `{NNNN}-` prefix so
    slug changes (issue title edits) don't produce a second board file.
    """
    if not DEV_PLAN_ROOT.exists():
        return None
    prefix = f"{issue_number:04d}-"
    # Each category lives in its own directory; underscore-prefixed entries
    # (`_template-*.md`, `_verify-links.sh`) are infrastructure files.
    for child in DEV_PLAN_ROOT.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        for p in child.iterdir():
            if p.is_file() and p.name.startswith(prefix) and p.suffix == ".md":
                return p
    return None


def classify_issue(issue: dict[str, Any]) -> str:
    """Return a category code from `CATEGORIES` for the issue.

    A separate, cheap Claude call. Failing softly to `99-misc` is intentional:
    a board in 99-misc is better than no board at all, and a human can move
    it to the right folder later.
    """
    title = issue.get("title") or "(no title)"
    body = (issue.get("body") or "").strip()
    labels = [
        (lbl.get("name") or "") for lbl in (issue.get("labels") or [])
        if isinstance(lbl, dict)
    ]
    labels_block = ", ".join(l for l in labels if l) or "(none)"

    category_lines = "\n".join(f"- `{code}` — {desc}" for code, desc in CATEGORIES)
    prompt = f"""Classify this GitHub issue into ONE category for the dev-plan documentation tree.

Categories (pick exactly one code):
{category_lines}

Issue title: {title}
Issue labels: {labels_block}

Issue body:
{body[:4000]}

Respond with the category code only, on a single line, no quotes, no prose, no markdown fence. Example: `20-sales`. If genuinely no category fits, respond `{FALLBACK_CATEGORY}`."""

    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout = int(os.environ.get("DEV_PLAN_CLASSIFY_TIMEOUT_SECONDS", "120"))
    cmd = ["claude", "-p", "--model", model, "--max-turns", "1", "--output-format", "text"]
    try:
        result = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            check=False, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        log(f"classify_failed err={type(e).__name__}: {e} — falling back to {FALLBACK_CATEGORY}")
        return FALLBACK_CATEGORY

    if result.returncode != 0:
        log(f"classify_rc_nonzero rc={result.returncode} stdout={(result.stdout or '').strip()[:200]!r} — falling back to {FALLBACK_CATEGORY}")
        return FALLBACK_CATEGORY

    raw = (result.stdout or "").strip()
    # Claude may wrap the code in backticks or add an explanatory clause —
    # extract the first token that matches a known category code.
    for token in re.split(r"[\s`,]+", raw):
        token = token.strip().strip("`")
        if token in VALID_CATEGORY_CODES:
            return token
    log(f"classify_output_unrecognized raw={raw[:120]!r} — falling back to {FALLBACK_CATEGORY}")
    return FALLBACK_CATEGORY


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
- Code references use the form ``[`path`](../../path) L{{start}}-L{{end}}`` and include a 5-15 line code block ONLY when you are certain the path and line range exist (see anti-hallucination rules below). If the repository has no existing code for this issue (greenfield), write `N/A — 新建模块` in §2.1.
- Acceptance criteria in §1.4 must be numeric / verifiable, not vague.
- §3 "目标产物" must clearly separate `要改` (modify existing) from `要建` (create new) — both lists may be empty but the headings must be present.
- §5 "实施步骤" must be machine-actionable: each step is either a shell command, a code diff, or "在 `foo.py` 第 N 行后插入 X". No "optimize the foo module" wording.
- §6 "验收" gives exact commands AND expected output (e.g. `pytest tests/unit/test_x.py -v` → `3 passed`).

ANTI-HALLUCINATION RULES (the previous prompt didn't enforce these and the
output was full of invented refs — pay close attention):
- You do NOT have file-system access. You CANNOT read this repo's source.
- Do NOT invent file paths, line numbers, function names, alembic migration
  revision ids (`abc123def456` style hex), git commits, GitHub issue numbers
  other than the parent issue being processed, or sibling dev-plan boards.
- When you need to reference an existing file you can't verify, write:
    `TBD - 待验证：<grep-friendly hint, e.g. "src/db/models/<似乎叫 activity 的文件> L? — 现有 activity 表 schema">`
  instead of fabricating a plausible-looking citation.
- Do NOT emit URLs like `https://github.com/.../issues/N` with literal `...`.
  If you don't know the owner/repo, just write `#N` and let GitHub render the link.
- Do NOT invent dependency boards. Only reference sibling boards if you can
  derive them from the issue body itself (e.g. "Depends on #N" lines).

PROJECT-SPECIFIC LINTS for this CRM repo (FastAPI + SQLAlchemy 2.x async + PostgreSQL):
- This repo's `PYTHONPATH=src`. Imports MUST be `from db.models...`,
  `from services...`, `from api.routers...`. NEVER `from src.db.models...`.
- SQLAlchemy: do NOT name a column `metadata` on a Base subclass — it
  collides with `Base.metadata` (the MetaData object) and crashes at class
  definition. Use `event_metadata`, `payload`, `attrs`, `meta`, etc.
- Multi-tenant: every SQL filter must include `tenant_id`. Service `__init__`
  takes `session: AsyncSession` with NO default.
- Service returns ORM objects + raises AppException subclasses; routers
  serialize via `.to_dict()`. NEVER call `.to_dict()` in services.
- Routers inject session via `session: AsyncSession = Depends(get_db)`.
  NEVER use `async with get_db() as session:`.
- Tests split into `tests/unit/` (mock DB, fast) and `tests/integration/`
  (real Postgres via docker compose). Each unit test file defines its own
  `mock_db_session` fixture using helpers from `tests/unit/conftest.py`.
- Lint = `ruff` only. NEVER recommend flake8 / pylint / black / isort.
- Alembic autogen tends to emit `sa.JSON()` for what should be `sa.JSONB()`
  and to drop `timezone=True` on DateTime columns. Note this in §4.4 「已知坑」
  whenever the issue touches a migration.

ALSO — about the template itself:
- The template's metadata table has rows for `Issue` (GH issue number) and
  `分类` (category code from this repo's docs/dev-plan/README.md §1.2). Do
  NOT add a `周次` (W{{n}}.{{m}}) row — that was a leftover from a sibling
  repo and does not apply here.
- §8 does NOT include Slack notifications or `script/testnet/*` paths. The
  template's §8 has the correct CRM-flavoured commands; follow it verbatim.
- §6 verification is `pytest` + `ruff` + `alembic`. Do NOT add `forge test`,
  `curl /healthz`, Prometheus, or Grafana checks unless they actually apply.

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
        # Capture BOTH streams. claude-cli sometimes writes its diagnostic to
        # stdout (auth errors, quota / 429s) and leaves stderr empty, so a
        # stderr-only log shows `stderr=''` and looks like a mystery.
        stderr_tail = (result.stderr or "").strip()[-300:]
        stdout_tail = (result.stdout or "").strip()[-300:]
        return "", f"claude_rc={result.returncode} stderr={stderr_tail!r} stdout={stdout_tail!r}"
    out = (result.stdout or "").strip()
    if not out:
        # Exit 0 with empty stdout — rare, but means Claude returned no text.
        # Treat as a generation failure so the caller logs + moves on.
        return "", "claude_returned_empty_stdout"

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


# Per-board commit logic removed — boards are now committed in one batch at
# the end of the monitor tick by commit_pending_boards(). See that function
# for the rationale (one PR per tick instead of one per board).


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

    category = classify_issue(issue)
    log(f"classified issue=#{number} category={category}")

    target = board_path_for(number, title, category)
    if dry_run:
        # Write to /tmp/ instead of touching the repo working tree.
        # Keep the category in the filename so dry-run output is identifiable.
        target = Path("/tmp") / f"{category}__{target.name}"

    prompt = build_prompt(issue, template_text, target.as_posix())
    board, err = call_claude_for_board(prompt)
    if err:
        return None, err

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(board if board.endswith("\n") else board + "\n", encoding="utf-8")
    log(f"board_written issue=#{number} path={target} bytes={target.stat().st_size}")

    # Boards are committed in one batch at end of run by commit_pending_boards.
    # We always report committed=pushed=False from per-board generation now;
    # the final batch step sets the real outcome via its own log line.
    return GeneratedBoard(number, target, committed=False, pushed=False), ""


def commit_pending_boards() -> tuple[int, str, str | None]:
    """Commit + push every uncommitted board under docs/dev-plan/ in ONE go.

    Returns ``(count, status, pr_url)``:
      - count: number of board files included in the commit
      - status: one of "pushed", "committed_no_push", "nothing", "error"
      - pr_url: URL of the opened/updated PR if status == "pushed", else None

    Why end-of-run batching:
      One commit + one PR per monitor tick keeps the PR list manageable
      (vs one PR per generated board), and means a single `git push` race
      can fail at most one tick's worth of work instead of failing each
      board individually.

    Env knobs:
      DEV_PLAN_DRY_RUN=1   skip git entirely
      DEV_PLAN_NO_PUSH=1   commit locally, skip push + PR
    """
    if os.environ.get("DEV_PLAN_DRY_RUN") == "1":
        log("commit_pending_boards skipped reason=dry_run")
        return 0, "nothing", None

    # 1. Find every uncommitted board file under docs/dev-plan/.
    st = run_git(["status", "--porcelain=v1", "--", str(DEV_PLAN_ROOT)])
    if st.returncode != 0:
        log(f"git_status_failed rc={st.returncode} stderr={st.stderr.strip()[:200]}")
        return 0, "error", None
    pending: list[Path] = []
    for line in (st.stdout or "").splitlines():
        # Porcelain format: "XY <path>" — XY is the status code.
        if len(line) < 4:
            continue
        path_str = line[3:].strip()
        # Quoted paths (e.g. with spaces) come back with surrounding quotes.
        if path_str.startswith('"') and path_str.endswith('"'):
            path_str = path_str[1:-1]
        p = Path(path_str)
        if p.suffix == ".md" and DEV_PLAN_ROOT.as_posix() in p.as_posix():
            pending.append(p)
    if not pending:
        log("commit_pending_boards nothing_to_commit")
        return 0, "nothing", None
    log(f"commit_pending_boards count={len(pending)} files={[p.as_posix() for p in pending]}")

    # 2. Snapshot contents — we may need to re-write them after a branch
    # reset (git checkout -B from origin/master would clobber them).
    payload: list[tuple[Path, str]] = []
    for p in pending:
        try:
            payload.append((p, p.read_text(encoding="utf-8")))
        except OSError as e:
            log(f"read_failed path={p} err={e} — skipping")
    if not payload:
        return 0, "error", None

    no_push = os.environ.get("DEV_PLAN_NO_PUSH") == "1"

    # 3. If we're not pushing, commit on whatever HEAD is.
    if no_push:
        if not _stage_and_commit(payload, count_for_msg=len(payload)):
            return len(payload), "error", None
        return len(payload), "committed_no_push", None

    # 4. Otherwise, cut a fresh branch from origin/master and commit there.
    # Per-tick branch name keeps each tick's batch isolated — one PR per
    # tick, no force-with-lease needed for normal traffic.
    fetch = run_git(["fetch", "origin", "master", "--depth=1"])
    if fetch.returncode != 0:
        log(f"git_fetch_failed rc={fetch.returncode} stderr={fetch.stderr.strip()[:200]} — falling back to current branch")
        if not _stage_and_commit(payload, count_for_msg=len(payload)):
            return len(payload), "error", None
        push = run_git(["push", "origin", "HEAD"])
        if push.returncode != 0:
            log(f"git_push_fallback_failed rc={push.returncode} stderr={push.stderr.strip()[:200]}")
            return len(payload), "error", None
        return len(payload), "pushed", None

    ts = subprocess.run(
        ["date", "-u", "+%Y%m%d-%H%M%S"], capture_output=True, text=True, check=False,
    ).stdout.strip() or "batch"
    branch = f"auto/dev-plan-batch-{ts}"

    co = run_git(["checkout", "-B", branch, "origin/master"])
    if co.returncode != 0:
        log(f"git_checkout_failed branch={branch} rc={co.returncode} stderr={co.stderr.strip()[:200]}")
        return len(payload), "error", None

    # 5. Re-materialize the files (the checkout wiped them).
    issue_numbers: list[int] = []
    for p, content in payload:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        # Extract the issue number prefix (NNNN-) for the commit message body.
        try:
            issue_numbers.append(int(p.name.split("-", 1)[0]))
        except ValueError:
            pass

    if not _stage_and_commit(payload, count_for_msg=len(payload), issue_numbers=issue_numbers):
        return len(payload), "error", None

    push = run_git(["push", "-u", "origin", branch])
    if push.returncode != 0:
        log(f"git_push_failed branch={branch} rc={push.returncode} stderr={push.stderr.strip()[:200]}")
        return len(payload), "error", None

    pr_url = _open_batch_pr(branch, issue_numbers)
    return len(payload), "pushed", pr_url


def _stage_and_commit(
    payload: list[tuple[Path, str]],
    count_for_msg: int,
    issue_numbers: list[int] | None = None,
) -> bool:
    add = run_git(["add", "--", str(DEV_PLAN_ROOT)])
    if add.returncode != 0:
        log(f"git_add_failed rc={add.returncode} stderr={add.stderr.strip()[:200]}")
        return False
    diff = run_git(["diff", "--cached", "--quiet"])
    if diff.returncode == 0:
        log("nothing_to_commit_after_stage")
        return False
    nums = sorted(set(issue_numbers or []))
    issue_clause = ", ".join(f"#{n}" for n in nums) if nums else ""
    title = f"docs(dev-plan): generate {count_for_msg} board(s)"
    body = f"Issues: {issue_clause}" if issue_clause else "Auto-generated dev-plan boards."
    commit = run_git(["commit", "-m", title, "-m", body])
    if commit.returncode != 0:
        log(f"git_commit_failed rc={commit.returncode} stderr={commit.stderr.strip()[:200]}")
        return False
    return True


def _open_batch_pr(branch: str, issue_numbers: list[int]) -> str | None:
    nums = sorted(set(issue_numbers))
    n_str = ", ".join(f"#{n}" for n in nums) if nums else "(see commit)"
    title = f"docs(dev-plan): boards for {n_str}" if nums else "docs(dev-plan): board batch"
    # GH PR titles are capped — fall back to a generic title if too long.
    if len(title) > 100:
        title = f"docs(dev-plan): board batch ({len(nums)} issues)"
    body = (
        f"Auto-generated dev-plan boards for: {n_str}.\n\n"
        f"Planning documents only — implementation PRs are opened separately "
        f"by `implement-ready-issues.yml` once each issue is `ready` and unblocked.\n\n"
        f"Format reference: `docs/dev-plan/_template-medium.md`."
    )
    r = subprocess.run(
        ["gh", "pr", "create",
         "--title", title,
         "--body", body,
         "--base", "master",
         "--head", branch,
         "--label", "automated"],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        log(f"pr_create_skipped branch={branch} stderr={r.stderr.strip()[:200]}")
        return None
    url = (r.stdout or "").strip()
    log(f"pr_created branch={branch} url={url}")
    return url


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
