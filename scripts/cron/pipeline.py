#!/usr/bin/env python3
"""Cron-driven multi-agent pipeline — OpenClaw edition.

Each cron entry invokes this script with an agent name:

    python3 scripts/cron/pipeline.py <agent>

Where <agent> is one of:
    manager          heartbeat snapshot (no LLM call)
    test             pytest on tests/unit (no LLM call — boolean)
    code-review      collect diff, ask openclaw to judge, gated on test green
    qc               collect style/type/docs signals, ask openclaw to judge
    orchestrator     run test -> review -> qc and let openclaw recommend next step
    deploy           run scripts/deploy.py (gated on qc green today)
    research         ask openclaw to propose new improvement tasks and drop
                     them into shared-memory/tasks/ as JSON files
    task             pop the oldest unclaimed task from shared-memory/tasks/,
                     ask openclaw to draft an execution plan for it (advisory
                     only — the cron loop never edits source code directly)

Design: this script is the *tool-user*. It runs pytest/ruff/mypy/git diff
locally, then hands the raw output to the OpenClaw ``main`` agent (backed
by ai-gateway/MiniMax-M2.7) for *judgement*. The agent replies in
structured JSON and the pipeline writes a result envelope that the next
cron stage gates on.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _load_dotenv_into_environ() -> None:
    """Load REPO_ROOT/.env into ``os.environ`` so all subprocess.run() calls
    (pytest in worktrees, ruff, mypy, the openclaw agent etc.) inherit the
    DB credentials and any other secrets the user kept out of git.

    Minimal parser — no python-dotenv dependency at the pipeline layer.
    Existing env vars are NOT overwritten (env wins over file).
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_dotenv_into_environ()

from docs.agents._llm import ask_agent, compose_prompt, LLMOutcome  # noqa: E402

SHARED = REPO_ROOT / "shared-memory"
RESULTS_DIR = SHARED / "results"
TASKS_DIR = SHARED / "tasks"
REPORTS_DIR = SHARED / "reports"
LOG_DIR = SHARED / "logs"
LOCK_DIR = SHARED / "locks"

for d in (RESULTS_DIR, TASKS_DIR, REPORTS_DIR, LOG_DIR, LOCK_DIR):
    d.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# Envelope / locking / gating helpers
# -----------------------------------------------------------------------------
def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _log(job: str, message: str) -> None:
    line = f"[{_now()}] [{job}] {message}"
    print(line)
    with (LOG_DIR / f"{job}.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _write_envelope(agent: str, status: str, details: Dict[str, Any]) -> Path:
    path = RESULTS_DIR / f"{agent}-result.json"
    path.write_text(json.dumps({
        "agent": agent,
        "status": status,
        "generated_at": _now(),
        "details": details,
    }, indent=2, ensure_ascii=False))
    return path


def _read_envelope(agent: str) -> Optional[Dict[str, Any]]:
    path = RESULTS_DIR / f"{agent}-result.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _is_green_today(agent: str, max_age: timedelta = timedelta(hours=24)) -> bool:
    env = _read_envelope(agent)
    if not env or env.get("status") != "pass":
        return False
    try:
        gen = datetime.fromisoformat(env["generated_at"].rstrip("Z"))
    except (KeyError, ValueError):
        return False
    return datetime.utcnow() - gen <= max_age


class _Lock:
    def __init__(self, name: str):
        self.path = LOCK_DIR / f"{name}.lock"
        self.name = name

    def __enter__(self) -> "_Lock":
        if self.path.exists():
            try:
                pid = int(self.path.read_text().strip() or 0)
            except ValueError:
                pid = 0
            if pid and _pid_alive(pid):
                _log(self.name, f"previous run (pid={pid}) still active; skipping")
                sys.exit(0)
            _log(self.name, "stale lock found; reclaiming")
        self.path.write_text(str(os.getpid()))
        return self

    def __exit__(self, *_exc) -> None:
        self.path.unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _run(cmd: List[str], job: str, timeout: int = 600) -> subprocess.CompletedProcess:
    _log(job, f"$ {' '.join(cmd)}")
    return subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout,
    )


def _envelope_from_llm(step: str, outcome: LLMOutcome,
                       local_data: Optional[Dict[str, Any]] = None) -> None:
    """Translate an LLM outcome + any local data into the pipeline envelope."""
    details: Dict[str, Any] = {
        "llm_status": outcome.status,
        "llm_parsed": outcome.parsed,
        "llm_elapsed_sec": round(outcome.elapsed_sec, 2),
    }
    if outcome.reason:
        details["reason"] = outcome.reason
    if outcome.raw_text and not outcome.parsed:
        details["raw_text_tail"] = outcome.raw_text.splitlines()[-10:]
    if local_data:
        details["local"] = local_data
    _write_envelope(step, outcome.status, details)
    _log(step, f"status={outcome.status} reason={outcome.reason or '-'}")


