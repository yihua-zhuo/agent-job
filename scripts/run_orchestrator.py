#!/usr/bin/env python3
"""
Orchestrator 任务队列系统
用法: python3 run_orchestrator.py enqueue <task_json>
      python3 run_orchestrator.py status
      python3 run_orchestrator.py report

设计：Orchestrator 负责把任务写入队列文件，main agent 负责实际执行。
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

WORKSPACE = Path("/home/node/.openclaw/workspace/dev-agent-system")
QUEUE_FILE = WORKSPACE / "shared-memory/orchestrator_queue.json"
STATE_FILE = WORKSPACE / "shared-memory/orchestrator_state.json"
RESULTS_DIR = WORKSPACE / "shared-memory/results"

# ---------------------------------------------------------------------------
# 任务定义：多租户隔离测试 + 修复
# ---------------------------------------------------------------------------

TENANT_ISOLATION_TASK = {
    "task_id": "T001",
    "name": "多租户隔离修复",
    "description": "修复 CRM 系统的租户隔离问题",
    "created_at": "",
    "status": "pending",
    "agents": [
        {
            "agent_id": "tenant-middleware",
            "name": "中间件层检查",
            "layer": "middleware",
            "task": """检查并修复租户隔离中间件:

1. 检查 src/internal/middleware/auth.py 是否提取 tenant_id 到 g 对象
2. 检查 src/internal/middleware/tenant.py 是否存在并正确实现
3. 检查 src/app.py 是否启用租户隔离中间件

需要验证的场景:
- g.tenant_id 是否从 JWT payload 中正确提取
- set_tenant_id() 是否在请求开始时调用

发现的问题直接修复并提交到 develop 分支。""",
            "timeout_seconds": 180
        },
        {
            "agent_id": "tenant-api",
            "name": "API 层检查",
            "layer": "api",
            "task": """检查并修复 API 层的租户隔离:

1. 检查 src/api/customers.py 的租户过滤
2. 检查 src/api/sales.py 的租户过滤
3. 检查 src/api/users.py 的租户过滤

需要验证的场景:
- GET /api/customers 是否只返回当前租户的客户
- POST /api/customers 是否自动设置 tenant_id
- DELETE /api/customers/{id} 是否验证租户所有权

发现的问题直接修复并提交到 develop 分支。""",
            "timeout_seconds": 180
        },
        {
            "agent_id": "tenant-db",
            "name": "数据库层检查",
            "layer": "database",
            "task": """检查并修复数据库模型的租户支持:

1. 检查 src/models/ 下的模型是否有 tenant_id 字段
   - customer.py
   - pipeline.py
   - opportunity.py
   - 其他关键模型

2. 如果缺少 tenant_id 字段，添加到模型定义

3. 检查 sql/ 目录下的 SQL 文件是否包含 tenant_id 列

发现的问题直接修复并提交到 develop 分支。""",
            "timeout_seconds": 180
        },
        {
            "agent_id": "tenant-service",
            "name": "Service 层检查",
            "layer": "service",
            "task": """检查并修复 Service 层的租户隔离:

1. 检查 src/services/customer_service.py 的租户过滤
2. 检查 src/services/sales_service.py 的租户过滤
3. 检查其他 service 文件

需要验证的场景:
- list_customers() 是否接受 tenant_id 参数并过滤
- create_customer() 是否自动设置 tenant_id
- delete_customer() 是否验证租户所有权

