"""
QC Agent — 质量控制
- 读取 code-review 和 test 的共享记忆结果
- 综合判断是否通过 quality gate
"""

import os
import subprocess
from agents.base_agent import BaseAgent


class QCAgent(BaseAgent):
    name = "qc"

    async def execute(self, task: dict) -> dict:
        parent_ctx = task.get("parent_context", {})
        parent_id = task.get("parent_id", "")
        repo_path = os.environ.get("REPO_PATH", "/home/node/.openclaw/workspace/dev-agent-system")

        # 读取其他 Agent 的结果
        shared_memory = await self._get_shared_memory(parent_id)
        review_issues = []
        test_passed = None

        for entry in shared_memory:
            if entry.get("author") == "code-review":
                result = entry.get("result", {})
                if result.get("status") == "fail":
                    review_issues = result.get("issues", [])
            elif entry.get("author") == "test":
                result = entry.get("result", {})
                test_passed = result.get("status") == "pass"

        checks = []
        warnings = []

        # 1. lint 检查
        try:
            lint_result = subprocess.run(
                ["python", "-m", "flake8", "src/", "--select=E9,F63,F7,F82", "--count"],
                capture_output=True, text=True, timeout=60, cwd=repo_path
            )
            lint_ok = lint_result.returncode == 0
            lint_count = lint_result.stdout.strip().split("\n")[-1] if lint_result.stdout else "0"
            checks.append(f"flake8 (E9,F63,F7,F82): {'✅' if lint_ok else '❌'} ({lint_count} errors)")
        except Exception as e:
            warnings.append(f"flake8 check failed: {e}")

        # 2. 类型检查
        try:
            mypy_result = subprocess.run(
                ["python", "-m", "mypy", "src/", "--ignore-missing-imports", "--no-error-summary"],
                capture_output=True, text=True, timeout=120, cwd=repo_path
            )
            mypy_ok = mypy_result.returncode == 0
            mypy_errors = len([l for l in mypy_result.stdout.split("\n") if "error:" in l])
            checks.append(f"mypy: {'✅' if mypy_ok else '⚠️'} ({mypy_errors} type errors)")
        except Exception:
            warnings.append("mypy check unavailable")

        # 3. 覆盖率检查（如果 coverage 文件存在）
        try:
            cov_file = f"{repo_path}/coverage/coverage-summary.json"
            if os.path.exists(cov_file):
                import json as _json
                with open(cov_file) as f:
                    cov_data = _json.load(f)
                cov_pct = cov_data.get("percent_covered", 0)
                checks.append(f"coverage: {'✅' if cov_pct >= 70 else '⚠️'} ({cov_pct:.1f}%)")
        except Exception:
            pass

        # 综合判断
        all_pass = test_passed and not review_issues

        return {
            "status": "pass" if all_pass else "fail",
            "summary": "QC gate passed" if all_pass else "QC gate failed",
            "checks": checks,
            "warnings": warnings,
            "review_issues_count": len(review_issues),
            "test_passed": test_passed,
        }

    async def _get_shared_memory(self, parent_id: str) -> list:
        from shared_memory import MemoryStore
        all_memory = await MemoryStore.get_shared_memory(limit=100)
        return [m for m in all_memory if m.get("parent_id") == parent_id]


if __name__ == "__main__":
    import asyncio
    agent = QCAgent()
    asyncio.run(agent.start())