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
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

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
# Steps
# -----------------------------------------------------------------------------
def step_manager() -> Dict[str, Any]:
    """Heartbeat — snapshot every envelope. No LLM call."""
    snapshot: Dict[str, Any] = {}
    for envelope_file in sorted(RESULTS_DIR.glob("*-result.json")):
        try:
            data = json.loads(envelope_file.read_text())
        except json.JSONDecodeError:
            continue
        snapshot[data.get("agent", envelope_file.stem)] = {
            "status": data.get("status"),
            "generated_at": data.get("generated_at"),
        }
    pending_tasks = sorted(p.name for p in TASKS_DIR.glob("*.json"))
    details = {"agents": snapshot, "pending_tasks": pending_tasks}
    _write_envelope("manager", "pass", details)
    _log("manager", f"snapshot: {len(snapshot)} agents, {len(pending_tasks)} tasks")
    return details


def step_test() -> Dict[str, Any]:
    """Run pytest. The pass/fail signal is binary — no need for an LLM."""
    try:
        proc = _run(
            ["python3", "-m", "pytest", "tests/unit", "-q",
             "--ignore=tests/unit/test_user_service.py",
             "--ignore=tests/unit/test_import_export_service.py"],
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
    """Gate on test green, grab the diff, ask openclaw to judge it."""
    if not _is_green_today("test"):
        _write_envelope("code-review", "skipped", {"reason": "test not green in last 24h"})
        _log("code-review", "test not green; skipping")
        return {"skipped": True}

    diff_proc = _run(["git", "diff", "HEAD~1..HEAD"], "code-review", timeout=30)
    diff = diff_proc.stdout or ""
    # Hard cap the prompt size so huge refactors don't blow the context window.
    MAX_DIFF = 60_000
    if len(diff) > MAX_DIFF:
        diff = diff[:MAX_DIFF] + f"\n\n...[truncated {len(diff) - MAX_DIFF} chars]"

    prompt = compose_prompt(
        role="code-review",
        task=(
            "Review the git diff across the four dimensions in your SOUL: "
            "quality, security, performance, architecture. "
            "Set status=\"pass\" ONLY if there are zero critical-severity issues."
        ),
        data=diff if diff.strip() else "(no diff - HEAD matches HEAD~1)",
        schema=(
            '{"status": "pass"|"fail", '
            '"critical": [{"dim": str, "line": int|null, "msg": str}], '
            '"warnings": [str], "suggestions": [str], "summary": str}'
        ),
    )
    outcome = ask_agent(prompt, thinking="medium")
    _envelope_from_llm("code-review", outcome, local_data={"diff_chars": len(diff)})
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
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent", choices=sorted(STEPS.keys()))
    args = parser.parse_args(argv)

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
