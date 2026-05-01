"""Synchronous helper for running async code in sync Flask handlers.

The problem: SQLAlchemy asyncpg connections are bound to the event loop that
created them. The module-level `engine` singleton holds connections from old
loops, causing "attached to a different loop" errors.

Solution: After each asyncio.run() completes, force-recreate the engine so
the next call starts with a fresh connection pool.
"""
import asyncio
import threading

_executor = threading.local()


def run_async(async_fn, *args, **kwargs):
    """Run an async function from a sync Flask handler."""
    # Get or create a dedicated thread for this request
    if not hasattr(_executor, 'loop') or _executor.loop is None:
        _executor.loop = asyncio.new_event_loop()
        _executor.thread = threading.Thread(
            target=_run_loop_forever, 
            args=(_executor.loop,), 
            daemon=True
        )
        _executor.thread.start()

    loop = _executor.loop
    future = asyncio.run_coroutine_threadsafe(async_fn(*args, **kwargs), loop)
    return future.result(timeout=30)


def _run_loop_forever(loop):
    """Run a permanent event loop in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()