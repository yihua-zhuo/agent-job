"""
Shared Memory — 基于 yihua-zhuo/agent-job-shared-memory 本地 clone

pipeline 每次运行前会 checkout agent-job-shared-memory 到本地目录，
所有 agent 通过读写该目录下的 JSON 文件实现状态共享。

目录结构（clone 自 agent-job-shared-memory）：
  orchestrator_queue.json   待处理任务队列（JSON）
  orchestrator_state.json    当前任务状态（JSON）
  results/                  各 agent 执行结果（JSON，一 agent 一文件）
  reports/                  最终汇总报告（JSON）
  tasks/                    历史任务记录（JSON）
  logs/                     日志文件
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── 路径配置 ──────────────────────────────────────────────────────────────────

# 默认 clone 根路径（pipeline 会 checkout 到这里）
SHARED_MEMORY_ROOT = Path(os.environ.get(
    "AGENT_JOB_SHARED_MEMORY",
    "/home/node/.openclaw/workspace/agent-job-shared-memory",
))

QUEUE_FILE   = SHARED_MEMORY_ROOT / "orchestrator_queue.json"
STATE_FILE   = SHARED_MEMORY_ROOT / "orchestrator_state.json"
RESULTS_DIR  = SHARED_MEMORY_ROOT / "results"
REPORTS_DIR  = SHARED_MEMORY_ROOT / "reports"
TASKS_DIR    = SHARED_MEMORY_ROOT / "tasks"
LOCK_TIMEOUT = 300  # 秒


# ─── 内部工具 ────────────────────────────────────────────────────────────────

_lock = threading.Lock()


def _read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ─── 队列操作 ────────────────────────────────────────────────────────────────

def read_queue() -> dict:
    """返回 orchestrator_queue.json 内容（字典或空 dict）"""
    return _read_json(QUEUE_FILE) or {"tasks": []}


def write_queue(queue: dict) -> None:
    """整体写入队列文件"""
    with _lock:
        _write_json(QUEUE_FILE, queue)


def enqueue_task(task_id: str, agent_id: str, name: str, description: str,
                 created_at: str, task: str, timeout_seconds: int = 300) -> None:
    """向队列尾部追加一个子任务"""
    queue = read_queue()
    if "tasks" not in queue:
        queue = {"tasks": []}

    # 避免重复
    existing = {t["task_id"] for t in queue["tasks"]}
    if task_id not in existing:
        queue["tasks"].append({
            "task_id": task_id,
            "name": name,
            "description": description,
            "created_at": created_at,
            "status": "pending",
            "agents": [{
                "agent_id": agent_id,
                "name": name,
                "task": task,
                "timeout_seconds": timeout_seconds,
                "status": "pending",
                "result": None,
                "commit_hash": None,
            }],
        })
        write_queue(queue)


def update_task_status(task_id: str, agent_id: str, status: str,
                       result: str = None, commit_hash: str = None) -> None:
    """
    更新队列中指定 task 和 agent 的状态。
    status: pending | running | completed | failed
    """
    queue = read_queue()
    for task in queue.get("tasks", []):
        if task["task_id"] != task_id:
            continue
        for agent in task.get("agents", []):
            if agent["agent_id"] == agent_id:
                agent["status"] = status
                if result is not None:
                    agent["result"] = result
                if commit_hash is not None:
                    agent["commit_hash"] = commit_hash
                break
        # 如果所有 agent 都完成了，标记任务整体完成
        if all(a["status"] in ("completed", "failed") for a in task.get("agents", [])):
            task["status"] = "completed"
        break
    write_queue(queue)


# ─── State 操作 ─────────────────────────────────────────────────────────────

def read_state() -> dict:
    """返回 orchestrator_state.json 内容"""
    return _read_json(STATE_FILE) or {}


def write_state(state: dict) -> None:
    """整体写入 state 文件"""
    with _lock:
        _write_json(STATE_FILE, state)


def init_state(task_id: str, name: str, agents: list[dict]) -> None:
    """初始化或覆写当前任务状态"""
    write_state({
        "task_id": task_id,
        "name": name,
        "status": "running",
        "started_at": datetime.utcnow().isoformat() + "Z",
        "completed_at": None,
        "summary": None,
        "agents": {a["agent_id"]: {
            "name": a["name"],
            "layer": a.get("layer", ""),
            "status": "pending",
            "commit_hash": None,
            "result": None,
        } for a in agents},
    })


def patch_agent_state(agent_id: str, **kwargs) -> None:
    """只更新指定 agent 字段（不覆写其他 agent）"""
    state = read_state()
    if agent_id in state.get("agents", {}):
        state["agents"][agent_id].update(kwargs)
    else:
        state["agents"][agent_id] = kwargs
    write_state(state)


def complete_state(summary: str) -> None:
    """标记当前任务完成并写入汇总"""
    state = read_state()
    state["status"] = "completed"
    state["completed_at"] = datetime.utcnow().isoformat() + "Z"
    state["summary"] = summary
    write_state(state)


# ─── Results 操作 ───────────────────────────────────────────────────────────

def write_result(agent_id: str, result: dict) -> None:
    """写入单个 agent 的执行结果到 results/{agent_id}_result.json"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{agent_id}_result.json"
    _write_json(path, {
        "agent_id": agent_id,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        **result,
    })


