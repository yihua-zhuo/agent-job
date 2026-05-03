"""
Supervisor Agent — 主编排器

职责：
1. 接收用户任务（通过 Telegram 或直接调用）
2. 将任务分解为多个子任务，提交到 SharedMemory（GitHub Issues）
3. 轮询所有子任务的完成状态
4. 汇总结果，报告给用户
"""

import asyncio
import os
import time
import json
import sys

from shared_memory import get_shared_memory, SharedMemory, Task


# ─── Supervisor 专属 Agent 名 ─────────────────────────────────────────────────

SUPERVISOR_NAME = "supervisor"
SUB_AGENTS = ["code-review", "test", "qc", "deploy"]


async def decompose_task(task_description: str) -> list[dict]:
    """
    将大任务分解为子任务。
    固定流程：code-review → test → qc → deploy
    """
    sub_tasks = [
        {
            "description": f"[Code Review] {task_description}",
            "agent": "code-review",
        },
        {
            "description": f"[Test] {task_description}",
            "agent": "test",
        },
        {
            "description": f"[QC] {task_description}",
            "agent": "qc",
        },
        {
            "description": f"[Deploy] {task_description}",
            "agent": "deploy",
        },
    ]
    return sub_tasks


async def wait_for_subtasks(sm: SharedMemory, parent_id: str, timeout: int = 300) -> dict:
    """
    轮询等待所有子任务完成。
    超时返回已完成的 + 超时未完成的。
    """
    start = time.time()
    completed = {}
    pending = set()

    while time.time() - start < timeout:
        # 读取父任务的 comments 获取各 Agent 结果
        # 找 parent task issue
        parent_task = await sm.get_task(parent_id)
        if not parent_task:
            await asyncio.sleep(3)
            continue

        comments = await sm.read_task_comments(parent_task.issue_number)

        # 从 comments 提取已完成的任务
        for c in comments:
            if isinstance(c, dict) and "author" in c:
                agent = c.get("author")
                if agent in SUB_AGENTS and agent not in completed:
                    status = c.get("content", {}).get("status", "unknown")
                    completed[agent] = status
                    pending.discard(agent)

        # 检查是否全部完成
        still_pending = [a for a in SUB_AGENTS if a not in completed]
        if not still_pending:
            break

        await asyncio.sleep(3)

    # 最终状态
    final = {}
    for agent in SUB_AGENTS:
        final[agent] = completed.get(agent, "timeout/not_started")
    return final


async def report_to_telegram(chat_id: str, text: str) -> None:
    """通过 Telegram Bot 发送消息"""
    import aiohttp
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print(f"[Telegram] No token, skipping: {text[:80]}")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                pass  # ignore result
    except Exception as e:
        print(f"[Telegram] Send failed: {e}")


async def main():
    """Supervisor 主入口：接收任务 → 分解 → 分发 → 等待 → 报告"""
    sm = get_shared_memory()
    print("[Supervisor] Ready. Waiting for tasks...")

    # 加载 Telegram chat_id
    ADMIN_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1680424782")

    while True:
        try:
            # 轮询 supervisor 自己被分配的任务
            tasks = await sm.get_pending_tasks(agent=SUPERVISOR_NAME)

            if not tasks:
                await asyncio.sleep(3)
                continue

            task = tasks[0]
            print(f"[Supervisor] Got task: {task.description[:80]}")
            await sm.claim_task(task)

            # 写入全局上下文，供子 Agent 使用
            await sm.write_context("current_task", {
                "task_id": task.task_id,
                "description": task.description,
                "submitted_at": task.created_at,
            })

            # 分解任务
            sub_tasks = await decompose_task(task.description)

            # 提交子任务到 SharedMemory
            sub_task_ids = []
            for st in sub_tasks:
                sub = await sm.submit_task(
                    description=st["description"],
                    agent=st["agent"],
                    parent_id=task.task_id,
                    context={"parent_issue": task.issue_number},
                )
                sub_task_ids.append((st["agent"], sub.task_id))
                print(f"[Supervisor] Subtask submitted: {st['agent']} → {sub.task_id}")

            # 等待所有子任务完成
            await report_to_telegram(ADMIN_CHAT_ID,
                f"🔄 开始处理：{task.description[:60]}...\n"
                f"已分发 {len(sub_tasks)} 个子任务，等待完成..."
            )

            results = await wait_for_subtasks(sm, task.task_id, timeout=600)

            # 汇总报告
            lines = [f"✅ 任务完成：<b>{task.description[:80]}</b>\n"]
            for agent, status in results.items():
                icon = "✅" if status == "pass" else "❌" if status == "fail" else "⏳"
                lines.append(f"{icon} <b>{agent}</b>: {status}")

            report = "\n".join(lines)
            print(f"[Supervisor] Report:\n{report}")
            await report_to_telegram(ADMIN_CHAT_ID, report)

            # 标记完成
            await sm.complete_task(task, {"subtask_results": results})
            await report_to_telegram(ADMIN_CHAT_ID, f"🏁 全部完成，任务 {task.task_id} 已归档。")

        except Exception as e:
            print(f"[Supervisor] Error: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())