"""
Shared Memory Redis Client
所有 Agent 通过这个模块访问共享记忆
"""

import json
import time
from typing import Any, Optional
import redis.asyncio as redis

REDIS_URL = "redis://localhost:6379/0"
TTL_SECONDS = 86400  # 24h


class RedisClient:
    _instance: Optional["RedisClient"] = None
    _client: Optional[redis.Redis] = None

    @classmethod
    async def get_client(cls) -> redis.Redis:
        if cls._client is None:
            cls._client = redis.from_url(REDIS_URL, decode_responses=True)
        return cls._client

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            cls._client = None


class MemoryStore:
    """共享记忆读写接口"""

    # ── 任务队列 ────────────────────────────────────────────

    @staticmethod
    async def push_task(task: dict) -> None:
        """添加任务到待执行队列"""
        client = await RedisClient.get_client()
        await client.lpush("agent-system:tasks:pending", json.dumps(task, ensure_ascii=False))
        await client.lpush("agent-system:tasks:all", json.dumps({**task, "queued_at": time.time()}))

    @staticmethod
    async def pop_task(block: bool = True, timeout: int = 5) -> Optional[dict]:
        """原子获取任务（BRPOP 支持阻塞）"""
        client = await RedisClient.get_client()
        if block:
            result = await client.brpop("agent-system:tasks:pending", timeout=timeout)
            if result:
                _, payload = result
                return json.loads(payload)
            return None
        else:
            payload = await client.rpop("agent-system:tasks:pending")
            if payload:
                return json.loads(payload)
            return None

    @staticmethod
    async def get_pending_tasks() -> list[dict]:
        client = await RedisClient.get_client()
        items = await client.lrange("agent-system:tasks:pending", 0, -1)
        return [json.loads(i) for i in items]

    @staticmethod
    async def push_result(task_id: str, result: dict) -> None:
        """写入任务结果"""
        client = await RedisClient.get_client()
        await client.hset(
            "agent-system:tasks:completed",
            task_id,
            json.dumps({**result, "completed_at": time.time()}, ensure_ascii=False)
        )
        await client.expire("agent-system:tasks:completed", TTL_SECONDS)

    @staticmethod
    async def get_result(task_id: str) -> Optional[dict]:
        client = await RedisClient.get_client()
        raw = await client.hget("agent-system:tasks:completed", task_id)
        if raw:
            return json.loads(raw)
        return None

    # ── 全局上下文 ───────────────────────────────────────────

    @staticmethod
    async def set_global_context(key: str, value: Any) -> None:
        client = await RedisClient.get_client()
        await client.hset("agent-system:context:global", key, json.dumps(value, ensure_ascii=False))
        await client.expire("agent-system:context:global", TTL_SECONDS)

    @staticmethod
    async def get_global_context(key: str) -> Any:
        client = await RedisClient.get_client()
        raw = await client.hget("agent-system:context:global", key)
        if raw is None:
            return None
        return json.loads(raw)

    @staticmethod
    async def get_all_global_context() -> dict:
        client = await RedisClient.get_client()
        raw = await client.hgetall("agent-system:context:global")
        return {k: json.loads(v) for k, v in raw.items()}

    # ── Agent 私有上下文 ────────────────────────────────────

    @staticmethod
    async def set_agent_context(agent: str, data: dict) -> None:
        client = await RedisClient.get_client()
        await client.hset(
            f"agent-system:context:agent:{agent}",
            "data",
            json.dumps(data, ensure_ascii=False)
        )
        await client.hset(
            f"agent-system:context:agent:{agent}",
            "heartbeat",
            str(time.time())
        )
        await client.expire(f"agent-system:context:agent:{agent}", TTL_SECONDS)

    @staticmethod
    async def get_agent_context(agent: str) -> dict:
        client = await RedisClient.get_client()
        raw = await client.hget(f"agent-system:context:agent:{agent}", "data")
        return json.loads(raw) if raw else {}

    @staticmethod
    async def get_agent_heartbeat(agent: str) -> Optional[float]:
        client = await RedisClient.get_client()
        raw = await client.hget(f"agent-system:context:agent:{agent}", "heartbeat")
        return float(raw) if raw else None

    @staticmethod
    async def get_all_agent_heartbeats() -> dict[str, float]:
        client = await RedisClient.get_client()
        keys = await client.keys("agent-system:context:agent:*")
        result = {}
        for key in keys:
            agent = key.split(":")[-1]
            hb = await client.hget(key, "heartbeat")
            if hb:
                result[agent] = float(hb)
        return result

    # ── 共享记忆（Agent 间交换信息） ─────────────────────────

    @staticmethod
    async def append_shared_memory(agent: str, entry: dict) -> None:
        """向共享记忆追加一条记录"""
        client = await RedisClient.get_client()
        entry_with_meta = {
            **entry,
            "author": agent,
            "timestamp": time.time(),
        }
        await client.lpush(
            "agent-system:memory:shared",
            json.dumps(entry_with_meta, ensure_ascii=False)
        )
        # 只保留最近 200 条
        await client.ltrim("agent-system:memory:shared", 0, 199)
        await client.expire("agent-system:memory:shared", TTL_SECONDS)

    @staticmethod
    async def get_shared_memory(limit: int = 50) -> list[dict]:
        client = await RedisClient.get_client()
        items = await client.lrange("agent-system:memory:shared", 0, limit - 1)
        return [json.loads(i) for i in items]

    # ── 任务锁 ───────────────────────────────────────────────

    @staticmethod
    async def acquire_lock(task_id: str, owner: str, ttl: int = 300) -> bool:
        """尝试获取任务锁"""
        client = await RedisClient.get_client()
        key = f"agent-system:lock:task:{task_id}"
        acquired = await client.set(key, owner, nx=True, ex=ttl)
        return bool(acquired)

    @staticmethod
    async def release_lock(task_id: str, owner: str) -> bool:
        """释放任务锁（只能由持有者释放）"""
        client = await RedisClient.get_client()
        key = f"agent-system:lock:task:{task_id}"
        current = await client.get(key)
        if current == owner:
            await client.delete(key)
            return True
        return False

    # ── 运行中任务追踪 ────────────────────────────────────────

    @staticmethod
    async def set_running_task(task_id: str, agent: str) -> None:
        client = await RedisClient.get_client()
        await client.hset("agent-system:tasks:running", task_id, json.dumps({
            "agent": agent,
            "started_at": time.time(),
        }))
        await client.expire("agent-system:tasks:running", TTL_SECONDS)

    @staticmethod
    async def remove_running_task(task_id: str) -> None:
        client = await RedisClient.get_client()
        await client.hdel("agent-system:tasks:running", task_id)

    @staticmethod
    async def get_running_tasks() -> dict[str, dict]:
        client = await RedisClient.get_client()
        raw = await client.hgetall("agent-system:tasks:running")
        return {k: json.loads(v) for k, v in raw.items()}

    # ── 清理 ─────────────────────────────────────────────────

    @staticmethod
    async def ping() -> bool:
        try:
            client = await RedisClient.get_client()
            await client.ping()
            return True
        except Exception:
            return False