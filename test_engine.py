import asyncio
import sys
sys.path.insert(0, '/home/node/.openclaw/workspace/agent-job')

async def test():
    from src.db.connection import _build_engine
    from src.configs.settings import settings

    print(f"Input URL: {repr(settings.database_url)}")
    engine = _build_engine(settings.database_url)
    print(f"Engine URL: {engine.url}")

    try:
        async with engine.connect() as conn:
            print("Connected!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

asyncio.run(test())
