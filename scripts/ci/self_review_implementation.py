#!/usr/bin/env python3
"""Stage 3 of the auto-implementation pipeline: self-review and fix.

After Stage 2 implements the plan, this step asks Claude to review its own
diff against the project's review rules in ``codereview.md`` and fix any
violations BEFORE the PR is opened. Catching them here keeps the review
cycle short and avoids re-running tests after each reviewer comment.

Uses the same streaming + bypassPermissions pattern as execute_implementation.py.
"""

import os
import select
import subprocess
import sys
import time


def log(msg: str) -> None:
    print(f"[self-review] {msg}", flush=True)


def build_prompt(issue_number: str, plan_path: str) -> str:
    return f"""You are self-reviewing the implementation you just completed for issue #{issue_number}.

The plan you followed is at `{plan_path}`.
The project's review rules are in `codereview.md` at the repo root.

Your task — execute in order:

1. Inspect your own changes:
       git diff --stat origin/master..HEAD
       git diff --stat                              # unstaged
       git diff origin/master..HEAD | head -800
       git diff | head -800                         # unstaged
   Use `head` or `--stat` first if the diff is large; you don't need every
   byte, just enough to find rule violations.

2. Read `codereview.md`. Pay particular attention to:
   - Architecture & Project Structure (rules 1-10)
   - Readability & Maintainability (rules 11-20)
   - Python-Specific Best Practices (rules 21-30)
   - Project-Specific Rules (121+) — especially the transaction-boundary
     rules (121-123) and the integration-tests-must-not-mock rule (124).

3. Identify violations IN YOUR OWN DIFF only. Be ruthless about real rule
   breakages (e.g. `session.commit()` in a service, `MagicMock` under
   `tests/integration/`, missing tenant_id filter, manual `try/except`
   in a router that should rely on the global exception handler).
   Do NOT flag things that already exist in the codebase outside your diff.

4. Apply fixes ONLY to the files you already touched. Rules:
   - Do NOT scope-creep into unrelated code or files.
   - Do NOT modify the plan file at `{plan_path}`.
   - Do NOT make purely stylistic changes that don't violate a rule.
   - Do NOT touch `.github/workflows/` or `scripts/ci/`.

5. If you made any fixes, re-run the full validation suite:
       PYTHONPATH=src ruff check src/
       PYTHONPATH=src pytest tests/unit/ -v
       DATABASE_URL=postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db PYTHONPATH=src pytest tests/integration/ -v
   All three must be green. If a fix breaks tests, refine the fix; don't
   revert silently.

6. Stop when: no more rule violations remain AND all three checks are green.
   Print a short summary of what you changed (or "no issues found, no
   changes made" if the diff was already clean).

7. Do NOT run `git commit`, `git push`, `git add`, `git stash`, `git reset`,
   or modify `.git/`. Leave all edits as unstaged changes — the workflow
   stages and commits them after you finish.

If you find no violations, say so explicitly and stop without making any
changes. Don't invent issues to fix.
"""


def stream_claude(cmd: list[str], prompt: str, timeout: int) -> int | None:
    """Run Claude with prompt on stdin; stream stdout/stderr live (same
    pattern as execute_implementation.py)."""
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except BrokenPipeError:
        pass

    stdout_fd = proc.stdout.fileno()
    stderr_fd = proc.stderr.fileno()
    streams = {
        stdout_fd: (proc.stdout, sys.stdout),
        stderr_fd: (proc.stderr, sys.stderr),
    }
    open_fds = {stdout_fd, stderr_fd}
    start = time.monotonic()

    while open_fds:
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            proc.kill()
            return None
        ready, _, _ = select.select(list(open_fds), [], [], min(1.0, remaining))
        if not ready:
            if proc.poll() is not None:
                pass
            continue
        for fd in ready:
            stream, out = streams[fd]
            line = stream.readline()
            if not line:
                open_fds.discard(fd)
                continue
            out.write(line)
            out.flush()

    try:
        proc.wait(timeout=max(1, timeout - (time.monotonic() - start)))
    except subprocess.TimeoutExpired:
        proc.kill()
        return None
    return proc.returncode


def main() -> int:
    issue_number = os.environ.get("ISSUE_NUMBER", "")
    plan_path = os.environ.get("PLAN_PATH", "")
    if not issue_number or not plan_path:
        log("missing_env ISSUE_NUMBER or PLAN_PATH")
        return 1

    prompt = build_prompt(issue_number, plan_path)
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "1800"))  # 30 min
    max_turns = os.environ.get("CLAUDE_MAX_TURNS", "100")

    cmd = [
        "claude", "-p",
        "--model", model,
        "--max-turns", max_turns,
        "--output-format", "json",
        # Same rationale as execute_implementation.py: headless -p in CI has
        # no UI for permission prompts, so silent denials cripple the run.
        "--permission-mode", "bypassPermissions",
    ]
    log(f"invoking_claude model={model} max_turns={max_turns} timeout={timeout}s")

    try:
        rc = stream_claude(cmd, prompt, timeout)
    except OSError as e:
        log(f"claude_not_runnable: {e}")
        return 1

    if rc is None:
        log("claude_timed_out")
        return 1
    if rc != 0:
        log(f"claude_failed rc={rc}")
        return rc
    log("claude_finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
