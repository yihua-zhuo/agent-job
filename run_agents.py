#!/usr/bin/env python3
"""
一键启动所有 Agent
- 启动 Redis（如未运行）
- 启动 Supervisor + 所有子 Agent
- 每个 Agent 是独立进程，通过共享 Redis 协作
"""

import multiprocessing
import os
import sys
import time

def run_supervisor():
    sys.path.insert(0, os.path.dirname(__file__))
    import asyncio
    from agents.supervisor.supervisor import main
    asyncio.run(main())

def run_code_review():
    sys.path.insert(0, os.path.dirname(__file__))
    import asyncio
    from agents.code_review.review_agent import CodeReviewAgent
    agent = CodeReviewAgent()
    asyncio.run(agent.start())

def run_test():
    sys.path.insert(0, os.path.dirname(__file__))
    import asyncio
    from agents.test.test_agent import TestAgent
    agent = TestAgent()
    asyncio.run(agent.start())

def run_qc():
    sys.path.insert(0, os.path.dirname(__file__))
    import asyncio
    from agents.qc.qc_agent import QCAgent
    agent = QCAgent()
    asyncio.run(agent.start())

def run_deploy():
    sys.path.insert(0, os.path.dirname(__file__))
    import asyncio
    from agents.deploy.deploy_agent import DeployAgent
    agent = DeployAgent()
    asyncio.run(agent.start())

def check_redis():
    import redis
    try:
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.ping()
        print("[Redis] Connected.")
        return True
    except Exception:
        print("[Redis] Not running. Start with: redis-server")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Multi-Agent System Starting...")
    print("=" * 50)

    # 检查 Redis
    if not check_redis():
        print("Please start Redis first: redis-server")
        sys.exit(1)

    processes = [
        ("Supervisor", run_supervisor),
        ("CodeReview", run_code_review),
        ("Test", run_test),
        ("QC", run_qc),
        ("Deploy", run_deploy),
    ]

    workers = []
    for name, target in processes:
        p = multiprocessing.Process(target=target, name=name)
        p.start()
        workers.append(p)
        print(f"[Launcher] Started {name} (PID: {p.pid})")
        time.sleep(0.5)

    print(f"\nAll {len(workers)} agents running. Press Ctrl+C to stop.\n")

    try:
        for p in workers:
            p.join()
    except KeyboardInterrupt:
        print("\n[Launcher] Shutting down...")
        for p in workers:
            p.terminate()
            p.join(timeout=5)
        print("[Launcher] Done.")