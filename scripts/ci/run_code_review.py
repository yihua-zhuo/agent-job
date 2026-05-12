#!/usr/bin/env python3
"""
run_code_review.py — End-to-end Claude code review pipeline.

Pipeline stages
───────────────
  1. INIT      Validate environment and resolve configuration
  2. FETCH     Fetch remote refs so base/head SHAs are available locally
  3. DIFF      Compute the file-level diff and write it to disk
  4. REVIEW    Run Claude on each changed file (batched)
  5. PERSIST   Write the structured JSON result to disk
  6. COMMENT   Post summary + inline line-level comments to the GitHub PR

Usage (all options are also readable from environment variables):
  python run_code_review.py [OPTIONS]

  --base-ref  BASE    Base branch/SHA  (env: DIFF_BASE_REF,   default: master)
  --head-ref  HEAD    Head branch/SHA  (env: DIFF_HEAD_REF,   default: develop)
  --remote    REMOTE  Git remote name  (env: DIFF_REMOTE,     default: origin)
  --model     MODEL   Claude model     (env: CLAUDE_MODEL,    default: claude-sonnet-4-6)
  --output    PATH    Result JSON path (env: CODE_REVIEW_RESULT_PATH)
  --diff-file PATH    Diff file path   (env: DIFF_FILE,       default: /tmp/pr-diff.txt)
  --batch-size N      Files per batch  (env: REVIEW_BATCH_SIZE, default: 4)
  --dry-run           Print config and diff; skip Claude + GitHub steps
  --skip-comment      Run review but do not post to GitHub
  --pr NUMBER         Override PR number (skips auto-detection)
  --fail-on-critical  Exit with code 1 if any critical issues are found

Required environment variables:
  GITHUB_TOKEN        Personal access token or Actions token with PR write scope

Optional environment variables (used when not on GitHub Actions):
  GITHUB_REPOSITORY   owner/repo  (inferred from git remote if absent)
  GITHUB_HEAD_REF     Branch name (inferred from git if absent)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

# ---------------------------------------------------------------------------
# Import the library module that lives alongside this runner.
# Both files are expected in the same directory.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from claude_code_review import (
    ClaudeRunner,
    FileReview,
    Git,
    GitHubClient,
    ReviewConfig,
    ReviewIssue,
    _format_summary_comment,
    log,
)


# ============================================================================
# ANSI colour helpers (gracefully degraded when stdout is not a tty)
# ============================================================================

_USE_COLOUR = sys.stdout.isatty()

_C = {
    "reset":  "\033[0m"  if _USE_COLOUR else "",
    "bold":   "\033[1m"  if _USE_COLOUR else "",
    "green":  "\033[32m" if _USE_COLOUR else "",
    "yellow": "\033[33m" if _USE_COLOUR else "",
    "red":    "\033[31m" if _USE_COLOUR else "",
    "cyan":   "\033[36m" if _USE_COLOUR else "",
    "dim":    "\033[2m"  if _USE_COLOUR else "",
}


def _banner(stage: int, total: int, label: str) -> None:
    bar   = f"{_C['bold']}{_C['cyan']}[{stage}/{total}]{_C['reset']}"
    title = f"{_C['bold']}{label}{_C['reset']}"
    print(f"\n{bar} {title}", flush=True)
    print(f"{_C['dim']}{'─' * 60}{_C['reset']}", flush=True)


def _ok(msg: str)   -> None: print(f"  {_C['green']}✓{_C['reset']} {msg}", flush=True)
def _warn(msg: str) -> None: print(f"  {_C['yellow']}⚠{_C['reset']} {msg}", flush=True)
def _err(msg: str)  -> None: print(f"  {_C['red']}✗{_C['reset']} {msg}", flush=True)
def _info(msg: str) -> None: print(f"  {_C['dim']}·{_C['reset']} {msg}", flush=True)


def _abort(msg: str, exit_code: int = 1) -> None:
    _err(msg)
    sys.exit(exit_code)


# ============================================================================
# CLI argument parsing
# ============================================================================

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_code_review.py",
        description="End-to-end Claude code review: diff → review → GitHub PR comment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Environment variables override defaults; CLI flags override env vars.

            Exit codes:
              0  success (or no changed files)
              1  configuration error / unrecoverable failure
              2  critical issues found (only with --fail-on-critical)
        """),
    )

    parser.add_argument("--base-ref",      default=None, metavar="REF",
                        help="Base branch or commit SHA (default: $DIFF_BASE_REF or 'master')")
    parser.add_argument("--head-ref",      default=None, metavar="REF",
                        help="Head branch or commit SHA (default: $DIFF_HEAD_REF or 'develop')")
    parser.add_argument("--remote",        default=None, metavar="NAME",
                        help="Git remote name (default: $DIFF_REMOTE or 'origin')")
    parser.add_argument("--model",         default=None, metavar="MODEL",
                        help="Claude model string (default: $CLAUDE_MODEL or 'claude-sonnet-4-6')")
    parser.add_argument("--output",        default=None, metavar="PATH",
                        help="Result JSON output path (default: $CODE_REVIEW_RESULT_PATH)")
    parser.add_argument("--diff-file",     default=None, metavar="PATH",
                        help="Where to write the changed-files list (default: $DIFF_FILE or /tmp/pr-diff.txt)")
    parser.add_argument("--batch-size",    default=None, type=int, metavar="N",
                        help="Number of files per Claude batch (default: $REVIEW_BATCH_SIZE or 4)")
    parser.add_argument("--pr",            default=None, type=int, metavar="NUMBER",
                        help="Override PR number (skips auto-detection)")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Print config and diff; skip Claude review and GitHub steps")
    parser.add_argument("--skip-comment",  action="store_true",
                        help="Run review but do not post anything to GitHub")
    parser.add_argument("--fail-on-critical", action="store_true",
                        help="Exit with code 2 if any critical issues are found")
    return parser.parse_args(argv)


