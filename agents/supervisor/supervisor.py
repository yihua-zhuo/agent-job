"""
Supervisor Agent — 主编排器
负责任务分解、子 Agent 分发、结果聚合、通过 Telegram 向用户报告
"""

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
import redis.asyncio as redis

from shared_memory import MemoryStore, RedisClient, TTL_SECONDS

TELEGRAM_BOT_TOKEN = "BOT_TOKEN"
TELEGRAM_CHAT_ID = "1680424782"
GITHUB_REPO = "yihua-zhuo/agent-job"
AGENT_NAMES = ["code-review", "test", "qc", "deploy"]
POLL_INTERVAL = 5  # seconds


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def send_telegram(message: str):
    """发送消息到 Telegram"""
    import urllib.request
    import urllib.parse
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(url, data=data)
    urllib.request.urlopen(req, timeout=10)


async def update_heartbeat(agent: str):
    await MemoryStore.set_agent_context(agent, {"status": "running", "last_update": utc_now()})


async def report_to_user(text: str):
    """通过 Telegram 实时通知用户"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: send_telegram(text))


async def parse_task_from_message(message: str) -> dict:
    """将用户消息解析为结构化任务"""
    return {
        "task_id": str(uuid.uuid4())[:8],
        "description": message.strip(),
        "status": "pending",
        "created_at": utc_now(),
    }


async def decompose_task(task: dict) -> list[dict]:
    """将大任务分解为子任务，分配给不同 Agent"""
    task_id = task["task_id"]
    description = task["description"]

    sub_tasks = []

    # 根据任务关键词决定走哪些 Agent
    review_keywords = ["review", "review code", "code review", "review pr", "review patch"]
    test_keywords = ["test", "测试", "unit test", "integration test"]
    qc_keywords = ["qc", "quality", "check", "lint", "style", "type check"]
    deploy_keywords = ["deploy", "部署", "release"]

    needs_review = any(k in description.lower() for k in review_keywords)
    needs_test = any(k in description.lower() for k in test_keywords)
    needs_qc = any(k in description.lower() for k in qc_keywords)
    needs_deploy = any(k in description.lower() for k in deploy_keywords)

    # 默认所有 Agent 都跑一轮（全面检查）
    if not any([needs_review, needs_test, needs_qc, needs_deploy]):
        needs_review = needs_test = needs_qc = True

    if needs_review:
        sub_tasks.append({
            "sub_task_id": f"{task_id}-review",
            "parent_id": task_id,
            "agent": "code-review",
            "description": f"Code review: {description}",
            "status": "pending",
            "created_at": utc_now(),
        })

    if needs_test:
        sub_tasks.append({
            "sub_task_id": f"{task_id}-test",
            "parent_id": task_id,
            "agent": "test",
            "description": f"Run tests: {description}",
            "status": "pending",
            "created_at": utc_now(),
        })

    if needs_qc:
        sub_tasks.append({
            "sub_task_id": f"{task_id}-qc",
            "parent_id": task_id,
            "agent": "qc",
            "description": f"QC check: {description}",
            "status": "pending",
            "created_at": utc_now(),
        })

    if needs_deploy:
        sub_tasks.append({
            "sub_task_id": f"{task_id}-deploy",
            "parent_id": task_id,
            "agent": "deploy",
            "description": f"Deploy: {description}",
            "status": "pending",
            "created_at": utc_now(),
        })

    return sub_tasks


async def dispatch_sub_task(sub_task: dict) -> Optional[str]:
    """分发子任务到指定 Agent（写入 Agent 队列）"""
    client = await RedisClient.get_client()
    agent_queue = f"agent-system:queue:{sub_task['agent']}"
    await client.lpush(agent_queue, json.dumps(sub_task, ensure_ascii=False))
    return sub_task["agent"]


async def collect_results(parent_id: str, expected_count: int, timeout: int = 300) -> list[dict]:
    """收集所有子任务结果"""
    results = []
    start = time.time()

    while len(results) < expected_count and (time.time() - start) < timeout:
        # 检查已完成任务
        all_completed_raw = await client.hget("agent-system:tasks:completed", parent_id)
        # 同时检查各子任务结果
        for agent in AGENT_NAMES:
            result = await MemoryStore.get_result(f"{parent_id}-{agent}")
            if result and result not in results:
                results.append(result)
        await asyncio.sleep(2)

    return results


async def aggregate_report(task: dict, sub_tasks: list, all_results: list) -> str:
    """聚合子 Agent 结果，生成用户报告"""
    lines = [f"📊 <b>任务完成</b>: {task['description']}", ""]

    agent_results = {}
    for r in all_results:
        agent_results[r.get("agent", "unknown")] = r

    for st in sub_tasks:
        agent = st["agent"]
        result = agent_results.get(agent, {})
        status = result.get("status", "no result")
        details = result.get("details", "")

        emoji = "✅" if status == "pass" else "❌" if status == "fail" else "⏳"
        lines.append(f"{emoji} <b>{agent}</b>: {status}")
        if details:
            lines.append(f"   └ {details}")

    lines.append("")
    lines.append(f"🕐 {utc_now()}")
    return "\n".join(lines)


async def supervisor_loop():
    """Supervisor 主循环"""
    print("[Supervisor] Starting...")

    client = await RedisClient.get_client()

    # 注册自己
    await update_heartbeat("supervisor")

    # 清理旧的任务状态
    await client.delete("agent-system:tasks:pending")
    await client.delete("agent-system:tasks:running")
    await client.delete("agent-system:tasks:completed")

    print("[Supervisor] Loop started, polling for tasks...")

    while True:
        try:
            # 1. 检查是否有新任务
            raw = await client.brpop("agent-system:tasks:pending", timeout=POLL_INTERVAL)
            if raw:
                _, payload = raw
                task = json.loads(payload)
                task_id = task["task_id"]

                print(f"[Supervisor] Got task: {task_id}")
                await report_to_user(f"🧠 <b>收到任务</b>: {task['description'][:100]}")

                # 2. 分解任务
                sub_tasks = await decompose_task(task)
                print(f"[Supervisor] Decomposed into {len(sub_tasks)} sub-tasks")

                # 3. 写入全局上下文（供各 Agent 读取）
                await MemoryStore.set_global_context(f"task:{task_id}", {
                    "task": task,
                    "sub_tasks": sub_tasks,
                    "status": "decomposed",
                    "updated_at": utc_now(),
                })

                # 4. 分发子任务到各 Agent 队列
                dispatch_info = []
                for st in sub_tasks:
                    await dispatch_sub_task(st)
                    dispatch_info.append(st["agent"])

                await report_to_user(
                    f"📦 分解为 {len(sub_tasks)} 个子任务，"
                    f"分发给: {', '.join(dispatch_info)}"
                )

                # 5. 等待子任务结果
                expected = len(sub_tasks)
                await asyncio.sleep(3)  # 等待 Agent 启动

                # 6. 监听子任务完成事件（简单轮询）
                collected = []
                start_wait = time.time()
                while len(collected) < expected and (time.time() - start_wait) < 600:
                    for st in sub_tasks:
                        result_key = f"agent-system:result:{st['sub_task_id']}"
                        raw_result = await client.get(result_key)
                        if raw_result and st["sub_task_id"] not in [c["sub_task_id"] for c in collected]:
                            result = json.loads(raw_result)
                            collected.append({**st, **result})
                            status_emoji = "✅" if result.get("status") == "pass" else "❌"
                            await report_to_user(
                                f"{status_emoji} <b>{st['agent']}</b> 完成: "
                                f"{result.get('summary', result.get('status', 'unknown'))}"
                            )
                    await asyncio.sleep(2)

                # 7. 聚合报告
                if collected:
                    report_lines = [f"📊 <b>任务完成</b>: {task['description']}", ""]
                    for c in collected:
                        emoji = "✅" if c.get("status") == "pass" else "❌"
                        report_lines.append(
                            f"{emoji} <b>{c['agent']}</b>: {c.get('summary', c.get('status', 'unknown'))}"
                        )
                    report_lines.append("")
                    report_lines.append(f"🕐 {utc_now()}")
                    await report_to_user("\n".join(report_lines))
                else:
                    await report_to_user("⚠️ 子任务结果收集超时")

            else:
                # 无任务，更新心跳
                await update_heartbeat("supervisor")

        except Exception as e:
            print(f"[Supervisor] Error: {e}")
            await asyncio.sleep(5)


async def main():
    print("[Supervisor] Initializing Redis connection...")
    client = await RedisClient.get_client()
    await client.ping()
    print("[Supervisor] Redis connected.")
    await supervisor_loop()


if __name__ == "__main__":
    asyncio.run(main())