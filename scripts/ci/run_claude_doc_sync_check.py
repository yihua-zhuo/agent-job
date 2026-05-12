#!/usr/bin/env python3
"""Run a scheduled Claude check for documentation drift."""

import json
import os
import subprocess
import sys
from json import JSONDecoder
from typing import Any


def build_prompt() -> str:
    return """You are a senior engineer checking whether repository documentation is out of sync
with the current codebase.

Inspect the current repository. Compare documentation against source code, configs,
workflows, scripts, and frontend files.

Documentation scope:
- README.md
- CLAUDE.md
- docs/**/*.md
- frontend/README.md
- frontend/AGENTS.md
- frontend/CLAUDE.md

Rules:
- Do not modify files.
- Report only materially stale or incorrect documentation: commands, paths, APIs,
  workflows, environment variables, deployment instructions, architecture claims,
  data schemas, or feature behavior that conflicts with current code.
- Ignore wording/style issues and missing documentation unless an existing document makes an incorrect claim.
- Use concrete file/path evidence from the repository.

Respond with only a JSON object using this schema:
{
  "status": "pass" | "fail",
  "out_of_sync": [
    {
      "doc_path": "path/to/doc.md",
      "claim": "documented claim that is stale",
      "current_reality": "what the code/config currently does",
      "evidence": ["code/path.py", ".github/workflows/name.yml"],
      "suggested_update": "specific documentation change"
    }
  ],
  "checked_documents": ["README.md"],
  "summary": "one sentence"
}

Set status="fail" if out_of_sync is non-empty. Set status="pass" only when no material documentation drift is found."""


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    decoder = JSONDecoder()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, str):
            try:
                return extract_json_object(result)
            except ValueError:
                pass
        return data

    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data

    raise ValueError("No JSON object found in Claude output")


def normalize_result(raw_output: str) -> dict[str, Any]:
    try:
        data = extract_json_object(raw_output)
    except ValueError as e:
        return {
            "status": "fail",
            "out_of_sync": [],
            "checked_documents": [],
            "summary": f"Failed to parse Claude output: {e}",
            "raw": raw_output[-2000:],
        }

    has_status = "status" in data
    has_out_of_sync = "out_of_sync" in data
    out_of_sync = data.get("out_of_sync", [])
    if out_of_sync is None:
        out_of_sync = []
    elif not isinstance(out_of_sync, list):
        out_of_sync = [out_of_sync]

    status = data.get("status")
    if not has_status and not has_out_of_sync:
        status = "fail"
    elif status not in {"pass", "fail"}:
        status = "fail" if out_of_sync else "pass"
    elif out_of_sync:
        status = "fail"

    data["status"] = status
    data["out_of_sync"] = out_of_sync
    data.setdefault("checked_documents", [])
    data.setdefault("summary", "")
    return data


def main() -> int:
    output_path = os.environ.get("DOC_SYNC_RESULT_PATH", "artifacts/doc-sync-result.json")
    raw_output_path = os.environ.get("CLAUDE_DOC_SYNC_OUTPUT_PATH", "/tmp/claude-doc-sync-output.txt")
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    timeout_seconds = int(os.environ.get("CLAUDE_DOC_SYNC_TIMEOUT_SECONDS", "900"))

    cmd = [
        "claude",
        "-p",
        "--model",
        model,
        "--max-turns",
        "100",
        "--output-format",
        "json",
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as e:
        raw_output = f"{e}\n"
        result = {
            "status": "fail",
            "out_of_sync": [],
            "checked_documents": [],
            "summary": "Claude documentation sync check could not start.",
            "raw": raw_output,
        }
    else:
        timed_out = False
        try:
            raw_output, _ = process.communicate(build_prompt(), timeout=timeout_seconds)
        except subprocess.TimeoutExpired as e:
            timed_out = True
            process.kill()
            tail_output, _ = process.communicate()
            raw_output = (e.output or "") + (tail_output or "")
        result = normalize_result(raw_output)
        if timed_out:
            result["status"] = "fail"
            result["summary"] = "Claude documentation sync check timed out."
        if process.returncode != 0 and result.get("status") == "pass":
            result["status"] = "fail"
            result["summary"] = "Claude documentation sync check exited non-zero."

    sys.stdout.write(raw_output)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    raw_dir = os.path.dirname(raw_output_path)
    if raw_dir:
        os.makedirs(raw_dir, exist_ok=True)
    with open(raw_output_path, "w") as f:
        f.write(raw_output)

    # Always exit 0 — drift is reported via a GitHub Issue (see create_doc_sync_issue.py),
    # not by failing the pipeline. The result file's "status" field still records
    # pass/fail so downstream consumers can branch on it.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
