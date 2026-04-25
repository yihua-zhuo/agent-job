"""Thin wrapper around the ``claw`` CLI (ultraworkers/claw-code).

Replaces the previous ``openclaw agent`` shell-out. ``claw`` is a Claude-Code-
style local agent that can be pointed at any OpenAI-compatible endpoint (we
route to the in-cluster ai-gateway running MiniMax-M2.7) and has explicit
per-call control over tool allowlist, permission mode, and model choice.

We invoke it as a one-shot::

    claw --output-format json --model openai/MiniMax-M2.7 \\
         --permission-mode workspace-write \\
         prompt "<prompt text>"

The JSON envelope on stdout looks like::

    {"message": "<think>...</think>actual text",
     "model": "...", "iterations": N,
     "tool_uses": [...], "tool_results": [...],
     "usage": {...}, "estimated_cost": "$..."}

We strip ``<think>...</think>`` blocks, then parse a JSON object out of what
remains (callers ask for ``Reply with ONLY a JSON object ...``).

Credential resolution (in order):

    1. ``OPENAI_API_KEY`` + ``OPENAI_BASE_URL``  — set them in your shell.
    2. ``AI_GATEWAY_MASTER_KEY`` + ``AI_GATEWAY_URL`` — auto-injected on the
       openclaw pod; we translate them to the OPENAI_* names ``claw`` expects.

Environment hooks (all optional):

    CLAW_BIN            Override the binary path (default: discover ``claw`` on
                        PATH, then fall back to the pod-canonical
                        ``/opt/data/home/.local/bin/claw``).
    CLAW_MODEL          Model identifier passed to ``--model``
                        (default: ``openai/MiniMax-M2.7``).
    CLAW_PERMISSION     Permission mode (default: ``workspace-write``).
    CLAW_TIMEOUT        Per-call timeout in seconds (default: 600).
    CLAW_DISABLED       Truthy → bypass the CLI; useful for local dev where
                        the binary or gateway is unreachable.
    OPENCLAW_DISABLED   Honoured for backwards compatibility — same effect.
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
from typing import Any, Dict, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TIMEOUT = int(os.environ.get("CLAW_TIMEOUT",
                                     os.environ.get("OPENCLAW_TIMEOUT", "600")))
DEFAULT_AGENT = os.environ.get("OPENCLAW_AGENT", "main")  # kept for API parity
DEFAULT_MODEL = os.environ.get("CLAW_MODEL", "openai/MiniMax-M2.7")
DEFAULT_PERMISSION = os.environ.get("CLAW_PERMISSION", "workspace-write")

_FALLBACK_CLAW_BIN = "/opt/data/home/.local/bin/claw"


@dataclass
class LLMOutcome:
    """What pipeline.py receives from a single ``claw`` call."""

    ok: bool
    status: str                               # pass | fail | skipped | error
    parsed: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    reason: str = ""                          # populated for skipped/error
    elapsed_sec: float = 0.0


def _claw_bin() -> Optional[str]:
    explicit = os.environ.get("CLAW_BIN")
    if explicit:
        return explicit if Path(explicit).exists() else None
    discovered = shutil.which("claw")
    if discovered:
        return discovered
    if Path(_FALLBACK_CLAW_BIN).exists():
        return _FALLBACK_CLAW_BIN
    return None


def _resolve_credentials(env: Dict[str, str]) -> Optional[str]:
    """Ensure ``env`` has OPENAI_API_KEY + OPENAI_BASE_URL; return error or None.

    Mutates ``env`` in place — fills in OPENAI_* from AI_GATEWAY_* when the
    direct vars are unset (this is how the pod is configured).
    """
    api_key = env.get("OPENAI_API_KEY") or env.get("AI_GATEWAY_MASTER_KEY")
    base_url = env.get("OPENAI_BASE_URL") or env.get("AI_GATEWAY_URL")
    if not api_key:
        return ("missing OPENAI_API_KEY (and AI_GATEWAY_MASTER_KEY fallback)"
                " — cannot call claw")
    if not base_url:
        return ("missing OPENAI_BASE_URL (and AI_GATEWAY_URL fallback)"
                " — cannot call claw")
    env["OPENAI_API_KEY"] = api_key
    env["OPENAI_BASE_URL"] = base_url
    return None


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    return _THINK_BLOCK.sub("", text or "").strip()


def _extract_reply_text(cli_stdout: str) -> str:
    """Pull the assistant text out of ``claw --output-format json`` output."""
    try:
        data = json.loads(cli_stdout)
    except json.JSONDecodeError:
        return cli_stdout  # already plain text
    if isinstance(data, dict):
        if "error" in data:
            return f"[claw error] {data.get('error')}"
        msg = data.get("message")
        if isinstance(msg, str):
            return _strip_thinking(msg)
    return cli_stdout


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
    agent: str = DEFAULT_AGENT,                 # kept for API parity (ignored)
    timeout: int = DEFAULT_TIMEOUT,
    thinking: str = "low",                       # kept for API parity (ignored)
    model: str = DEFAULT_MODEL,
    permission_mode: str = DEFAULT_PERMISSION,
    allowed_tools: Optional[Iterable[str]] = None,
    cwd: Optional[Path] = None,
) -> LLMOutcome:
    """Ask ``claw`` and parse a JSON reply.

    The caller is expected to include a brief "reply in JSON matching this
    schema: {...}" instruction in ``prompt`` so the reply is machine-readable.
    We still fall back to a best-effort JSON extraction if the agent wraps
    its answer in prose, ``<think>`` blocks, or code fences.

    ``agent`` and ``thinking`` are accepted for backwards compatibility with
    the previous ``openclaw agent`` wrapper but have no direct claw equivalent.
    """
    del agent, thinking  # API-parity stubs

    if os.environ.get("CLAW_DISABLED") or os.environ.get("OPENCLAW_DISABLED"):
        return LLMOutcome(ok=False, status="skipped",
                          reason="CLAW_DISABLED / OPENCLAW_DISABLED is set")

    binary = _claw_bin()
    if not binary:
        return LLMOutcome(ok=False, status="skipped",
                          reason="claw binary not found on PATH or pod fallback")

    env = os.environ.copy()
    cred_err = _resolve_credentials(env)
    if cred_err:
        return LLMOutcome(ok=False, status="skipped", reason=cred_err)

    cmd = [
        binary,
        "--output-format", "json",
        "--model", model,
        "--permission-mode", permission_mode,
    ]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    cmd += ["prompt", prompt]

    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout + 30,  # grace window over our own timeout
            cwd=str(cwd or REPO_ROOT),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return LLMOutcome(ok=False, status="error",
                          reason=f"subprocess timeout after {timeout + 30}s",
                          elapsed_sec=time.monotonic() - started)
    elapsed = time.monotonic() - started

    if proc.returncode != 0:
        return LLMOutcome(
            ok=False, status="error",
            reason=f"claw exited {proc.returncode}: "
                   f"{(proc.stderr or proc.stdout).strip()[:200]}",
            elapsed_sec=elapsed,
        )

    reply = _extract_reply_text(proc.stdout)
    if reply.startswith("[claw error]"):
        return LLMOutcome(ok=False, status="error",
                          reason=reply, raw_text=proc.stdout,
                          elapsed_sec=elapsed)

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