def _build_config(args: argparse.Namespace) -> ReviewConfig:
    """Merge CLI flags on top of the env-var defaults from ReviewConfig.from_env()."""
    base = ReviewConfig.from_env()
    return ReviewConfig(
        base_ref    = args.base_ref    or base.base_ref,
        head_ref    = args.head_ref    or base.head_ref,
        remote      = args.remote      or base.remote,
        model       = args.model       or base.model,
        output_path = args.output      or base.output_path,
        diff_path   = args.diff_file   or base.diff_path,
        batch_size  = args.batch_size  or base.batch_size,
    )


# ============================================================================
# Stage 1 — INIT: validate configuration
# ============================================================================

def stage_init(config: ReviewConfig, args: argparse.Namespace) -> GitHubClient | None:
    """
    Validate required tokens and credentials.
    Returns a GitHubClient when GitHub integration is active, or None for dry-run
    / skip-comment modes.
    """
    _banner(1, 6, "INIT — validating configuration")

    _info(f"base_ref    = {config.base_ref}")
    _info(f"head_ref    = {config.head_ref}")
    _info(f"remote      = {config.remote}")
    _info(f"model       = {config.model}")
    _info(f"output_path = {config.output_path}")
    _info(f"diff_path   = {config.diff_path}")
    _info(f"batch_size  = {config.batch_size}")
    _info(f"dry_run     = {args.dry_run}")
    _info(f"skip_comment= {args.skip_comment}")
    _info(f"pr_override = {args.pr}")

    if args.dry_run or args.skip_comment:
        _warn("GitHub integration disabled (dry-run or skip-comment)")
        return None

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        _warn("GITHUB_TOKEN not set — PR comments will be skipped")
        return None

    git = Git(remote=config.remote)
    repo = os.environ.get("GITHUB_REPOSITORY") or git.infer_github_repo()
    if not repo:
        _warn("Cannot infer GitHub repository — PR comments will be skipped")
        return None

    _ok(f"GitHub repo = {repo}")
    return GitHubClient(token=token, repo=repo)


# ============================================================================
# Stage 2 — FETCH: pull remote refs
# ============================================================================

