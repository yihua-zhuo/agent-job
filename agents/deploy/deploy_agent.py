"""
Deploy Agent
- 验证所有 gate 通过后执行部署
- 写入部署日志到共享记忆
"""

import subprocess
from agents.base_agent import BaseAgent


class DeployAgent(BaseAgent):
    name = "deploy"

    async def execute(self, task: dict) -> dict:
        parent_ctx = task.get("parent_context", {})
        parent_id = task.get("parent_id", "")
        repo_path = "/home/node/.openclaw/workspace/dev-agent-system"

        # 读取前置 Agent 结果
        shared = await self._get_shared_memory(parent_id)
        test_passed = None
        review_issues = 0

        for entry in shared:
            if entry.get("author") == "test":
                test_passed = entry.get("result", {}).get("status") == "pass"
            elif entry.get("author") == "code-review":
                review_issues = len(entry.get("result", {}).get("issues", []))

        if not test_passed:
            return {
                "status": "fail",
                "summary": "Deploy blocked: tests not passed",
                "gates": {"test": False, "review": review_issues == 0},
            }

        if review_issues > 0:
            return {
                "status": "fail",
                "summary": f"Deploy blocked: {review_issues} code review issues remain",
                "gates": {"test": True, "review": False},
            }

        # 执行部署
        try:
            # 示例：git push + Railway 部署
            # 实际部署命令根据项目配置
            result = subprocess.run(
                ["git", "push", "origin", "HEAD", "--force"],
                capture_output=True, text=True, timeout=60, cwd=repo_path
            )

            if result.returncode == 0:
                return {
                    "status": "pass",
                    "summary": "Deploy triggered successfully",
                    "gates": {"test": True, "review": True},
                    "output": result.stdout.strip()[-500:],
                }
            else:
                return {
                    "status": "fail",
                    "summary": f"Deploy failed: {result.stderr.strip()[:200]}",
                    "gates": {"test": True, "review": True},
                }
        except Exception as e:
            return {
                "status": "fail",
                "summary": f"Deploy error: {str(e)[:200]}",
                "gates": {"test": True, "review": True},
            }

    async def _get_shared_memory(self, parent_id: str) -> list:
        from shared_memory import MemoryStore
        all_memory = await MemoryStore.get_shared_memory(limit=100)
        return [m for m in all_memory if m.get("parent_id") == parent_id]


if __name__ == "__main__":
    import asyncio
    agent = DeployAgent()
    asyncio.run(agent.start())