发现的问题直接修复并提交到 develop 分支。""",
            "timeout_seconds": 180
        }
    ]
}


# ---------------------------------------------------------------------------
# 队列管理
# ---------------------------------------------------------------------------

def load_queue() -> Dict:
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return {"tasks": [], "pending_agents": []}


def save_queue(queue: Dict) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(queue, indent=2, ensure_ascii=False))


def load_state() -> Dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: Dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# 命令处理
# ---------------------------------------------------------------------------

def cmd_enqueue(task_def: Dict) -> None:
    """入队一个任务"""
    queue = load_queue()

    # 检查是否已有相同任务在队列中
    existing = [t for t in queue["tasks"] if t["task_id"] == task_def["task_id"] and t["status"] == "pending"]
    if existing:
        print(f"⚠️  任务 {task_def['task_id']} 已在队列中")
        return

    task_def["created_at"] = datetime.now().isoformat()
    task_def["status"] = "pending"
    queue["tasks"].append(task_def)

    # 所有 agent 也入队
    for agent in task_def["agents"]:
        queue["pending_agents"].append({
            "agent_id": agent["agent_id"],
            "task_id": task_def["task_id"],
            "name": agent["name"],
            "layer": agent["layer"],
            "task": agent["task"],
            "timeout_seconds": agent["timeout_seconds"],
            "status": "pending",
            "session_key": None,
            "run_id": None
        })

    save_queue(queue)

    # 保存任务状态
    state = {
        "task_id": task_def["task_id"],
        "name": task_def["name"],
        "status": "queued",
        "agents": {ag["agent_id"]: {"name": ag["name"], "layer": ag["layer"], "status": "pending"} for ag in task_def["agents"]},
        "created_at": task_def["created_at"]
    }
    save_state(state)

    print(f"✅ 任务已入队: {task_def['task_id']}")
    print(f"   任务名: {task_def['name']}")
    print(f"   Agent 数量: {len(task_def['agents'])}")
    for ag in task_def["agents"]:
        print(f"   - {ag['agent_id']} ({ag['layer']})")


def cmd_status() -> None:
    """显示队列状态"""
    queue = load_queue()
    state = load_state()

    if not queue["tasks"]:
        print("📭 队列为空")
        return

    print(f"\n{'='*60}")
    print("  Orchestrator 队列状态")
    print(f"{'='*60}")

    for task in queue["tasks"]:
        print(f"\n📋 任务: {task['name']} ({task['task_id']})")
        print(f"   状态: {task['status']}")
        print(f"   创建: {task['created_at']}")
        print(f"   Agents:")

        for ag in task["agents"]:
            agent_status = state.get("agents", {}).get(ag["agent_id"], {}).get("status", "unknown")
            icon = {"pending": "⏳", "running": "🔄", "completed": "✅", "timeout": "⏱️", "failed": "❌"}.get(agent_status, "❓")
            print(f"     {icon} {ag['agent_id']} ({ag['layer']}) - {agent_status}")

    pending = [a for a in queue["pending_agents"] if a["status"] == "pending"]
    print(f"\n待执行 Agent: {len(pending)}")


def cmd_list() -> None:
    """列出下一个待执行的 Agent"""
    queue = load_queue()

    pending = [a for a in queue["pending_agents"] if a["status"] == "pending"]
    if not pending:
        print("✅ 所有 Agent 已完成")
        return

    agent = pending[0]
    print(json.dumps(agent, indent=2, ensure_ascii=False))


def cmd_mark_running(agent_id: str, session_key: str, run_id: str) -> None:
    """标记 Agent 为 running"""
    queue = load_queue()

    for ag in queue["pending_agents"]:
        if ag["agent_id"] == agent_id and ag["status"] == "pending":
            ag["status"] = "running"
            ag["session_key"] = session_key
            ag["run_id"] = run_id
            break

    save_queue(queue)


def cmd_mark_done(agent_id: str, status: str, result: str) -> None:
    """标记 Agent 完成"""
    queue = load_queue()

    for ag in queue["pending_agents"]:
        if ag["agent_id"] == agent_id and ag["status"] == "running":
            ag["status"] = status  # completed / timeout / failed
            ag["result"] = result
            ag["completed_at"] = datetime.now().isoformat()
            break

    save_queue(queue)


def cmd_report() -> None:
    """生成完整报告"""
    queue = load_queue()
    state = load_state()

    if not queue["tasks"]:
        print("📭 没有任务记录")
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    latest_task = queue["tasks"][-1]

    lines = [f"# Orchestrator 执行报告 - {latest_task['name']}"]
    lines.append(f"**Task ID**: {latest_task['task_id']}")
    lines.append(f"**时间**: {latest_task['created_at']}")
    lines.append("")
    lines.append("## Agent 执行状态")
    lines.append("")

    for ag in latest_task["agents"]:
        icon = {"completed": "✅", "timeout": "⏱️", "failed": "❌", "running": "🔄", "pending": "⏳"}.get(
            state.get("agents", {}).get(ag["agent_id"], {}).get("status", "pending"), "❓"
        )
        lines.append(f"- {icon} **{ag['name']}** ({ag['layer']}) - {state.get('agents', {}).get(ag['agent_id'], {}).get('status', 'pending')}")

    lines.append("")
    lines.append("## 待处理")

    pending = [a for a in queue["pending_agents"] if a["status"] == "pending"]
    if pending:
        for ag in pending:
            lines.append(f"- ⏳ {ag['name']} ({ag['layer']})")
    else:
        lines.append("✅ 所有 Agent 已完成")

    report_text = "\n".join(lines)
    print(report_text)

    report_path = RESULTS_DIR / f"orchestrator_report_{latest_task['task_id']}.md"
    report_path.write_text(report_text)
    print(f"\n📄 报告已保存: {report_path}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 run_orchestrator.py enqueue <task_json>")
        print("  python3 run_orchestrator.py status")
        print("  python3 run_orchestrator.py list")
        print("  python3 run_orchestrator.py mark-running <agent_id> <session_key> <run_id>")
        print("  python3 run_orchestrator.py mark-done <agent_id> <status> <result>")
        print("  python3 run_orchestrator.py report")
        print("")
        print("预设任务:")
        print("  python3 run_orchestrator.py tenant-isolation")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "tenant-isolation":
        TENANT_ISOLATION_TASK["created_at"] = datetime.now().isoformat()
        cmd_enqueue(TENANT_ISOLATION_TASK)
    elif cmd == "enqueue":
        if len(sys.argv) > 2:
            task_file = Path(sys.argv[2])
            task_def = json.loads(task_file.read_text())
        else:
            task_def = json.loads(sys.stdin.read())
        cmd_enqueue(task_def)
    elif cmd == "status":
        cmd_status()
    elif cmd == "list":
        cmd_list()
    elif cmd == "mark-running" and len(sys.argv) > 4:
        cmd_mark_running(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "mark-done" and len(sys.argv) > 3:
        result = sys.argv[3] if len(sys.argv) == 4 else " ".join(sys.argv[3:])
        cmd_mark_done(sys.argv[2], "completed", result)
    elif cmd == "report":
        cmd_report()
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