def stage_fetch(config: ReviewConfig) -> tuple[str, str]:
    """
    Fetch base and head refs from the remote, then return
    (head_sha, base_sha) as full 40-char commit hashes.
    """
    import re
    _banner(2, 6, "FETCH — pulling remote refs")

    git = Git(remote=config.remote)

    refs_to_fetch = [
        r for r in (config.base_ref, config.head_ref)
        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", r)
    ]
    if refs_to_fetch:
        _info(f"git fetch {config.remote} {' '.join(refs_to_fetch)}")
        try:
            git.fetch(*refs_to_fetch)
            _ok("fetch complete")
        except Exception as exc:
            _warn(f"fetch failed ({exc}) — will try with locally cached refs")
    else:
        _info("refs are commit SHAs — skipping fetch")

    head_sha = git.current_head()
    _ok(f"head = {head_sha}")

    resolved_base_ref = git.resolve_revision(config.base_ref)
    base_sha = git.commit_hash(resolved_base_ref)
    _ok(f"base = {base_sha}  ({resolved_base_ref})")

    return head_sha, base_sha


# ============================================================================
# Stage 3 — DIFF: compute changed files and write diff to disk
# ============================================================================

def stage_diff(config: ReviewConfig, head_sha: str, base_sha: str) -> list[str]:
    """
    Run `git diff` between base and head, write the changed-file list to
    config.diff_path, and return the list.
    """
    _banner(3, 6, "DIFF — computing changed files")

    git = Git(remote=config.remote)
    files = git.changed_files(base_sha, head_sha)

    diff_path = Path(config.diff_path)
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text("\n".join(files) + ("\n" if files else ""), encoding="utf-8")

    if files:
        _ok(f"{len(files)} file(s) changed — written to {config.diff_path}")
        for f in files:
            _info(f)
    else:
        _warn("no changed files found")

    return files


# ============================================================================
# Stage 4 — REVIEW: run Claude on each changed file
# ============================================================================

def stage_review(
    config: ReviewConfig,
    files: list[str],
    dry_run: bool,
) -> list[FileReview]:
    """
    Dispatch files to Claude in batches.  Returns one FileReview per file.
    In dry-run mode the Claude invocation is skipped and stub results are returned.
    """
    _banner(4, 6, "REVIEW — running Claude code review")

    if not files:
        _warn("nothing to review")
        return []

    if dry_run:
        _warn("dry-run: skipping Claude invocation")
        return [FileReview(file=f, returncode=None, output="[dry-run]", parsed=None) for f in files]

    runner = ClaudeRunner(model=config.model)
    reviews: list[FileReview] = []
    total_batches = (len(files) + config.batch_size - 1) // config.batch_size

    for batch_idx, start in enumerate(range(0, len(files), config.batch_size), 1):
        batch = files[start: start + config.batch_size]
        _info(f"batch {batch_idx}/{total_batches}: {batch}")
        t0 = time.monotonic()
        batch_reviews = runner.review_batch(batch)
        elapsed = time.monotonic() - t0
        reviews.extend(batch_reviews)

        issues_in_batch = sum(len(fr.issues) for fr in batch_reviews)
        _ok(f"batch {batch_idx} done in {elapsed:.1f}s — {issues_in_batch} issue(s) found")

    total_issues = sum(len(fr.issues) for fr in reviews)
    _ok(f"review complete: {len(reviews)} file(s), {total_issues} total issue(s)")
    return reviews


# ============================================================================
# Stage 5 — PERSIST: aggregate results and write JSON
# ============================================================================

