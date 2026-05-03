"""
Base Agent — 所有子 Agent 的基类

职责：
- 通过 SharedMemory（GitHub Issues）轮询自己的任务队列
- 认领任务、执行、写入结果、标记完成
- 3 秒轮询间隔
"""

import asyncio
import os
import time
from abc import ABC, abstractmethod
from typing import Optional

from shared_memory import get_shared_memory, SharedMemory, Task


class BaseAgent(ABC):
    """Agent 基类：轮询 → 认领 → 执行 → 完成"""

    name: str = "base"  # 子类覆盖

    def __init__(self):
        self._sm: Optional[SharedMemory] = None
        self._running = False

    async def _get_sm(self) -> SharedMemory:
        if self._sm is None:
            self._sm = get_shared_memory()
        return self._sm

    async def start(self) -> None:
        """主循环：轮询任务，执行，汇报"""
        print(f"[{self.name}] Starting agent...")
        self._running = True

        while self._running:
            try:
                sm = await self._get_sm()

                # 1. 轮询 pending 任务
                tasks = await sm.get_pending_tasks(agent=self.name)

                if tasks:
                    task = tasks[0]  # 每次取一个
                    print(f"[{self.name}] Claiming task {task.task_id}")

                    # 2. 认领
                    await sm.claim_task(task)

                    # 3. 执行（子类实现）
                    result = await self.execute(task)
                    if result is None:
                        result = {"status": "done"}

                    # 4. 完成
                    await sm.complete_task(task, result)
                    print(f"[{self.name}] Completed {task.task_id}: {result.get('summary', result.get('status', ''))}")

                    # 5. 写共享记忆（供其他 Agent 读取）
                    await sm.write_memory(
                        author=self.name,
                        parent_id=task.task_id,
                        content=result,
                    )

                else:
                    # 无任务，挂起 POLL_INTERVAL
                    await asyncio.sleep(3)

            except Exception as e:
                print(f"[{self.name}] Error in loop: {e}")
                await asyncio.sleep(5)

    def stop(self) -> None:
        self._running = False

    @abstractmethod
    async def execute(self, task: Task) -> dict:
        """执行任务，子类实现。返回结果 dict"""
        raise NotImplementedError


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <agent_name>")
        sys.exit(1)
    name = sys.argv[1]

    class Runner(BaseAgent):
        name = name
        async def execute(self, task: Task) -> dict:
            return {"status": "done", "note": f"Agent {name} processed {task.description[:50]}"}

    agent = Runner()
    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        agent.stop()
        print(f"[{name}] Stopped.")