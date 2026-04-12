#!/usr/bin/env python3
"""
QC Agent - Quality Control verification before merge
Performs final checks on documentation, compliance, and deployment readiness
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

class QCAgent:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.checks: List[Dict] = []

    def check_documentation(self) -> Dict:
        """Verify required documentation exists"""
        docs = ["README.md", "CONTRIBUTING.md", "docs/"]
        missing = []
        
        for doc in docs:
            if not (self.workspace / doc).exists():
                missing.append(doc)
        
        return {
            "check": "documentation",
            "passed": len(missing) == 0,
            "missing": missing,
            "message": "All documentation present" if not missing else f"Missing: {', '.join(missing)}"
        }

    def check_code_style(self) -> Dict:
        """Run linters and style checkers"""
        result = subprocess.run(
            ["flake8", "src/", "--count", "--select=E9,F63,F7,F82", "--show-source", "--statistics"],
            capture_output=True,
            text=True,
            cwd=self.workspace
        )
        
        return {
            "check": "code_style",
            "passed": result.returncode == 0,
            "errors": result.stdout,
            "message": "Code style check passed" if result.returncode == 0 else "Style issues found"
        }

    def check_type_annotations(self) -> Dict:
        """Verify type hints are present"""
        result = subprocess.run(
            ["mypy", "src/", "--ignore-missing-imports"],
            capture_output=True,
            text=True,
            cwd=self.workspace
        )
        
        return {
            "check": "type_annotations",
            "passed": result.returncode == 0,
            "output": result.stdout,
            "message": "Type checking passed" if result.returncode == 0 else "Type issues found"
        }

    def check_deploy_readiness(self) -> Dict:
        """Verify build and deployment readiness"""
        checks = {
            "build": (subprocess.run(["python3", "-m", "py_compile"] + [str(p) for p in (self.workspace / "src").rglob("*.py")], capture_output=True, cwd=self.workspace).returncode == 0),
            "config": (self.workspace / "pyproject.toml").exists()
        }
        
        return {
            "check": "deploy_readiness",
            "passed": all(checks.values()),
            "details": checks,
            "message": "Ready for deployment" if all(checks.values()) else "Deployment issues"
        }

    def run_all_checks(self) -> Dict:
        """Execute all QC checks"""
        results = {
            "documentation": self.check_documentation(),
            "code_style": self.check_code_style(),
            "type_annotations": self.check_type_annotations(),
            "deploy_readiness": self.check_deploy_readiness()
        }
        
        results["overall_pass"] = all(r["passed"] for r in results.values())
        return results

    def generate_report(self, results: Dict) -> str:
        """Generate QC report"""
        report = ["## QC Report\n"]
        
        for check, result in results.items():
            if check == "overall_pass":
                continue
            status = "✓" if result["passed"] else "✗"
            report.append(f"- {status} {check}: {result['message']}")
        
        overall = "✓ PASS" if results["overall_pass"] else "✗ FAIL"
        report.append(f"\n### Overall: {overall}")
        
        return "\n".join(report)

def main():
    qc_agent = QCAgent(Path("/home/node/.openclaw/workspace/dev-agent-system"))
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            result = qc_agent.run_all_checks()
            print(json.dumps(result, indent=2))
        elif sys.argv[1] == "docs":
            print(json.dumps(qc_agent.check_documentation(), indent=2))
        elif sys.argv[1] == "style":
            print(json.dumps(qc_agent.check_code_style(), indent=2))
    else:
        result = qc_agent.run_all_checks()
        print(qc_agent.generate_report(result))

if __name__ == "__main__":
    main()