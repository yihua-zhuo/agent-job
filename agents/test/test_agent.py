"""
Test Agent
- 执行单元测试
- 上传测试结果到共享记忆
"""

import os
import subprocess
from agents.base_agent import BaseAgent


class TestAgent(BaseAgent):
    name = "test"

    async def execute(self, task: dict) -> dict:
        parent_ctx = task.get("parent_context", {})
        repo_path = os.environ.get("REPO_PATH", "/home/node/.openclaw/workspace/dev-agent-system")

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short",
                 f"--rootdir={repo_path}"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=repo_path,
                env={**os.environ, "PYTHONPATH": f"{repo_path}/src"}
            )

            passed = result.stdout.count(" PASSED") + result.stdout.count("passed")
            failed = result.stdout.count(" FAILED") + result.stdout.count("failed")

            # 提取失败测试名
            failed_tests = []
            for line in result.stdout.split("\n"):
                if "FAILED" in line:
                    failed_tests.append(line.strip())

            summary = result.stdout.strip().split("\n")[-3:] if result.stdout else []
            summary_text = " | ".join([s.strip() for s in summary if s.strip()])

            if failed > 0:
                return {
                    "status": "fail",
                    "summary": f"{failed} test(s) failed",
                    "passed": passed,
                    "failed": failed,
                    "failed_tests": failed_tests[:10],
                    "output_tail": summary_text,
                }
            else:
                return {
                    "status": "pass",
                    "summary": f"All {passed} tests passed",
                    "passed": passed,
                    "failed": 0,
                }

        except subprocess.TimeoutExpired:
            return {"status": "fail", "summary": "Test execution timed out (>5min)"}
        except Exception as e:
            return {"status": "fail", "summary": f"Test error: {str(e)}"}


if __name__ == "__main__":
    import asyncio
    agent = TestAgent()
    asyncio.run(agent.start())