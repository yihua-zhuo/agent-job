#!/usr/bin/env python3
"""Detect and resolve merge conflicts between the PR branch and master.

Attempts ``git merge --no-commit --no-ff origin/master``.

  - If the merge is clean (no conflicts), abort it. The PR didn't need a
    merge to keep moving and we don't want to introduce a gratuitous
    "Merge master into ..." commit when nothing was actually conflicting.
  - If conflicts exist, keep the working tree in conflict state, list the
    conflicted files for Claude, and invoke Claude to resolve each one.
    The workflow's later commit step finalises the merge commit.

On Claude failure or timeout the merge is aborted so the working tree
isn't left half-merged for downstream steps or the next run.

Env vars:
    PR_NUMBER       required  PR number being fixed (for prompt context)
    HEAD_REF        required  PR's head branch (for prompt context)
"""

import os
import select
import subprocess
import sys
import time


def log(msg: str) -> None:
    print(f"[merge-conflicts] {msg}", flush=True)


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def unmerged_files() -> list[str]:
    """Files marked unmerged in the index (i.e. with conflict markers)."""
    r = run_git(["diff", "--name-only", "--diff-filter=U"])
    if r.returncode != 0:
        return []
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


def in_merge_state() -> bool:
    return os.path.exists(os.path.join(".git", "MERGE_HEAD"))


def abort_merge() -> None:
    """Best-effort abort; safe to call even when no merge is in progress."""
    if in_merge_state():
        run_git(["merge", "--abort"])


def stream_claude(cmd: list[str], prompt: str, timeout: int) -> int | None:
    """Same streaming pattern as the other pipeline scripts."""
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


def build_prompt(pr_number: str, head_ref: str, conflicts: list[str]) -> str:
    files_list = "\n".join(f"- `{f}`" for f in conflicts)
    return f"""You are resolving git merge conflicts on PR #{pr_number} (branch `{head_ref}`).

The workflow ran `git merge --no-commit --no-ff origin/master`. The merge
produced conflicts in {len(conflicts)} file(s):

{files_list}

Each conflicted file contains conflict markers:

    <<<<<<< HEAD                ← code from the PR (auto/{head_ref})
    ...
    =======                     ← divider
    ...                         ← code from origin/master
    >>>>>>> origin/master

Your job — execute in order:

1. For each conflicted file:
   a. Read the file end-to-end to see ALL conflict regions and surrounding
      context.
   b. Understand both sides' intent — what the PR is trying to do, what
      master has done.
   c. Produce a merged version that preserves the intent of BOTH sides
      where possible. Remove every conflict marker (`<<<<<<<`, `=======`,
      `>>>>>>>`). The final file must contain valid, runnable code with
      no markers left behind.
   d. If one side genuinely supersedes the other (e.g. master refactored
      a function the PR is modifying), pick the post-refactor structure
      and re-apply the PR's intent on top of it. Don't blindly take "ours"
      or "theirs".

2. After resolving each file, mark it resolved by running:
       git add <file>

3. Once every file is resolved AND staged, run the full validation suite.
   Every command must exit 0:
       PYTHONPATH=src ruff check src/
       PYTHONPATH=src pytest tests/unit/ -v
       DATABASE_URL=postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db PYTHONPATH=src pytest tests/integration/ -v
   If a resolution breaks tests, refine it — don't revert a side wholesale.

4. Do NOT run `git commit`, `git push`, `git merge --abort`, `git reset`,
   or `git stash`. Just edit files, run tests, and `git add` the resolved
   files. The workflow's commit step will finalise the merge commit.

5. Stop when:
   - Every conflict marker is gone.
   - `git diff --name-only --diff-filter=U` is empty.
   - All three checks are green.
   Print a numbered summary listing each file with a one-line description
   of what you did (e.g. "kept master's refactor, re-applied PR's new
   field via the new shape").

If a file is genuinely unmergeable without human judgment (e.g. the two
sides contradict each other and there's no defensible reconciliation),
note it in your summary as "UNRESOLVED: <file> — <reason>" and leave
its markers in place. The workflow will then abort the merge cleanly
rather than commit broken code.
"""


