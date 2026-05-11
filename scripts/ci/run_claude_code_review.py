#!/usr/bin/env python3
"""Run Claude code review and capture its output for later parsing."""

import os
import subprocess
import sys


def build_prompt(diff: str, head: str, base: str) -> str:
    return f"""You are a senior engineer. Review the following diff between origin/master and origin/develop.
The commit being reviewed: {head} (base: {base}).

diff:
{diff}

Respond with a JSON object:
{{
  "verdict": "pass" | "fail",
  "critical_issues": ["list of critical bugs, security issues, or regressions"],
  "suggestions": ["minor improvements"],
  "summary": "one sentence overall assessment"
}}

Only set verdict=pass if there are ZERO critical-severity issues."""


def main() -> None:
    diff_path = os.environ.get("DIFF_FILE", "/tmp/pr-diff.txt")
    output_path = os.environ.get("CLAUDE_OUTPUT_PATH", "/tmp/claude-output.txt")
    head = os.environ.get("HEAD_INFO", "")
    base = os.environ.get("BASE_INFO", "")
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    with open(diff_path) as f:
        diff = f.read()

    prompt = build_prompt(diff, head, base)
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

    with open(output_path, "w") as out:
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as e:
            message = f"{e}\n"
            sys.stdout.write(message)
            out.write(message)
            return

        output, _ = process.communicate(prompt)
        sys.stdout.write(output)
        out.write(output)


if __name__ == "__main__":
    main()
