"""同步封装 async API 调用的辅助工具"""
import asyncio
from functools import wraps


def async_handler(sync_fn):
    """装饰器：将同步 Flask handler 转为调用 async service 的同步包装"""
    @wraps(sync_fn)
    def wrapper(*args, **kwargs):
        async def _run():
            return await sync_fn(*args, **kwargs)
        return asyncio.run(_run())
    return wrapper


class AsyncResult:
    """将 coroutine 转为可序列化结果的简易封装"""
    def __init__(self, awaitable):
        self._awaitable = asyncio.run(self._awaitable)
    
    @classmethod
    def from_coro(cls, coro):
        return cls(coro)
    
    def to_dict(self):
        if hasattr(self._awaitable, 'to_dict'):
            return self._awaitable.to_dict()
        elif isinstance(self._awaitable, dict):
            return self._awaitable
        return self._awaitable


async def call_async(fn, *args, **kwargs):
    """执行 async 函数并返回结果"""
    result = await fn(*args, **kwargs)
    if hasattr(result, 'to_dict'):
        return result.to_dict()
    return result
