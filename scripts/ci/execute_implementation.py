#!/usr/bin/env python3
"""Stage 2 of the auto-implementation pipeline.

Reads the plan written by claim_and_plan_issue.py and invokes Claude Code
with full Bash/Edit/Read/Write tools to implement it. Claude is required
to run unit tests AND integration tests AND ruff before declaring done.

Does NOT commit — the surrounding workflow handles git operations. There
is no separate test gate after this step; Claude owns the test pass, and
PR-time CI (ci.yml) re-verifies independently before merge.
"""

import os
import select
import subprocess
import sys
import time
from pathlib import Path


def log(msg: str) -> None:
    print(f"[execute] {msg}", flush=True)


def build_prompt(issue_number: str, plan_path: str, plan_text: str) -> str:
    return f"""You are implementing GitHub issue #{issue_number} in this repository.

The implementation plan is at `{plan_path}` and reproduced below. Read it carefully
and treat it as the source of truth for scope.

----- PLAN -----
{plan_text}
----- END PLAN -----

Critical rules — follow ALL of them:

1. Implement exactly what the plan describes. If the plan turns out to be wrong
   or incomplete, update the source code as needed — but do NOT modify the
   plan file at `{plan_path}`.

2. Before declaring done, ALL of the following commands must succeed in a clean
   run (exit code 0):
       PYTHONPATH=src ruff check src/
       PYTHONPATH=src pytest tests/unit/ -v
       DATABASE_URL=postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db PYTHONPATH=src pytest tests/integration/ -v

3. If any of those fail after your changes, fix the failure and re-run. Iterate
   until ALL THREE are green. Do not stop on a partial pass.

4. Use the Bash tool to run pytest, ruff, and any shell commands. Use Edit and
   Write to modify files. Use Read to examine code before changing it.

5. Do NOT run `git commit`, `git push`, `git add`, or modify anything under
   `.git/`. The workflow will commit your changes after verifying tests.

6. Do NOT modify `.github/workflows/` files unless the plan explicitly requires it.

7. Do NOT modify the plan file at `{plan_path}`.

8. When all three checks pass and you have nothing more to do, stop and print a
   short summary of the files you changed.

Begin by reading `{plan_path}` and the source files it references.
"""


def stream_claude(cmd: list[str], prompt: str, timeout: int) -> int | None:
    """Run Claude with prompt on stdin, streaming stdout/stderr line-by-line
    so the workflow log shows progress in real time instead of buffering for
    the entire (potentially 40-minute) run.

    Returns the subprocess returncode, or None if the wall-clock timeout was
    hit. Caller handles OSError (e.g. binary missing) outside.
    """
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # line-buffered
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
                # Process exited; drain any remaining buffered data on the
                # next iteration (open_fds shrinks only on EOF reads).
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

    plan_file = Path(plan_path)
    if not plan_file.exists():
        log(f"missing_plan path={plan_path}")
        return 1
    plan_text = plan_file.read_text(encoding="utf-8")

    prompt = build_prompt(issue_number, plan_path, plan_text)
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "2400"))  # 40 min default
    max_turns = os.environ.get("CLAUDE_MAX_TURNS", "150")
    cmd = [
        "claude", "-p",
        "--model", model,
        "--max-turns", max_turns,
        "--output-format", "json",
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