def ensure_full_history() -> bool:
    """Unshallow if needed so the merge-base between HEAD and origin/master is reachable.

    `git merge` fails with "refusing to merge unrelated histories" when it
    can't find a common ancestor. That's usually a symptom of a shallow
    clone (actions/checkout sometimes ends up shallow despite fetch-depth: 0
    interactions with later fetches), not genuinely orphaned branches.
    """
    if os.path.exists(os.path.join(".git", "shallow")):
        log("local_clone_is_shallow — deepening from origin")
        r = run_git(["fetch", "--unshallow", "origin"])
        if r.returncode != 0:
            # --unshallow errors if the clone is already complete; fall back
            # to a max-depth fetch which is always safe.
            r = run_git(["fetch", "origin", "--depth=2147483647"])
            if r.returncode != 0:
                log(f"deepen_failed stderr={r.stderr.strip()[:200]}")
                return False
    return True


def has_shared_history() -> bool:
    """True iff HEAD and origin/master share at least one common ancestor."""
    r = run_git(["merge-base", "HEAD", "origin/master"])
    return r.returncode == 0 and bool(r.stdout.strip())


def main() -> int:
    pr_number = os.environ.get("PR_NUMBER", "").strip()
    head_ref = os.environ.get("HEAD_REF", "").strip()
    if not pr_number or not head_ref:
        log("missing_env PR_NUMBER or HEAD_REF")
        return 1

    log(f"pr=#{pr_number} branch={head_ref}")

    # Refresh master (and the PR branch implicitly via the deepen path).
    if not ensure_full_history():
        log("ensure_full_history failed; aborting merge resolution")
        return 1
    fetch = run_git(["fetch", "origin", "master"])
    if fetch.returncode != 0:
        log(f"fetch_failed stderr={fetch.stderr.strip()[:200]}")
        return 1

    # Guard: if HEAD and master genuinely have no common ancestor, there's
    # nothing this script can sensibly do. That state usually means the PR
    # branch was created in an unusual way (force-pushed root, imported
    # from a separate repo, etc.) — exit 0 with a clear warning so the
    # downstream review-fix step still runs but no merge is attempted.
    if not has_shared_history():
        log(
            "unrelated_histories: HEAD and origin/master share no common "
            "ancestor — skipping merge resolution. The PR is likely orphaned; "
            "investigate manually."
        )
        return 0

    # Attempt the merge without auto-committing or fast-forwarding.
    merge = run_git(["merge", "--no-commit", "--no-ff", "origin/master"])
    conflicts = unmerged_files()

    if merge.returncode == 0 and not conflicts:
        # Clean merge: master integrates without manual work needed. We
        # don't want to gratuitously merge master in if nothing required
        # it — abort and leave the PR untouched.
        log("no_conflicts — aborting clean merge to leave PR state untouched")
        abort_merge()
        return 0

    if not conflicts:
        # Non-conflict failure (uncommitted changes, lost remote, etc).
        log(f"merge_failed_without_conflicts stderr={merge.stderr.strip()[:300]}")
        abort_merge()
        return 1

    log(f"conflicts_found count={len(conflicts)}")
    for f in conflicts:
        log(f"  conflicted: {f}")

    prompt = build_prompt(pr_number, head_ref, conflicts)
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "2400"))  # 40 min
    max_turns = os.environ.get("CLAUDE_MAX_TURNS", "150")
    cmd = [
        "claude", "-p",
        "--model", model,
        "--max-turns", max_turns,
        "--output-format", "json",
        "--permission-mode", "bypassPermissions",
    ]
    log(f"invoking_claude model={model} max_turns={max_turns} timeout={timeout}s")

    try:
        rc = stream_claude(cmd, prompt, timeout)
    except OSError as e:
        log(f"claude_not_runnable: {e}")
        abort_merge()
        return 1

    if rc is None:
        log("claude_timed_out — aborting merge")
        abort_merge()
        return 1
    if rc != 0:
        log(f"claude_failed rc={rc} — aborting merge")
        abort_merge()
        return rc

    remaining = unmerged_files()
    if remaining:
        log(f"conflicts_remain_after_claude={remaining} — aborting merge")
        abort_merge()
        return 1

    log(f"all_conflicts_resolved count={len(conflicts)} — workflow will commit the merge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
