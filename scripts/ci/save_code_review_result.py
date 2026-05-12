#!/usr/bin/env python3
"""Parse Claude code-review output and save the structured result."""

import json
import os


def main() -> None:
    input_path = os.environ.get("CLAUDE_OUTPUT_PATH", "/tmp/claude-output.txt")
    output_path = os.environ.get(
        "CODE_REVIEW_RESULT_PATH",
        "shared-memory/results/code-review-result.json",
    )

    with open(input_path) as f:
        text = f.read()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        idx = text.rfind("{")
        data = json.loads(text[idx:])
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        with open(output_path, "w") as f:
            json.dump({"error": str(e), "raw": text[-500:]}, f)


if __name__ == "__main__":
    main()