def read_result(agent_id: str) -> dict | None:
    """读取单个 agent 的结果"""
    path = RESULTS_DIR / f"{agent_id}_result.json"
    return _read_json(path)


def read_all_results() -> dict[str, dict]:
    """读取所有 agent 结果"""
    if not RESULTS_DIR.exists():
        return {}
    results = {}
    for path in RESULTS_DIR.glob("*_result.json"):
        agent_id = path.stem.replace("_result", "")
        data = _read_json(path)
        if data:
            results[agent_id] = data
    return results


# ─── Reports 操作 ────────────────────────────────────────────────────────────

def write_report(task_id: str, report: dict) -> None:
    """写入最终报告到 reports/{task_id}_report.json"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{task_id}_report.json"
    _write_json(path, {
        "task_id": task_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        **report,
    })


def read_report(task_id: str) -> dict | None:
    """读取指定任务的报告"""
    path = REPORTS_DIR / f"{task_id}_report.json"
    return _read_json(path)


# ─── Tasks 历史操作 ───────────────────────────────────────────────────────────

def write_task_record(task_id: str, record: dict) -> None:
    """写入任务记录到 tasks/{task_id}.json"""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    path = TASKS_DIR / f"{task_id}.json"
    _write_json(path, record)


def read_task_record(task_id: str) -> dict | None:
    """读取指定任务记录"""
    path = TASKS_DIR / f"{task_id}.json"
    return _read_json(path)


# ─── Agent 轮询接口 ───────────────────────────────────────────────────────────

def get_pending_agents(agent_id: str = None) -> list[dict]:
    """
    从 orchestrator_queue.json 找出状态为 pending 的 agent 任务。
    如果指定了 agent_id，只返回匹配的任务。
    """
    queue = read_queue()
    pending = []
    for task in queue.get("tasks", []):
        if task.get("status") != "pending":
            continue
        for agent in task.get("agents", []):
            if agent["status"] != "pending":
                continue
            if agent_id and agent["agent_id"] != agent_id:
                continue
            pending.append({
                "task_id": task["task_id"],
                **agent,
            })
    return pending


def get_running_tasks() -> list[dict]:
    """获取所有 running 状态的任务"""
    queue = read_queue()
    return [
        {**task, "agents": [a for a in task.get("agents", []) if a.get("status") == "running"]}
        for task in queue.get("tasks", [])
        if task.get("status") == "running"
    ]


def get_completed_tasks() -> list[dict]:
    """获取所有已完成的任务"""
    queue = read_queue()
    return [task for task in queue.get("tasks", []) if task.get("status") == "completed"]


# ─── 简易 cron 同步（每次心跳调用）────────────────────────────────────────────

def sync_from_git(ref: str = "HEAD") -> None:
    """
    可选：运行 `git fetch && git checkout {ref}` 从远程拉最新共享记忆。
    pipeline 完成后会自动 checkout，这里只是安全网。
    """
    if not SHARED_MEMORY_ROOT.exists():
        return
    import subprocess
    try:
        subprocess.run(
            ["git", "-C", str(SHARED_MEMORY_ROOT), "fetch", "--all"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "-C", str(SHARED_MEMORY_ROOT), "checkout", ref],
            capture_output=True, timeout=10,
        )
    except Exception as e:
        print(f"[shared_memory] git sync failed: {e}")


# ─── 调试 / 快速 CLI ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Shared memory root: {SHARED_MEMORY_ROOT}")
    print(f"Queue exists: {QUEUE_FILE.exists()}")
    print(f"State exists: {STATE_FILE.exists()}")
    print()
    print("=== Queue ===")
    print(json.dumps(read_queue(), ensure_ascii=False, indent=2))
    print()
    print("=== State ===")
    print(json.dumps(read_state(), ensure_ascii=False, indent=2))
