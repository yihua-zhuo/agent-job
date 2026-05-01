"""同步 HTTP 辅助工具 - 包装 async 服务调用"""
import asyncio
from functools import wraps


def run_async(coro):
    """对 async coroutine 调用 asyncio.run()"""
    return asyncio.run(coro)


def async_to_dict(result):
    """将 service 结果转为 dict"""
    if hasattr(result, 'to_dict'):
        return result.to_dict()
    if isinstance(result, dict):
        return result
    return result
