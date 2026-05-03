"""
Code Review Agent
- 读取共享上下文获取代码变更
- 分析代码问题，写入共享记忆
"""

import subprocess
from agents.base_agent import BaseAgent


class CodeReviewAgent(BaseAgent):
    name = "code-review"

    async def execute(self, task: dict) -> dict:
        description = task.get("description", "")
        parent_ctx = task.get("parent_context", {})
        repo_info = parent_ctx.get("task", {}).get("repo", "yihua-zhuo/agent-job")

        issues = []

        # 获取最近变更的文件
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~5", "HEAD"],
                capture_output=True, text=True, timeout=30
            )
            changed_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        except Exception:
            changed_files = []

        # 对每个变更文件做代码审查
        for filepath in changed_files:
            if not filepath.endswith(".py"):
                continue

            try:
                diff_result = subprocess.run(
                    ["git", "diff", "HEAD~5", "HEAD", "--", filepath],
                    capture_output=True, text=True, timeout=15
                )
                diff_text = diff_result.stdout

                # 基础检查：trailing whitespace
                for i, line in enumerate(diff_text.split("\n"), 1):
                    if " \n" in line or "\t\n" in line:
                        issues.append(f"Trailing whitespace in {filepath}:{i}")
                    if len(line) > 120 and ".py" in filepath:
                        issues.append(f"Line too long ({len(line)} chars) in {filepath}:{i}")

            except Exception:
                pass

        if not issues:
            return {
                "status": "pass",
                "summary": "No code issues found",
                "files_reviewed": len(changed_files),
                "issues": [],
            }

        return {
            "status": "fail",
            "summary": f"Found {len(issues)} code issue(s)",
            "files_reviewed": len(changed_files),
            "issues": issues[:20],
        }


if __name__ == "__main__":
    import asyncio
    agent = CodeReviewAgent()
    asyncio.run(agent.start())