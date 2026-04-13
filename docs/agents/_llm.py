"""Thin wrapper around the real ``openclaw agent`` CLI.

The ``main`` agent lives in ``/home/node/.openclaw/workspace`` inside the
k8s pod and is backed by ai-gateway/MiniMax-M2.7. We invoke it as:

    openclaw agent --agent <id> --message <prompt> --json --timeout <sec>

and parse the structured reply. The agent itself does NOT have shell or
filesystem tools by default — the cron (``scripts/cron/pipeline.py``) runs
the local work (pytest, git diff, ruff) and passes the raw output in the
prompt. The agent's job is *judgement*: deciding whether a diff is safe,
whether QC signals a release-blocker, etc.

Environment hooks (all optional):

    OPENCLAW_BIN        Override the binary name (default: ``openclaw``).
    OPENCLAW_AGENT      Which configured agent to route to (default: ``main``).
    OPENCLAW_TIMEOUT    Per-call timeout in seconds (default: 600).
    OPENCLAW_DISABLED   Set to any truthy value to bypass the CLI entirely;
                        useful in local dev where the binary is absent.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TIMEOUT = int(os.environ.get("OPENCLAW_TIMEOUT", "600"))
DEFAULT_AGENT = os.environ.get("OPENCLAW_AGENT", "main")


@dataclass
class LLMOutcome:
    """What pipeline.py receives from a single ``openclaw agent`` call."""

    ok: bool
    status: str                               # pass | fail | skipped | error
    parsed: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    reason: str = ""                          # populated for skipped/error
    elapsed_sec: float = 0.0


def _openclaw_bin() -> Optional[str]:
    return shutil.which(os.environ.get("OPENCLAW_BIN", "openclaw"))


def _extract_reply_text(cli_stdout: str) -> str:
    """Pull the agent reply text out of ``openclaw agent --json`` output.

    The shape is::

        { "result": { "payloads": [{"text": "...", "mediaUrl": null}, ...], ... } }

    We concatenate all text payloads in order so multi-part replies still
    round-trip cleanly.
    """
    try:
        data = json.loads(cli_stdout)
    except json.JSONDecodeError:
        return cli_stdout  # already plain text

    result = data.get("result") or {}
    payloads = result.get("payloads") or []
    parts = [p.get("text", "") for p in payloads if isinstance(p, dict)]
    joined = "\n".join(part for part in parts if part)
    return joined or cli_stdout


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parse_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Accept either raw JSON or a JSON object inside a ```json fence."""
    text = (text or "").strip()
    if not text:
        return None

    for candidate in (text, *_JSON_FENCE.findall(text)):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    # Last resort: find the first {...} span that parses cleanly.
    start = text.find("{")
    while start != -1:
        end = text.rfind("}")
        if end == -1 or end <= start:
            break
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        start = text.find("{", start + 1)
    return None


def ask_agent(
    prompt: str,
    *,
    agent: str = DEFAULT_AGENT,
    timeout: int = DEFAULT_TIMEOUT,
    thinking: str = "low",
) -> LLMOutcome:
    """Ask the configured OpenClaw agent a question and parse a JSON reply.

    The caller is expected to include a brief "reply in JSON matching this
    schema: {...}" instruction in ``prompt`` so the reply is machine-readable.
    We still fall back to a best-effort JSON extraction if the agent wraps
    its answer in prose or code fences.
    """
    if os.environ.get("OPENCLAW_DISABLED"):
        return LLMOutcome(ok=False, status="skipped",
                          reason="OPENCLAW_DISABLED is set")

    binary = _openclaw_bin()
    if not binary:
        return LLMOutcome(ok=False, status="skipped",
                          reason="openclaw binary not on PATH")

    cmd = [
        binary, "agent",
        "--agent", agent,
        "--message", prompt,
        "--json",
        "--thinking", thinking,
        "--timeout", str(timeout),
    ]

    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout + 30,  # give the CLI a grace window over --timeout
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return LLMOutcome(ok=False, status="error",
                          reason=f"subprocess timeout after {timeout + 30}s",
                          elapsed_sec=time.monotonic() - started)
    elapsed = time.monotonic() - started

    if proc.returncode != 0:
        return LLMOutcome(
            ok=False, status="error",
            reason=f"openclaw exited {proc.returncode}: {proc.stderr.strip()[:200]}",
            elapsed_sec=elapsed,
        )

    reply = _extract_reply_text(proc.stdout)
    parsed = _parse_json_block(reply) or {}
    status = str(parsed.get("status", "")).lower()
    if status not in {"pass", "fail", "skipped"}:
        status = "fail" if not parsed else "pass"

    return LLMOutcome(
        ok=(status == "pass"),
        status=status,
        parsed=parsed,
        raw_text=reply,
        elapsed_sec=elapsed,
    )


def soul_for(role: str) -> str:
    """Load the SOUL.md for a given role, if present."""
    candidates = [
        REPO_ROOT / "docs" / "agents" / f"{role}-agent" / "SOUL.md",
        REPO_ROOT / "docs" / "agents" / role / "SOUL.md",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def compose_prompt(role: str, task: str, data: str, schema: str) -> str:
    """Stitch SOUL + role + task + raw data + expected schema into one prompt.

    Keeping this as a single function means pipeline.py never has to
    remember the prompt layout, and any future prompt tweaks live here.
    """
    soul = soul_for(role) or f"(no SOUL.md found for role={role})"
    return "\n\n".join([
        f"[role={role}] You are invoked by cron. Follow your SOUL strictly.",
        "=== SOUL ===",
        soul.strip(),
        "=== TASK ===",
        task.strip(),
        "=== INPUT DATA ===",
        data.strip() or "(no data)",
        "=== OUTPUT CONTRACT ===",
        "Reply with ONLY a JSON object (no prose, no code fences) matching:",
        schema.strip(),
    ])
