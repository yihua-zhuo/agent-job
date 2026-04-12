#!/usr/bin/env python3
"""
Test Agent - Executes unit and integration tests
Handles test discovery, execution, and reporting
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

class TestAgent:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.test_results: List[Dict] = []

    def discover_tests(self, test_path: str = "tests") -> List[str]:
        """Discover all tests in the given path"""
        path = self.workspace / test_path
        tests = []
        for ext in ["test_*.py", "*_test.py"]:
            tests.extend(str(p.relative_to(self.workspace)) for p in path.rglob(ext))
        return tests

    def run_unit_tests(self, test_path: str = "tests/unit") -> Dict:
        """Run unit tests with coverage"""
        result = subprocess.run(
            ["pytest", test_path, "-v", "--cov=src", "--cov-report=json", "--cov-report=term"],
            capture_output=True,
            text=True,
            cwd=self.workspace
        )
        
        return {
            "type": "unit",
            "passed": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr,
            "returncode": result.returncode
        }

    def run_integration_tests(self, test_path: str = "tests/integration") -> Dict:
        """Run integration tests"""
        result = subprocess.run(
            ["pytest", test_path, "-v", "-m", "integration"],
            capture_output=True,
            text=True,
            cwd=self.workspace
        )
        
        return {
            "type": "integration",
            "passed": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr,
            "returncode": result.returncode
        }

    def run_all_tests(self) -> Dict:
        """Run full test suite"""
        results = {
            "unit": self.run_unit_tests(),
            "integration": self.run_integration_tests(),
            "overall_pass": False
        }
        results["overall_pass"] = results["unit"]["passed"] and results["integration"]["passed"]
        return results

    def generate_report(self, results: Dict) -> str:
        """Generate test execution report"""
        report = ["## Test Execution Report\n"]
        report.append(f"### Unit Tests: {'✓ PASSED' if results['unit']['passed'] else '✗ FAILED'}")
        report.append(f"### Integration Tests: {'✓ PASSED' if results['integration']['passed'] else '✗ FAILED'}")
        report.append(f"\n### Overall: {'PASS' if results['overall_pass'] else 'FAIL'}")
        return "\n".join(report)

def main():
    test_agent = TestAgent(Path("/home/node/.openclaw/workspace/dev-agent-system"))
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "discover":
            tests = test_agent.discover_tests()
            print(json.dumps(tests, indent=2))
        elif sys.argv[1] == "unit":
            result = test_agent.run_unit_tests()
            print(json.dumps(result, indent=2))
        elif sys.argv[1] == "integration":
            result = test_agent.run_integration_tests()
            print(json.dumps(result, indent=2))
        elif sys.argv[1] == "all":
            result = test_agent.run_all_tests()
            print(json.dumps(result, indent=2))
    else:
        result = test_agent.run_all_tests()
        print(test_agent.generate_report(result))

if __name__ == "__main__":
    main()