def stage_persist(
    config: ReviewConfig,
    head_sha: str,
    base_sha: str,
    files: list[str],
    reviews: list[FileReview],
) -> tuple[dict[str, Any], list[ReviewIssue], list[ReviewIssue]]:
    """
    Aggregate all file reviews into the canonical result envelope,
    write it to disk, and return (result, critical_issues, warning_issues).
    """
    _banner(5, 6, "PERSIST — writing result JSON")

    qualified_base = f"{config.remote}/{config.base_ref}"
    qualified_head = f"{config.remote}/{config.head_ref}"
    summary = f"Reviewed {len(files)} file(s) between {qualified_base} and {qualified_head}."

    critical: list[ReviewIssue] = []
    warnings: list[ReviewIssue] = []

    for fr in reviews:
        for issue in fr.issues:
            (critical if issue.is_critical else warnings).append(issue)
        # Surface parse failures / summaries-only as info warnings
        if not fr.issues and fr.summary:
            warnings.append(ReviewIssue(
                file=fr.file, line="", severity="info", message=fr.summary,
            ))

    status = "fail" if critical else "pass"
    result: dict[str, Any] = {
        "status":          status,
        "verdict":         status,
        "summary":         summary,
        "critical_issues": [i.to_dict() for i in critical],
        "suggestions":     [i.to_dict() for i in warnings],
        "details": {
            "llm_parsed": {
                "verdict":  status,
                "critical": [i.to_dict() for i in critical],
                "warnings": [i.to_dict() for i in warnings],
                "summary":  summary,
            },
            "reviewed_refs": {
                "base":       base_sha,
                "head":       head_sha,
                "base_label": qualified_base,
                "head_label": qualified_head,
            },
            "reviewed_files":   files,
            "per_file_reviews": [
                {
                    "file":       fr.file,
                    "returncode": fr.returncode,
                    "summary":    fr.summary,
                    "issues":     [i.to_dict() for i in fr.issues],
                }
                for fr in reviews
            ],
        },
    }

    out = Path(config.output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    _ok(f"result written to {config.output_path}")
    _info(f"status       = {status}")
    _info(f"critical     = {len(critical)}")
    _info(f"warnings     = {len(warnings)}")

    return result, critical, warnings


# ============================================================================
# Stage 6 — COMMENT: post to GitHub PR
# ============================================================================

def stage_comment(
    config: ReviewConfig,
    github: GitHubClient | None,
    result: dict[str, Any],
    critical: list[ReviewIssue],
    warnings: list[ReviewIssue],
    files: list[str],
    pr_override: int | None,
    dry_run: bool,
) -> bool:
    """
    Post the summary comment and inline review to the PR.
    Returns True when the comment was successfully written.
    """
    _banner(6, 6, "COMMENT — posting to GitHub PR")

    if dry_run:
        _warn("dry-run: skipping GitHub comment")
        _print_dry_run_comment(result, critical, warnings, files)
        return False

    if github is None:
        _warn("GitHub client not available — comment skipped")
        return False

    git = Git(remote=config.remote)
    branch = git.current_branch()
    _info(f"branch = {branch!r}")

    try:
        pr_number = pr_override or github.resolve_pr_number(branch)
    except Exception as exc:
        _err(f"could not resolve PR number: {exc}")
        return False

    if not pr_number:
        _warn("no open PR found for this branch — comment skipped")
        return False

    _info(f"PR number = {pr_number}")

    # --- head commit SHA ------------------------------------------------
    try:
        commit_sha = github.get_pr_head_sha(pr_number)
    except Exception as exc:
        _warn(f"could not fetch PR head SHA: {exc} — inline comments will be skipped")
        commit_sha = None

    if commit_sha:
        _ok(f"head SHA = {commit_sha}")
    else:
        _warn("head SHA unavailable — inline comments will be skipped")

    # --- summary comment ------------------------------------------------
    status  = result.get("status", "unknown")
    summary = result.get("summary", "")
    summary_body = _format_summary_comment(status, critical, warnings, summary, files)

    try:
        github.upsert_summary_comment(pr_number, summary_body)
        _ok("summary comment posted")
    except (HTTPError, URLError, OSError, ValueError) as exc:
        _err(f"summary comment failed: {exc}")
        return False

    # --- inline review --------------------------------------------------
    if not commit_sha:
        _warn("skipping inline review (no commit SHA)")
        return True

    all_issues = critical + warnings
    inline_count = sum(
        1 for i in all_issues
        if i.line and str(i.line).strip().isdigit() and int(str(i.line).strip()) > 0
    )
    _info(f"eligible inline comments = {inline_count}")

    try:
        github.dismiss_previous_review_comments(pr_number)
        _info("previous bot review comments dismissed")
    except Exception as exc:
        _warn(f"could not dismiss old comments: {exc}")

    try:
        github.post_review_with_inline_comments(
            pr_number=pr_number,
            commit_sha=commit_sha,
            issues=all_issues,
            summary_body=summary_body,
        )
        _ok(f"inline review posted ({inline_count} comment(s))")
    except (HTTPError, URLError, OSError, ValueError) as exc:
        _err(f"inline review failed: {exc}")
        return False

    return True


# ============================================================================
# Dry-run pretty-print
# ============================================================================

def _print_dry_run_comment(
    result: dict[str, Any],
    critical: list[ReviewIssue],
    warnings: list[ReviewIssue],
    files: list[str],
) -> None:
    status = result.get("status", "unknown")
    summary_body = _format_summary_comment(status, critical, warnings, result.get("summary", ""), files)
    print()
    print(f"{_C['dim']}{'─' * 60}")
    print("  DRY-RUN — PR comment body that would be posted:")
    print(f"{'─' * 60}{_C['reset']}")
    for line in summary_body.splitlines():
        print(f"  {line}")
    print(f"{_C['dim']}{'─' * 60}{_C['reset']}")


# ============================================================================
# Final summary
# ============================================================================

def _print_final_summary(
    critical: list[ReviewIssue],
    warnings: list[ReviewIssue],
    comment_written: bool,
    elapsed: float,
) -> None:
    print()
    print(f"{_C['bold']}{'═' * 60}{_C['reset']}")
    status_str = (
        f"{_C['red']}FAIL{_C['reset']}" if critical
        else f"{_C['green']}PASS{_C['reset']}"
    )
    print(f"  {_C['bold']}Result:{_C['reset']} {status_str}")
    print(f"  Critical issues : {_C['red']}{len(critical)}{_C['reset']}")
    print(f"  Warnings        : {_C['yellow']}{len(warnings)}{_C['reset']}")
    print(f"  PR comment      : {'✅ posted' if comment_written else '⏭ skipped'}")
    print(f"  Total time      : {elapsed:.1f}s")
    print(f"{_C['bold']}{'═' * 60}{_C['reset']}")
    print()


# ============================================================================
# Main entry point
# ============================================================================

def main(argv: list[str] | None = None) -> int:
    """
    Run the full e2e pipeline and return an exit code:
      0  — success
      1  — unrecoverable error
      2  — critical issues found (only when --fail-on-critical is set)
    """
    args   = _parse_args(argv)
    config = _build_config(args)
    t_start = time.monotonic()

    try:
        # ── Stage 1: validate config and build GitHub client ──────────────
        github = stage_init(config, args)

        # ── Stage 2: fetch remote refs ─────────────────────────────────────
        head_sha, base_sha = stage_fetch(config)

        # ── Stage 3: compute diff ──────────────────────────────────────────
        files = stage_diff(config, head_sha, base_sha)

        if not files:
            _print_final_summary([], [], False, time.monotonic() - t_start)
            return 0

        # ── Stage 4: run Claude review ─────────────────────────────────────
        reviews = stage_review(config, files, dry_run=args.dry_run)

        # ── Stage 5: persist result JSON ───────────────────────────────────
        result, critical, warnings = stage_persist(
            config, head_sha, base_sha, files, reviews
        )

        # ── Stage 6: post PR comment ────────────────────────────────────────
        comment_written = stage_comment(
            config=config,
            github=github,
            result=result,
            critical=critical,
            warnings=warnings,
            files=files,
            pr_override=args.pr,
            dry_run=args.dry_run,
        )

        _print_final_summary(critical, warnings, comment_written, time.monotonic() - t_start)

        # Enforce required-comment gate (only on GitHub Actions PR events)
        if (
            not args.dry_run
            and not args.skip_comment
            and not comment_written
            and os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
        ):
            _err("PR comment was required but not posted")
            return 1

        if args.fail_on_critical and critical:
            _err(f"{len(critical)} critical issue(s) found — failing build")
            return 2

        return 0

    except KeyboardInterrupt:
        print("\n[interrupted]", flush=True)
        return 1

    except Exception as exc:  # noqa: BLE001
        _err(f"unexpected error: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
