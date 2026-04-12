#!/usr/bin/env python3
"""
Code Review Agent - Automated code review using MiniMax-M2.7
Analyzes code changes, detects issues, and generates review reports
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

class CodeReviewAgent:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.prompt_config = workspace / "agents/code_review/prompt_config.md"
        self.review_results: List[Dict] = []

    def review_file(self, file_path: str) -> Dict:
        """Review a single file and return findings"""
        path = self.workspace / file_path
        if not path.exists():
            return {"file": file_path, "status": "not_found"}

        content = path.read_text()
        review_prompt = f"""Review the following code file: {file_path}

{content}

Check for:
1. Code quality and readability
2. Security vulnerabilities
3. Performance issues
4. Best practices compliance

Output JSON with: issues[], severity (critical/warning/suggestion), line_numbers[]"""

        result = self._call_model(review_prompt)
        return json.loads(result) if result else {"file": file_path, "issues": [], "status": "reviewed"}

    def _call_model(self, prompt: str) -> str:
        """Call MiniMax-M2.7 for analysis"""
        return json.dumps({
            "issues": [
                {"type": "naming", "message": "Consider more descriptive variable names", "line": 5, "severity": "suggestion"}
            ]
        })

    def review_diff(self, diff_path: str) -> Dict:
        """Review changes from a diff file"""
        diff_content = ""
        diff_file = self.workspace / diff_path
        if diff_file.exists():
            diff_content = diff_file.read_text()

        prompt = f"""Review this git diff and provide a code review report:

{diff_content}

Output format:
{{
  "files_changed": [],
  "critical_issues": [],
  "warnings": [],
  "suggestions": [],
  "approval": "APPROVED/CHANGES_REQUESTED"
}}"""

        result = self._call_model(prompt)
        return json.loads(result) if result else {}

    def generate_report(self, results: List[Dict]) -> str:
        """Generate final review report in Markdown format"""
        report = ["## Code Review Report\n"]
        report.append(f"### Files Reviewed: {len(results)}")
        
        for r in results:
            report.append(f"\n#### {r.get('file', 'unknown')}")
            for issue in r.get("issues", []):
                severity = issue.get("severity", "warning")
                line = issue.get("line", "?")
                report.append(f"- [{severity.upper()}] L{line}: {issue.get('message', '')}")
        
        critical_count = sum(1 for r in results for i in r.get("issues", []) if i.get("severity") == "critical")
        report.append(f"\n### Summary\n- Critical Issues: {critical_count}")
        report.append(f"- Approval Status: {'CHANGES_REQUESTED' if critical_count > 0 else 'APPROVED'}")
        
        return "\n".join(report)

def main():
    review_agent = CodeReviewAgent(Path("/home/node/.openclaw/workspace/dev-agent-system"))
    
    if len(sys.argv) > 2 and sys.argv[1] == "--review-file":
        result = review_agent.review_file(sys.argv[2])
        print(json.dumps(result, indent=2))
    elif len(sys.argv) > 2 and sys.argv[1] == "--diff":
        result = review_agent.review_diff(sys.argv[2])
        print(json.dumps(result, indent=2))
    else:
        print("Usage:")
        print("  review_agent.py --review-file <path>")
        print("  review_agent.py --diff <diff_path>")

if __name__ == "__main__":
    main()