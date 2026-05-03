"""
Base Agent — 所有子 Agent 的基类
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Optional

from shared_memory import MemoryStore, RedisClient


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, poll_interval: int = 3):
        self.poll_interval = poll_interval
        self.running = False

    async def start(self):
        """启动 Agent 主循环"""
        print(f"[{self.name}] Starting...")
        client = await RedisClient.get_client()
        await client.ping()
        print(f"[{self.name}] Connected to Redis.")
        self.running = True
        await self.run_loop()

    async def stop(self):
        self.running = False
        print(f"[{self.name}] Stopped.")

    @abstractmethod
    async def execute(self, task: dict) -> dict:
        """执行任务，返回结果"""
        raise NotImplementedError

    async def run_loop(self):
        """主循环：竞争获取任务、执行、写入结果"""
        while self.running:
            try:
                # 1. 更新心跳
                await MemoryStore.set_agent_context(self.name, {
                    "status": "idle" if not self.running else "running",
                    "last_poll": time.time(),
                })

                # 2. 尝试从自己的队列获取任务
                client = await RedisClient.get_client()
                raw = await client.brpop(f"agent-system:queue:{self.name}", timeout=self.poll_interval)
                if not raw:
                    continue

                _, payload = raw
                task = json.loads(payload)
                sub_task_id = task["sub_task_id"]
                parent_id = task["parent_id"]

                print(f"[{self.name}] Got task: {sub_task_id}")

                # 3. 获取任务锁
                locked = await MemoryStore.acquire_lock(sub_task_id, self.name, ttl=300)
                if not locked:
                    print(f"[{self.name}] Could not acquire lock for {sub_task_id}, skipping.")
                    continue

                # 4. 读取全局上下文（父任务信息）
                parent_ctx = await MemoryStore.get_global_context(f"task:{parent_id}")
                if parent_ctx:
                    task["parent_context"] = parent_ctx

                # 5. 执行业务逻辑
                start_time = time.time()
                result = await self.execute(task)
                elapsed = time.time() - start_time

                # 6. 写入结果
                result_payload = {
                    "agent": self.name,
                    "sub_task_id": sub_task_id,
                    "parent_id": parent_id,
                    "elapsed_seconds": round(elapsed, 1),
                    "started_at": start_time,
                    **result,
                }

                # 写入 result hash（供 Supervisor 收集）
                client = await RedisClient.get_client()
                await client.set(
                    f"agent-system:result:{sub_task_id}",
                    json.dumps(result_payload, ensure_ascii=False),
                    ex=3600,
                )
                await MemoryStore.push_result(parent_id, result_payload)

                # 写入共享记忆
                await MemoryStore.append_shared_memory(self.name, {
                    "sub_task_id": sub_task_id,
                    "parent_id": parent_id,
                    "result": result,
                    "elapsed": elapsed,
                })

                # 7. 释放锁
                await MemoryStore.release_lock(sub_task_id, self.name)
                print(f"[{self.name}] Completed {sub_task_id} in {elapsed:.1f}s")

            except Exception as e:
                print(f"[{self.name}] Error in loop: {e}")
                await asyncio.sleep(5)