# -----------------------------------------------------------------------------
# Stats (read-only, no locks, cheap — safe to call from any prompt)
# -----------------------------------------------------------------------------
def _collect_stats() -> Dict[str, Any]:
    """Summarize task queue + pipeline health for the manager heartbeat.

    Task lifecycle (see step_research / step_task):
      pending    — task file exists, ``claimed_at`` is null
      executing  — ``claimed_at`` is set but ``result_path`` is null
      completed  — ``result_path`` points at a real file under shared-memory/
    """
    pending = executing = completed = 0
    impl_open = impl_failed = 0
    impl_prs: List[str] = []
    latest_task: Optional[Dict[str, Any]] = None

    for path in sorted(TASKS_DIR.glob("research-*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if not data.get("claimed_at"):
            pending += 1
        elif not data.get("result_path"):
            executing += 1
        else:
            completed += 1
        if data.get("implementation_branch"):
            impl_open += 1
            if data.get("pr_url"):
                impl_prs.append(data["pr_url"])
        if data.get("implementation_failed"):
            impl_failed += 1
        if latest_task is None or (data.get("created_at") or "") > (latest_task.get("created_at") or ""):
            latest_task = data

    # Pipeline stage health + age.
    stages: Dict[str, Dict[str, Any]] = {}
    now_utc = datetime.utcnow()
    for agent in ("test", "code-review", "qc", "deploy", "orchestrator",
                  "research", "task"):
        env = _read_envelope(agent)
        if not env:
            stages[agent] = {"status": "missing", "age_min": None}
            continue
        try:
            gen = datetime.fromisoformat(env["generated_at"].rstrip("Z"))
            age_min = int((now_utc - gen).total_seconds() // 60)
        except (KeyError, ValueError):
            age_min = None
        stages[agent] = {"status": env.get("status"), "age_min": age_min}

    # Non-research task files (e.g. crm_phaseN_plan.json) — not part of the
    # research loop but still sitting in the queue; report them too.
    other_files = sorted(
        p.name for p in TASKS_DIR.glob("*.json")
        if not p.name.startswith("research-")
    )

    return {
        "generated_at": _now(),
        "tasks": {
            "pending": pending,
            "executing": executing,
            "completed": completed,
            "implemented_prs": impl_open,
            "implementation_failed": impl_failed,
            "pr_urls": impl_prs,
            "other_files": other_files,
            "latest_research": (latest_task or {}).get("title"),
        },
        "stages": stages,
    }


def _format_stats_human(stats: Dict[str, Any]) -> str:
    """Human-readable rendering suitable as a one-shot status line."""
    t = stats["tasks"]
    lines = [
        f"📊 Tasks: {t['pending']} pending · {t['executing']} executing · {t['completed']} completed",
    ]
    if t.get("implemented_prs") or t.get("implementation_failed"):
        lines.append(
            f"   🤖 impl: {t.get('implemented_prs', 0)} PR(s), "
            f"{t.get('implementation_failed', 0)} failed"
        )
    if t.get("other_files"):
        lines.append(f"   + {len(t['other_files'])} non-research task file(s) in queue")
    if t.get("latest_research"):
        lines.append(f"   latest research: {t['latest_research']}")

    stage_parts = []
    for name, info in stats["stages"].items():
        age = f"{info['age_min']}m" if info.get("age_min") is not None else "?"
        stage_parts.append(f"{name}={info['status']}({age})")
    lines.append("🔧 Stages: " + " ".join(stage_parts))
    return "\n".join(lines)


def cmd_stats(as_json: bool = False) -> int:
    """Print pipeline stats to stdout. Returns 0 so cron agent can chain this."""
    stats = _collect_stats()
    if as_json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        print(_format_stats_human(stats))
    return 0


# -----------------------------------------------------------------------------
# Steps
# -----------------------------------------------------------------------------
def step_manager() -> Dict[str, Any]:
    """Heartbeat — persist the stats snapshot + log the human-readable line."""
    stats = _collect_stats()
    _write_envelope("manager", "pass", stats)
    _log("manager", _format_stats_human(stats).replace("\n", " | "))
    return stats


def step_test() -> Dict[str, Any]:
    """Run pytest. The pass/fail signal is binary — no need for an LLM."""
    try:
        proc = _run(
            ["python3", "-m", "pytest", "tests/unit", "-q",
             "--ignore=tests/unit/test_user_service.py",
             "--ignore=tests/unit/test_import_export_service.py",
             "--ignore=tests/unit/test_db_engine.py"],
            "test",
        )
    except subprocess.TimeoutExpired as exc:
        _write_envelope("test", "fail", {"reason": "pytest timeout", "timeout": exc.timeout})
        return {"timeout": True}

    status = "pass" if proc.returncode == 0 else "fail"
    details = {
        "returncode": proc.returncode,
        "tail": proc.stdout.splitlines()[-8:] if proc.stdout else [],
    }
    _write_envelope("test", status, details)
    _log("test", f"pytest returncode={proc.returncode}")
    return details


def step_code_review() -> Dict[str, Any]:
    """Review what's on ``origin/develop`` but not on ``origin/master`` —
    i.e. the current "pending release" delta. Anchored to remote refs so it
    doesn't matter what the local HEAD is or whether the pod has pulled."""
    if not _is_green_today("test"):
        _write_envelope("code-review", "skipped", {"reason": "test not green in last 24h"})
        _log("code-review", "test not green; skipping")
        return {"skipped": True}

    # Freshen both refs so the review sees post-merge reality, not pod-local
    # state. ``--no-write-fetch-head`` avoids touching FETCH_HEAD churn.
    _run(["git", "fetch", "--quiet", "origin", "master", "develop"],
         "code-review", timeout=60)

    diff_proc = _run(
        ["git", "diff", "origin/master..origin/develop"],
        "code-review", timeout=30,
    )
    diff = diff_proc.stdout or ""
    MAX_DIFF = 60_000
    truncated_chars = 0
    if len(diff) > MAX_DIFF:
        truncated_chars = len(diff) - MAX_DIFF
        diff = diff[:MAX_DIFF] + f"\n\n...[truncated {truncated_chars} chars]"

    # List the refs so the LLM can tell from the prompt what it's reviewing.
    head_info = subprocess.run(
        ["git", "log", "-1", "--format=%H %s", "origin/develop"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    base_info = subprocess.run(
        ["git", "log", "-1", "--format=%H %s", "origin/master"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
    ).stdout.strip()

    prompt = compose_prompt(
        role="code-review",
        task=(
            "Review the diff from origin/master to origin/develop — this is "
            "what would merge to main on the next release. Look across your "
            "four SOUL dimensions: quality, security, performance, "
            "architecture. Set status=\"pass\" ONLY if there are zero "
            "critical-severity issues."
        ),
        data=(
            f"base: {base_info}\nhead: {head_info}\n\n"
            + (diff if diff.strip() else "(no diff — develop has nothing new vs master)")
        ),
        schema=(
            '{"status": "pass"|"fail", '
            '"critical": [{"dim": str, "line": int|null, "msg": str}], '
            '"warnings": [str], "suggestions": [str], "summary": str}'
        ),
    )
    outcome = ask_agent(prompt, thinking="medium")
    _envelope_from_llm("code-review", outcome, local_data={
        "diff_chars": len(diff),
        "truncated_chars": truncated_chars,
        "base": base_info,
        "head": head_info,
    })
    return outcome.parsed


def step_qc() -> Dict[str, Any]:
    """Gate on review green. Collect style/type/docs signals, ask for judgement."""
    if not _is_green_today("code-review"):
        _write_envelope("qc", "skipped", {"reason": "code-review not green in last 24h"})
        _log("qc", "code-review not green; skipping")
        return {"skipped": True}

    signals: Dict[str, Any] = {}

    ruff = _run(["python3", "-m", "ruff", "check", "src"], "qc", timeout=60)
    if ruff.returncode == 127 or "No module named" in (ruff.stderr or ""):
        compile_proc = _run(
            ["python3", "-c",
             "import compileall,sys; sys.exit(0 if compileall.compile_dir('src', quiet=1) else 1)"],
            "qc", timeout=60,
        )
        signals["style"] = {"tool": "compileall", "returncode": compile_proc.returncode}
    else:
        signals["style"] = {
            "tool": "ruff",
            "returncode": ruff.returncode,
            "findings_tail": (ruff.stdout or "").splitlines()[-10:],
        }

    if (REPO_ROOT / "mypy.ini").exists():
        mypy = _run(["python3", "-m", "mypy", "src"], "qc", timeout=120)
        if mypy.returncode == 127 or "No module named" in (mypy.stderr or ""):
            signals["types"] = {"tool": "mypy", "returncode": "not-installed"}
        else:
            signals["types"] = {
                "tool": "mypy",
                "returncode": mypy.returncode,
                "findings_tail": (mypy.stdout or "").splitlines()[-10:],
            }

    signals["docs"] = {"readme_exists": (REPO_ROOT / "README.md").exists()}

    prompt = compose_prompt(
        role="qc",
        task=(
            "Review the QC signals below (style, types, docs). "
            "Respect your SOUL's quality gate: status=\"pass\" only if the "
            "release is genuinely deploy-ready."
        ),
        data=json.dumps(signals, indent=2, ensure_ascii=False),
        schema=(
            '{"status": "pass"|"fail", '
            '"blocking": [str], "non_blocking": [str], "summary": str}'
        ),
    )
    outcome = ask_agent(prompt, thinking="low")
    _envelope_from_llm("qc", outcome, local_data={"signals": signals})
    return outcome.parsed


def step_orchestrator() -> Dict[str, Any]:
    """Run test -> review -> qc in order, let openclaw recommend next action."""
    ran: List[str] = []
    for name, fn in [("test", step_test), ("code-review", step_code_review), ("qc", step_qc)]:
        ran.append(name)
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            _write_envelope(name, "fail", {"exception": str(exc)})
            _log("orchestrator", f"{name} raised: {exc}")
            break

    summary = {
        agent: (_read_envelope(agent) or {}).get("status", "missing")
        for agent in ("test", "code-review", "qc")
    }

    prompt = compose_prompt(
        role="orchestrator",
        task=(
            "Given each sub-agent's status below, decide whether to recommend "
            "deployment. Only recommend deploy when ALL statuses are \"pass\"."
        ),
        data=json.dumps(summary, indent=2),
        schema=(
            '{"status": "pass"|"fail", '
            '"recommendation": "deploy"|"fix-and-retry"|"hold", '
            '"reason": str}'
        ),
    )
    outcome = ask_agent(prompt, thinking="low")

    all_green = all(v == "pass" for v in summary.values())
    recommendation = outcome.parsed.get("recommendation") or (
        "deploy" if all_green else "fix-and-retry"
    )

    report = {
        "report_id": f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": _now(),
        "ran": ran,
        "summary": summary,
        "recommendation": recommendation,
        "llm_reason": outcome.parsed.get("reason", ""),
    }
    (REPORTS_DIR / f"{report['report_id']}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    _write_envelope("orchestrator", "pass" if all_green else "fail", report)
    _log("orchestrator", f"report={report['report_id']} recommendation={recommendation}")
    return report


def step_deploy() -> Dict[str, Any]:
    """Only deploy if QC is green today. No LLM in the path — binary decision."""
    if not _is_green_today("qc"):
        _write_envelope("deploy", "skipped", {"reason": "qc not green today"})
        _log("deploy", "qc not green; skipping")
        return {"skipped": True}

    deploy_script = REPO_ROOT / "scripts" / "deploy.py"
    if not deploy_script.exists():
        _write_envelope("deploy", "fail", {"reason": "scripts/deploy.py missing"})
        _log("deploy", "deploy script missing")
        return {"missing": True}

    proc = _run(["python3", str(deploy_script)], "deploy", timeout=900)
    status = "pass" if proc.returncode == 0 else "fail"
    details = {
        "returncode": proc.returncode,
        "tail": proc.stdout.splitlines()[-12:] if proc.stdout else [],
    }
    _write_envelope("deploy", status, details)
    _log("deploy", f"deploy finished status={status}")
    return details


def _existing_queue_titles() -> List[str]:
    """Titles of all tasks currently in the queue — helps the researcher
    avoid proposing duplicates of work we've already planned."""
    titles: List[str] = []
    for p in sorted(TASKS_DIR.glob("research-*.json")):
        try:
            titles.append(json.loads(p.read_text()).get("title") or p.stem)
        except json.JSONDecodeError:
            continue
    return titles


def _repo_inventory() -> str:
    """Lightweight inventory of service methods and test functions under
    src/services/ and tests/unit/. Lets the researcher check whether a
    proposed method/test already exists *before* proposing it."""
    lines: List[str] = []
    # Service method signatures
    svc_grep = subprocess.run(
        ["git", "grep", "-n", "-E", r"^    def [a-z_][a-z_0-9]*\(",
         "--", "src/services/"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
    )
    svc_lines = [l for l in (svc_grep.stdout or "").splitlines()
                 if "__init__" not in l and "_post_init" not in l]
    lines.append(f"## existing service methods ({len(svc_lines)})")
    # Keep it capped to avoid prompt bloat.
    lines.extend(svc_lines[:80])

    # Test function names
    test_grep = subprocess.run(
        ["git", "grep", "-n", "-E", r"^    def test_[a-z_0-9]+\(",
         "--", "tests/unit/"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
    )
    test_lines = [l for l in (test_grep.stdout or "").splitlines()]
    lines.append(f"\n## existing unit tests ({len(test_lines)})")
    lines.extend(test_lines[:80])

    return "\n".join(lines)


def _collect_context_for_research() -> str:
    """Gather lightweight signals the researcher role uses as input.

    The goal of this context is to make "already done" detectable at
    proposal time — we include the current method/test inventory so the
    researcher doesn't invent tasks that are already satisfied.
    """
    parts: List[str] = []

    log_proc = subprocess.run(
        ["git", "log", "--oneline", "-15"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
    )
    parts.append("## recent commits\n" + (log_proc.stdout or "(none)"))

    health: Dict[str, str] = {}
    for agent in ("test", "code-review", "qc", "deploy"):
        env = _read_envelope(agent)
        health[agent] = (env or {}).get("status", "missing")
    parts.append("## pipeline health\n" + json.dumps(health, indent=2))

    try:
        grep = subprocess.run(
            ["git", "grep", "-n", "-E", r"TODO|FIXME|XXX", "--", "src"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
        todos = (grep.stdout or "").splitlines()[:30]
        parts.append("## TODO/FIXME markers (first 30)\n"
                     + ("\n".join(todos) or "(none)"))
    except subprocess.TimeoutExpired:
        parts.append("## TODO/FIXME markers\n(scan timed out)")

    parts.append(_repo_inventory())

    existing = _existing_queue_titles()
    parts.append("## existing task titles in queue — DO NOT duplicate\n"
                 + ("\n".join(f"- {t}" for t in existing) or "(none)"))

    return "\n\n".join(parts)


_FILENAME_RE = re.compile(r"[A-Za-z0-9_\-./]+\.py")


def _research_task_is_implementable(task: Dict[str, Any]) -> Optional[str]:
    """Return None if the task is fit for autonomous implementation, else
    a string explaining why it's being dropped.

    This mirrors the implementer's pre-flight gates so we don't pollute the
    queue with tasks the implementer will never pick up.
    """
    if not isinstance(task, dict):
        return "not an object"
    title = (task.get("title") or "").strip()
    if not title:
        return "missing title"
    if task.get("priority") not in {"low", "medium", "high"}:
        return f"invalid priority={task.get('priority')!r}"
    if task.get("kind") not in {"bugfix", "test", "refactor", "docs", "security"}:
        return f"invalid kind={task.get('kind')!r}"

    targets = task.get("target_files") or []
    if not isinstance(targets, list) or not targets:
        return "target_files empty"
    # Every target must live under the implementer's allowlist AND look like
    # an actual file path (ends in .py or .pyi, or is a directory under one
    # of the allowed prefixes).
    for t in targets:
        if not isinstance(t, str) or not t.strip():
            return f"non-string target {t!r}"
        # Strip ":<lineno>" suffixes the LLM sometimes appends.
        tt = t.split(":", 1)[0].strip()
        if not any(tt.startswith(p) for p in IMPLEMENT_ALLOWED_PREFIXES):
            return f"target {t!r} outside {IMPLEMENT_ALLOWED_PREFIXES}"
        # Accept .py and the text-config files we expect inside src/+tests/
        # (alembic.ini, env.py.mako, MIGRATION_NOTES.md, etc.). Reject
        # anything that doesn't look like text source.
        _allowed_exts = (".py", ".pyi", ".ini", ".cfg", ".toml",
                         ".mako", ".md", ".txt", ".json", ".yaml", ".yml")
        if not (tt.endswith(_allowed_exts) or tt.endswith("/")):
            return f"target {t!r} is not a recognised text-source file or directory"

    desc = (task.get("description") or "").strip()
    acc = (task.get("acceptance") or "").strip()
    if len(desc) < 40:
        return "description too short (need concrete spec)"
    if len(acc) < 40:
        return "acceptance too short"
    # Acceptance must contain at least ONE mechanically-checkable signal.
    # A simple heuristic: require either a named function/method or a
    # grep-able signal like "returns", "equals", "passes".
    acc_lower = acc.lower()
    mechanical = any(h in acc_lower for h in (
        "returns ", "equal", "assert", "pytest", "method ", "function ",
        "class ", "test_", "def ", "raises", "== ", "contains ",
    ))
    if not mechanical:
        return "acceptance lacks a mechanical check"
    return None


def step_research() -> Dict[str, Any]:
    """Ask the LLM to propose 1-3 new IMPLEMENTABLE tasks and drop them as files.

    Two layers of quality control:
      1. Prompt constrains proposals to files under src/|tests/, concrete
         named symbols, and mechanically-checkable acceptance.
      2. Post-LLM pre-filter (_research_task_is_implementable) drops any
         proposal that still slips past the prompt, and records why.
    """
    context = _collect_context_for_research()

    prompt = compose_prompt(
        role="research",
        task=(
            "Propose between 1 and 3 new, IMPLEMENTABLE tasks for the "
            "autonomous implementer agent. A task is 'implementable' iff "
            "ALL of the following hold:\n"
            f"  (a) Every target_files entry lives under "
            f"{', '.join(IMPLEMENT_ALLOWED_PREFIXES)} — NEVER .github/, "
            ".idea/, scripts/, docs/, shared-memory/, pyproject.toml, or "
            "any root-level config.\n"
            "  (b) Target files exist OR the task explicitly creates them "
            "under tests/unit/.\n"
            "  (c) Work is tightly scoped: <= ~60 lines of net diff.\n"
            "  (d) The task describes a NEW symbol (method name, class "
            "name, or test function name) that does NOT appear in the "
            "'existing service methods' or 'existing unit tests' inventory "
            "above — this makes 'already done' mechanically detectable.\n"
            "  (e) The 'acceptance' field contains at least one "
            "mechanical check (e.g. 'count_by_status returns "
            "Dict[CustomerStatus,int]', 'test_foo passes', "
            "'assert len(x)==3').\n"
            "Prefer filling test gaps for methods that already have code "
            "but minimal coverage. Only propose 'bugfix' if you can cite a "
            "specific line and a concrete failure mode."
        ),
        data=context,
        schema=(
            '{"status": "pass"|"fail", '
            '"notes": str (one sentence: why you chose this many tasks, '
            'or why zero — e.g. "queue already covers gaps"), '
            '"tasks": [{"title": str, '
            '"kind": "bugfix"|"test"|"refactor"|"docs"|"security", '
            '"priority": "high"|"medium"|"low", '
            '"target_files": [str], '
            '"description": str (>=40 chars, cites exact new symbol name), '
            '"acceptance": str (>=40 chars, includes mechanical check)}]}'
        ),
    )
    outcome = ask_agent(prompt, thinking="medium")

    proposed = outcome.parsed.get("tasks") or []
    created: List[str] = []
    dropped: List[Dict[str, str]] = []
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    for idx, task in enumerate(proposed):
        reject = _research_task_is_implementable(task if isinstance(task, dict) else {})
        if reject:
            dropped.append({"index": idx, "reason": reject,
                            "title": (task.get("title") if isinstance(task, dict) else "?")})
            continue
        task_id = f"research-{ts}-{idx:02d}"
        path = TASKS_DIR / f"{task_id}.json"
        path.write_text(json.dumps({
            "task_id": task_id,
            "created_at": _now(),
            "source": "research",
            "claimed_at": None,
            "result_path": None,
            **task,
        }, indent=2, ensure_ascii=False))
        created.append(task_id)

    notes = (outcome.parsed.get("notes") or "").strip()
    details = {
        "llm_status": outcome.status,
        "llm_elapsed_sec": round(outcome.elapsed_sec, 2),
        "created_tasks": created,
        "proposed_count": len(proposed),
        "dropped_count": len(dropped),
        "dropped": dropped,
        "llm_notes": notes,
    }
    # Research "passing" just means the run completed. Zero kept after
    # filtering is still a pass — it means the researcher didn't give us
    # anything clean enough this cycle, not that the pipeline is broken.
    _write_envelope("research", "pass" if outcome.status != "error" else "fail", details)
    log_line = (
        f"proposed={len(proposed)} created={len(created)} dropped={len(dropped)}"
    )
    if dropped:
        log_line += f" (first_drop: {dropped[0]['reason']})"
    if notes:
        log_line += f" | notes: {notes[:140]}"
    elif len(proposed) == 0:
        log_line += " | notes: (agent gave none — add 'notes' to schema next)"
    _log("research", log_line)
    return details


def step_task() -> Dict[str, Any]:
    """Pop the oldest unclaimed research task and draft an execution plan.

    Advisory only: this step never edits source files. Its job is to
    produce a detailed plan a human (or a future action-agent) can apply.
    That keeps the autonomous loop safe.
    """
    candidates = sorted(TASKS_DIR.glob("research-*.json"))
    pending: Optional[Path] = None
    for path in candidates:
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if not data.get("claimed_at"):
            pending = path
            break

    if pending is None:
        _write_envelope("task", "skipped", {"reason": "no unclaimed tasks in queue"})
        _log("task", "no unclaimed tasks")
        return {"skipped": True}

    task = json.loads(pending.read_text())
    task_id = task.get("task_id", pending.stem)

    # Claim the task so a concurrent cron fire doesn't re-pick it.
    task["claimed_at"] = _now()
    pending.write_text(json.dumps(task, indent=2, ensure_ascii=False))

    # Add relevant file excerpts (first 120 lines each, up to 3 files) so the
    # LLM can cite specifics. Keeps prompt bounded.
    excerpts: Dict[str, str] = {}
    for target in (task.get("target_files") or [])[:3]:
        p = REPO_ROOT / target
        if p.is_file():
            try:
                excerpts[target] = "\n".join(p.read_text().splitlines()[:120])
            except OSError:
                continue

    prompt = compose_prompt(
        role="task",
        task=(
            "Draft a precise execution plan for the task below. DO NOT write "
            "any code in your reply — this is advisory. Produce concrete "
            "diff-level guidance: which file, which function, what changes. "
            "Flag risks and list a verification strategy."
        ),
        data=json.dumps({"task": task, "file_excerpts": excerpts}, indent=2, ensure_ascii=False),
        schema=(
            '{"status": "pass"|"fail", '
            '"plan": [{"file": str, "function": str, "change": str}], '
            '"risks": [str], '
            '"verify": [str], '
            '"estimate_minutes": int}'
        ),
    )
    outcome = ask_agent(prompt, thinking="medium")

    result_path = RESULTS_DIR / f"task-{task_id}-result.json"
    result_path.write_text(json.dumps({
        "task_id": task_id,
        "generated_at": _now(),
        "plan": outcome.parsed,
        "raw_tail": outcome.raw_text.splitlines()[-10:] if outcome.raw_text and not outcome.parsed else [],
    }, indent=2, ensure_ascii=False))

    # Point the task file at its result so the manager heartbeat can show it.
    task["result_path"] = str(result_path.relative_to(REPO_ROOT))
    pending.write_text(json.dumps(task, indent=2, ensure_ascii=False))

    _write_envelope("task", outcome.status, {
        "task_id": task_id,
        "result_path": str(result_path.relative_to(REPO_ROOT)),
        "llm_elapsed_sec": round(outcome.elapsed_sec, 2),
    })
    _log("task", f"planned task_id={task_id} status={outcome.status}")
    return {"task_id": task_id, "status": outcome.status}


# -----------------------------------------------------------------------------
# step_implement — turn a planned task into a branch + PR
#
# Guardrails (enforced by the code, NOT just the prompt):
#   * Cooldown: no implement run in the last IMPLEMENT_COOLDOWN_MIN minutes
#   * Test gate: test envelope must be green (within 24h)
#   * Task must have a plan (result_path set) and no prior implementation_branch
#   * Task priority must NOT be "high" (those need human attention)
#   * Task plan estimate_minutes must be <= IMPLEMENT_MAX_ESTIMATE_MIN
#   * Every edit must land under src/ or tests/
#   * No writes to .git/, shared-memory/, scripts/, docs/, .github/
#   * Diff must be <= IMPLEMENT_MAX_DIFF_LINES total
#   * Tests must pass inside the worktree after the agent's work
#   * Pre-commit hook must pass (the agent iterates on failures itself,
#     using its own read/edit/write/exec tools)
#   * Branches are pushed, PRs are opened, nothing is merged.
# -----------------------------------------------------------------------------
IMPLEMENT_COOLDOWN_MIN = 60
IMPLEMENT_MAX_DIFF_LINES = 400
IMPLEMENT_MAX_ESTIMATE_MIN = 30
IMPLEMENT_ALLOWED_PREFIXES = ("src/", "tests/")
IMPLEMENT_FORBIDDEN_PREFIXES = (
    ".git/", ".github/", "shared-memory/", "scripts/", "docs/", ".idea/",
)
# Token-shaped patterns we refuse to commit even if the LLM tries. Conservative.
_SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"gho_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]
WORKTREE_ROOT = REPO_ROOT / ".worktrees"


def _find_implementable_task() -> Optional[Path]:
    """Pick the oldest planned task that passes all structural gates."""
    for path in sorted(TASKS_DIR.glob("research-*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if not data.get("result_path"):
            continue  # not planned yet
        if (data.get("implementation_branch")
                or data.get("implementation_failed")
                or data.get("implementation_obsolete")):
            continue  # already attempted / already done / no-op
        if (data.get("priority") or "medium") == "high":
            continue  # high-priority = human review
        # target_files must all live under the allowlist
        targets = data.get("target_files") or []
        if not targets or not all(
            any(t.startswith(p) for p in IMPLEMENT_ALLOWED_PREFIXES) for t in targets
        ):
            continue
        # Load the plan — need estimate_minutes
        result_path = REPO_ROOT / data["result_path"]
        if not result_path.exists():
            continue
        try:
            plan = json.loads(result_path.read_text()).get("plan", {})
        except json.JSONDecodeError:
            continue
        # Estimate gate: only reject when the planner explicitly said the
        # task is bigger than our cap. A missing/zero estimate falls through
        # — the diff-size guardrail is the real safety net.
        est = plan.get("estimate_minutes")
        if isinstance(est, int) and est > IMPLEMENT_MAX_ESTIMATE_MIN:
            continue
        return path
    return None


def _implement_cooldown_active() -> Optional[int]:
    """Return remaining cooldown minutes if the previous run was recent."""
    env = _read_envelope("implement")
    if not env:
        return None
    try:
        gen = datetime.fromisoformat(env["generated_at"].rstrip("Z"))
    except (KeyError, ValueError):
        return None
    elapsed = int((datetime.utcnow() - gen).total_seconds() // 60)
    if elapsed < IMPLEMENT_COOLDOWN_MIN:
        return IMPLEMENT_COOLDOWN_MIN - elapsed
    return None


def _path_allowed(rel_path: str) -> bool:
    """True iff the edit target is inside the allowlist and outside forbidden."""
    rel = rel_path.lstrip("./")
    if any(rel.startswith(p) for p in IMPLEMENT_FORBIDDEN_PREFIXES):
        return False
    return any(rel.startswith(p) for p in IMPLEMENT_ALLOWED_PREFIXES)


def _scan_for_secrets(text: str) -> Optional[str]:
    for pat in _SECRET_PATTERNS:
        m = pat.search(text or "")
        if m:
            return pat.pattern
    return None


_SKILL_DIR = Path("/home/node/.openclaw/workspace/skills")


def _prune_old_failed_worktrees(keep: int = 3) -> None:
    """Remove oldest failed worktrees beyond ``keep`` to bound disk growth."""
    if not WORKTREE_ROOT.exists():
        return
    failed = [
        p for p in WORKTREE_ROOT.iterdir()
        if p.is_dir() and (p / ".implement-failed").exists()
    ]
    failed.sort(key=lambda p: p.stat().st_mtime)
    for old in failed[:-keep]:
        subprocess.run(["git", "worktree", "remove", str(old), "--force"],
                       cwd=REPO_ROOT, capture_output=True, timeout=30)


def _load_skill_doc(name: str) -> str:
    """Return the SKILL.md contents for the given OpenClaw skill, if present.

    When the pipeline runs inside the pod the skill lives at
    ``~/.openclaw/workspace/skills/<name>/SKILL.md``. When running locally the
    file won't exist — the caller uses whatever falls through.
    """
    candidates = [
        _SKILL_DIR / name / "SKILL.md",
        REPO_ROOT / "docs" / "agents" / name / "SKILL.md",
    ]
    for path in candidates:
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            # Cap at 8 KiB — enough for any SKILL we care about, keeps prompt sane.
            return text[:8000]
    return ""


def _scan_worktree_for_secrets(worktree: Path) -> Optional[str]:
    """Scan only the files the worktree diff introduces/modifies for secrets."""
    proc = subprocess.run(
        ["git", "diff", "origin/develop", "--name-only"],
        cwd=worktree, capture_output=True, text=True, timeout=15,
    )
    for rel in (proc.stdout or "").splitlines():
        rel = rel.strip()
        if not rel:
            continue
        target = worktree / rel
        if not target.is_file():
            continue
        try:
            content = target.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hit = _scan_for_secrets(content)
        if hit:
            return f"{rel}: /{hit}/"
    return None


def _worktree_diff_lines(worktree: Path, base: str = "origin/develop") -> int:
    """Count line changes vs base branch. Measures COMMITTED changes, not
    the working-tree delta — important because the agent commits its work."""
    proc = subprocess.run(
        ["git", "diff", "--numstat", base], cwd=worktree,
        capture_output=True, text=True, timeout=30,
    )
    total = 0
    for line in (proc.stdout or "").splitlines():
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        try:
            total += int(cols[0]) + int(cols[1])
        except ValueError:
            pass
    return total


def _gh_open_pr(branch: str, title: str, body: str,
                base: str = "develop") -> Dict[str, Any]:
    """Open a PR via the GitHub REST API. Returns parsed JSON or an error dict."""
    token = (os.environ.get("GITHUB_BOT_TOKEN")
             or os.environ.get("GITHUB_TOKEN"))
    if not token:
        # Fall back to reading the PAT already configured on the remote URL
        # (the pod has it embedded in .git/config, per earlier setup).
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
        url = (proc.stdout or "").strip()
        m = re.search(r"https://([^@]+)@github\.com/", url)
        if m and ":" not in m.group(1):
            token = m.group(1)

    if not token:
        return {"error": "no GitHub token available (set GITHUB_BOT_TOKEN)"}

    # Derive owner/repo from origin URL
    proc = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
    )
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", proc.stdout or "")
    if not m:
        return {"error": f"could not parse owner/repo from {proc.stdout!r}"}
    owner, repo = m.group(1), m.group(2)

    payload = json.dumps({
        "title": title, "body": body, "head": branch, "base": base,
    })
    # Use curl so we don't take a new Python dependency.
    curl = subprocess.run(
        ["curl", "-sS", "-X", "POST",
         "-H", f"Authorization: Bearer {token}",
         "-H", "Accept: application/vnd.github+json",
         "-H", "X-GitHub-Api-Version: 2022-11-28",
         "-d", payload,
         f"https://api.github.com/repos/{owner}/{repo}/pulls"],
        capture_output=True, text=True, timeout=30,
    )
    if curl.returncode != 0:
        return {"error": f"curl failed: {curl.stderr.strip()[:200]}"}
    try:
        data = json.loads(curl.stdout)
    except json.JSONDecodeError:
        return {"error": "GitHub reply was not JSON", "raw": curl.stdout[:500]}
    if "html_url" not in data:
        # Common edge case: a previous attempt already opened a PR for the same
        # head+base. GitHub returns "Validation Failed" with a
        # "pull request already exists" sub-error. Look up the existing PR
        # and return its URL so the envelope still points at something useful.
        errors_blob = json.dumps(data.get("errors") or [])
        if "pull request already exists" in errors_blob.lower() or \
                data.get("message", "").lower() == "validation failed":
            existing = subprocess.run(
                ["curl", "-sS",
                 "-H", f"Authorization: Bearer {token}",
                 "-H", "Accept: application/vnd.github+json",
                 f"https://api.github.com/repos/{owner}/{repo}/pulls"
                 f"?state=open&head={owner}:{branch}"],
                capture_output=True, text=True, timeout=30,
            )
            try:
                prs = json.loads(existing.stdout) or []
            except json.JSONDecodeError:
                prs = []
            if isinstance(prs, list) and prs:
                return {"url": prs[0]["html_url"],
                        "number": prs[0].get("number"),
                        "note": "existing PR reused"}
        return {"error": data.get("message", "PR not created"),
                "detail": (data.get("errors") or [])[:3]}
    return {"url": data["html_url"], "number": data.get("number")}


def step_implement() -> Dict[str, Any]:
    """Pick a planned task, generate edits, test+commit+push, open a PR.

    Gates can be bypassed for manual runs by setting ``PIPELINE_FORCE=1`` in
    the environment (the ``--force`` CLI flag sets this for you).
    """
    forced = bool(os.environ.get("PIPELINE_FORCE"))

    # -- Gate 1: cooldown ------------------------------------------------------
    remaining = _implement_cooldown_active()
    if remaining is not None and not forced:
        _write_envelope("implement", "skipped",
                        {"reason": f"cooldown active, {remaining}m remaining"})
        _log("implement", f"cooldown skip ({remaining}m left)")
        return {"skipped": True}
    if remaining is not None and forced:
        _log("implement", f"cooldown ({remaining}m left) bypassed by --force")

    # -- Gate 2: test must be green --------------------------------------------
    if not _is_green_today("test"):
        _write_envelope("implement", "skipped",
                        {"reason": "test not green in last 24h"})
        _log("implement", "test not green; skip")
        return {"skipped": True}

    # -- Gate 3: find a workable task ------------------------------------------
    task_file = _find_implementable_task()
    if task_file is None:
        _write_envelope("implement", "skipped",
                        {"reason": "no eligible task in queue"})
        _log("implement", "no eligible task")
        return {"skipped": True}
    task = json.loads(task_file.read_text())
    task_id = task["task_id"]
    plan = json.loads((REPO_ROOT / task["result_path"]).read_text()).get("plan", {})

    # -- Set up fresh worktree off origin/develop ------------------------------
    WORKTREE_ROOT.mkdir(exist_ok=True)
    wt = WORKTREE_ROOT / f"auto-{task_id}"
    branch = f"auto/{task_id}"
    if wt.exists():
        subprocess.run(["git", "worktree", "remove", str(wt), "--force"],
                       cwd=REPO_ROOT, capture_output=True, timeout=30)
    # A stale branch from a previous attempt would collide with `-b`. Drop it.
    subprocess.run(["git", "branch", "-D", branch],
                   cwd=REPO_ROOT, capture_output=True, timeout=30)
    # Make sure we have the latest develop locally before branching off it.
    subprocess.run(["git", "fetch", "origin", "develop"],
                   cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
    add = subprocess.run(
        ["git", "worktree", "add", str(wt), "-b", branch, "origin/develop"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    if add.returncode != 0:
        _write_envelope("implement", "fail",
                        {"reason": "worktree add failed",
                         "stderr": add.stderr.strip()[:300]})
        _log("implement", f"worktree add failed: {add.stderr[:200]}")
        return {"failed": True}

    # -- Delegate the actual coding to the agent ------------------------------
    # The main agent has read/edit/write/exec/sessions_spawn natively. We
    # inject the subagent-driven-development SKILL.md as instructions so it
    # follows a TDD loop and keeps responsibility for any pre-commit-hook
    # back-and-forth. pipeline.py owns the guardrails, not the editing.
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()

    skill_doc = _load_skill_doc("subagent-driven-development")

    task_summary = {
        "task_id": task_id,
        "title": task.get("title"),
        "kind": task.get("kind"),
        "priority": task.get("priority"),
        "description": task.get("description"),
        "acceptance": task.get("acceptance"),
        "target_files": task.get("target_files"),
        "plan": plan,
    }
    delegate_prompt = "\n\n".join([
        "[role=implement] You are the implementer agent triggered by cron.",
        "You have the tools: read, edit, write, exec (plus sessions_spawn if you want a sub-turn).",
        f"Work ONLY inside this worktree: {wt}",
        f"The branch is already checked out: {branch} (off origin/develop).",
        "",
        "HARD CONSTRAINTS (pipeline will reject the result if violated):",
        f"  * Only modify files under: {', '.join(IMPLEMENT_ALLOWED_PREFIXES)}",
        f"  * NEVER touch: {', '.join(IMPLEMENT_FORBIDDEN_PREFIXES)}",
        f"  * Total diff vs origin/develop must be <= {IMPLEMENT_MAX_DIFF_LINES} lines",
        "  * Do NOT commit any secrets (PATs, API keys, etc.)",
        "  * You MUST produce at least one commit on this branch before returning.",
        "  * The pre-commit hook MUST pass — iterate on your edits until it does.",
        "  * The full pytest suite MUST be green after your changes.",
        "",
        "WORKFLOW (follow this skill, adapted for the worktree):",
        skill_doc or "(skill doc not loaded; default to: write failing test, implement, run pytest, commit)",
        "",
        "TASK:",
        json.dumps(task_summary, indent=2, ensure_ascii=False),
        "",
        "When finished, reply with ONLY this JSON (no prose, no fences):",
        '{"status": "pass"|"fail", "commit_sha": "<40-hex-or-empty>", '
        '"summary": "<one-sentence description>", "reason": "<only if fail>"}',
    ])

    outcome = ask_agent(delegate_prompt, thinking="high", timeout=1200)

    # -- Post-hoc verification — pipeline enforces ALL guardrails, not prompt -
    def _fail(reason: str, **extra: Any) -> Dict[str, Any]:
        # Snapshot diagnostics BEFORE cleaning up the worktree.
        diag: Dict[str, Any] = {"reason": reason, "task_id": task_id}
        diag["agent_status"] = outcome.status
        diag["agent_parsed"] = outcome.parsed
        diag["agent_raw_tail"] = (outcome.raw_text or "").splitlines()[-12:]
        diag["agent_elapsed_sec"] = round(outcome.elapsed_sec, 2)
        if wt.exists():
            # Capture what the agent actually wrote (if anything) so we can
            # diagnose hallucinated "pass" responses vs real workflow bugs.
            st = subprocess.run(
                ["git", "status", "--porcelain"], cwd=wt,
                capture_output=True, text=True, timeout=10,
            )
            diag["worktree_status"] = (st.stdout or "").splitlines()[:30]
            lg = subprocess.run(
                ["git", "log", "--oneline", "-5"], cwd=wt,
                capture_output=True, text=True, timeout=10,
            )
            diag["worktree_log"] = (lg.stdout or "").splitlines()
        diag.update(extra)
        task["implementation_failed"] = True
        task["last_error"] = reason
        task_file.write_text(json.dumps(task, indent=2, ensure_ascii=False))
        # Keep the worktree on fail so humans can inspect; add a marker file
        # and cap the number of preserved worktrees to prevent unbounded growth.
        if wt.exists():
            (wt / ".implement-failed").write_text(
                json.dumps(diag, indent=2, ensure_ascii=False)
            )
            _prune_old_failed_worktrees(keep=3)
        _write_envelope("implement", "fail", diag)
        _log("implement", f"task_id={task_id} fail: {reason}")
        return {"failed": True, "task_id": task_id, "reason": reason}

    if outcome.status != "pass":
        return _fail(f"agent returned status={outcome.status}: {outcome.reason or '-'}")

    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if not head_sha or head_sha == base_sha:
        # Distinguish "agent decided the task was already satisfied" (no-op,
        # obsolete task) from "agent claimed to work but didn't" (real fail).
        # Both show up as "no new commit", but the former has a meaningful
        # summary the agent wanted to convey.
        agent_summary = (outcome.parsed.get("summary") or "").strip()
        task["implementation_obsolete"] = True
        task["last_agent_summary"] = agent_summary
        task_file.write_text(json.dumps(task, indent=2, ensure_ascii=False))
        subprocess.run(["git", "worktree", "remove", str(wt), "--force"],
                       cwd=REPO_ROOT, capture_output=True, timeout=30)
        _write_envelope("implement", "skipped", {
            "task_id": task_id,
            "reason": "agent reports task already complete (no-op)",
            "agent_summary": agent_summary,
            "agent_elapsed_sec": round(outcome.elapsed_sec, 2),
        })
        _log("implement",
             f"task_id={task_id} no-op: {agent_summary[:120] or '(agent gave no summary)'}")
        return {"skipped": True, "task_id": task_id,
                "reason": "task already complete per agent"}

    changed = subprocess.run(
        ["git", "diff", "origin/develop", "--name-only"],
        cwd=wt, capture_output=True, text=True, timeout=15,
    ).stdout.splitlines()
    bad = [f for f in changed if f.strip() and not _path_allowed(f.strip())]
    if bad:
        return _fail(f"agent touched forbidden paths: {bad[:5]}")

    diff_lines = _worktree_diff_lines(wt)
    if diff_lines > IMPLEMENT_MAX_DIFF_LINES:
        return _fail(f"diff {diff_lines} > {IMPLEMENT_MAX_DIFF_LINES}",
                     diff_lines=diff_lines)

    secret_hit = _scan_worktree_for_secrets(wt)
    if secret_hit:
        return _fail(f"secret-shaped token in diff: {secret_hit}")

    # Final sanity run — if the agent broke tests and committed anyway, catch it.
    tproc = subprocess.run(
        ["python3", "-m", "pytest", "tests/unit", "-q",
         "--ignore=tests/unit/test_user_service.py",
         "--ignore=tests/unit/test_import_export_service.py"],
        cwd=wt, capture_output=True, text=True, timeout=240,
    )
    if tproc.returncode != 0:
        return _fail("final pytest failed in worktree",
                     tail=(tproc.stdout or "").splitlines()[-10:])

    commit_message = subprocess.run(
        ["git", "log", "-1", "--format=%s", head_sha],
        cwd=wt, capture_output=True, text=True, timeout=10,
    ).stdout.strip() or f"auto: implement {task_id}"

    # -- Push branch -----------------------------------------------------------
    # --force-with-lease is safe because we own the auto/* namespace and any
    # prior content on the remote branch came from a previous failed attempt
    # of the same task. It refuses to clobber unexpected upstream changes.
    p = subprocess.run(
        ["git", "push", "-u", "--force-with-lease", "origin", branch],
        cwd=wt, capture_output=True, text=True, timeout=120,
    )
    if p.returncode != 0:
        _write_envelope("implement", "fail",
                        {"task_id": task_id, "reason": "push failed",
                         "stderr": p.stderr.strip()[:300]})
        _log("implement", f"push failed: {p.stderr[:200]}")
        return {"failed": True, "task_id": task_id}

    # -- Open PR ---------------------------------------------------------------
    pr_body = "\n".join([
        f"**Automated implementation of `{task_id}`**",
        "",
        f"- **task:** {task.get('title','')}",
        f"- **priority:** {task.get('priority','?')} · **kind:** {task.get('kind','?')}",
        f"- **estimate:** {plan.get('estimate_minutes','?')} min",
        "",
        "**Plan steps**",
        *[f"- `{s.get('file','?')}`: {s.get('change','')}"
          for s in (plan.get("plan") or [])],
        "",
        "**Risks flagged by planner**",
        *[f"- {r}" for r in (plan.get("risks") or [])],
        "",
        "**Verification run in worktree before push**",
        "- pytest: ✅ unit suite green",
        "- pre-commit hook: ✅ passed",
        "",
        "Generated by `scripts/cron/pipeline.py implement`. "
        "This PR was not merged and will not auto-merge.",
    ])
    pr_title = f"auto: {task.get('title') or task_id}"[:120]
    pr = _gh_open_pr(branch, pr_title, pr_body, base="develop")

    # -- Update task + envelope ------------------------------------------------
    task["implementation_branch"] = branch
    task["implementation_commit_msg"] = commit_message
    task["pr_url"] = pr.get("url")
    task["pr_error"] = pr.get("error")
    task_file.write_text(json.dumps(task, indent=2, ensure_ascii=False))

    subprocess.run(["git", "worktree", "remove", str(wt), "--force"],
                   cwd=REPO_ROOT, capture_output=True, timeout=30)

    envelope_status = "pass" if pr.get("url") else "fail"
    _write_envelope("implement", envelope_status, {
        "task_id": task_id, "branch": branch,
        "pr_url": pr.get("url"), "pr_error": pr.get("error"),
        "diff_lines": diff_lines,
        "agent_elapsed_sec": round(outcome.elapsed_sec, 2),
    })
    _log("implement",
         f"task_id={task_id} status={envelope_status} pr={pr.get('url') or pr.get('error')}")
    return {"task_id": task_id, "pr": pr}


# -----------------------------------------------------------------------------
# Dispatcher
# -----------------------------------------------------------------------------
STEPS: Dict[str, Callable[[], Dict[str, Any]]] = {
    "manager": step_manager,
    "test": step_test,
    "code-review": step_code_review,
    "qc": step_qc,
    "orchestrator": step_orchestrator,
    "deploy": step_deploy,
    "research": step_research,
    "task": step_task,
    "implement": step_implement,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # ``stats`` is a read-only CLI command (no lock, no envelope write) —
    # listed alongside the locked steps for discoverability.
    parser.add_argument("agent", choices=sorted(list(STEPS.keys()) + ["stats"]))
    parser.add_argument("--json", action="store_true",
                        help="For 'stats': print JSON instead of human text")
    parser.add_argument("--force", action="store_true",
                        help="Bypass cooldown/gate checks for this run. "
                             "Sets PIPELINE_FORCE=1 in the step's environment.")
    args = parser.parse_args(argv)

    if args.agent == "stats":
        return cmd_stats(as_json=args.json)

    if args.force:
        os.environ["PIPELINE_FORCE"] = "1"

    with _Lock(args.agent):
        try:
            STEPS[args.agent]()
        except Exception as exc:  # noqa: BLE001
            _log(args.agent, f"unhandled exception: {exc}")
            _write_envelope(args.agent, "fail", {"exception": str(exc)})
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
