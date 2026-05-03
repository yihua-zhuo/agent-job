#!/usr/bin/env python3
"""
Telegram Bot — 用户通过 Telegram 与 Agent 系统交互
命令：/start /status /submit /tasks /abort
"""

import json
import os
import sys
import time
import re

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_CHAT_ID = "1680424782"  # Kim
POLL_INTERVAL = 3

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id: str, text: str, parse_mode: str = "HTML"):
    import urllib.request, urllib.parse
    url = f"{API_URL}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }).encode()
    req = urllib.request.Request(url, data=data)
    urllib.request.urlopen(req, timeout=10)


def get_updates(offset: int = 0):
    import urllib.request, urllib.parse
    url = f"{API_URL}/getUpdates"
    data = urllib.parse.urlencode({"offset": offset, "timeout": POLL_INTERVAL}).encode()
    req = urllib.request.Request(url, data=data)
    import json as _json
    with urllib.request.urlopen(req, timeout=POLL_INTERVAL + 5) as resp:
        return _json.load(_json.loads(resp.read()))


async def submit_task(message: str) -> str:
    """通过 Redis 提交任务"""
    import redis.asyncio as redis
    task_id = f"task-{int(time.time())}"
    task = {
        "task_id": task_id,
        "description": message,
        "submitted_by": "telegram",
        "submitted_at": time.time(),
    }
    r = redis.from_url("redis://localhost:6379/0", decode_responses=True)
    await r.lpush("agent-system:tasks:pending", json.dumps(task, ensure_ascii=False))
    await r.close()
    return task_id


def format_status() -> str:
    return """
🤖 <b>Agent 团队状态</b>

• <b>Supervisor</b> — 协调者，负责分解任务
• <b>Code Review</b> — 代码审查
• <b>Test</b> — 测试执行
• <b>QC</b> — 质量控制
• <b>Deploy</b> — 部署

📋 <b>命令</b>
/start — 显示此信息
/status — Agent 状态
/submit <任务> — 提交新任务
/tasks — 查看任务队列
/result <task_id> — 查看结果
/abort <task_id> — 取消任务
"""


def main():
    print("[Bot] Starting Telegram bot...")
    offset = 0

    while True:
        try:
            updates = get_updates(offset)
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message", {})
                chat_id = str(message.get("chat", {}).get("id", ""))
                text = message.get("text", "")
                first_name = message.get("chat", {}).get("first_name", "")

                if not text:
                    continue

                # 解析命令
                if text.strip() == "/start":
                    send_message(chat_id, f"👋 Hello {first_name}!\n{format_status()}")
                    continue

                if text.strip() == "/status":
                    send_message(chat_id, format_status())
                    continue

                if text.startswith("/submit "):
                    task_desc = text[8:].strip()
                    if not task_desc:
                        send_message(chat_id, "用法: /submit <任务描述>\n例如: /submit review the latest commit")
                        continue
                    # 同步提交到 Redis（简化，实际用异步）
                    import redis
                    r = redis.from_url("redis://localhost:6379/0", decode_responses=True)
                    task_id = f"task-{int(time.time())}"
                    task = {
                        "task_id": task_id,
                        "description": task_desc,
                        "submitted_by": "telegram",
                        "submitted_at": time.time(),
                    }
                    r.lpush("agent-system:tasks:pending", json.dumps(task, ensure_ascii=False))
                    r.close()
                    send_message(
                        chat_id,
                        f"✅ <b>任务已提交</b>\n"
                        f"ID: <code>{task_id}</code>\n"
                        f"描述: {task_desc[:100]}...\n\n"
                        f"用 /tasks 查看进度"
                    )
                    continue

                if text.startswith("/tasks"):
                    send_message(chat_id, "📋 任务队列查看中...\n(需要 Redis 连接)")
                    continue

                if text.startswith("/abort "):
                    send_message(chat_id, "🚫 任务取消功能开发中")
                    continue

                # 未知命令
                send_message(chat_id, f"未知命令: {text}\n\n{format_status()}")

        except Exception as e:
            print(f"[Bot] Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()