#!/usr/bin/env python3
"""
OpenClaw 多 Agent 协调器
使用 sessions_spawn 启动子 Agent，通过 sessions_send 传递任务

用法:
    python3 coordinator.py <task> [--code-dir <path>]
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# 路径配置
BASE_DIR = Path(__file__).parent
SHARED_MEMORY = BASE_DIR / "shared-memory"
TASKS_DIR = SHARED_MEMORY / "tasks"
RESULTS_DIR = SHARED_MEMORY / "results"
REPORTS_DIR = SHARED_MEMORY / "reports"

# Agent 配置
AGENTS = {
    "test": {
        "name": "测试工程师",
        "emoji": "🧪",
        "workspace": "test-agent",
        "description": "执行单元测试和集成测试"
    },
    "code-review": {
        "name": "代码审查工程师",
        "emoji": "🔍",
        "workspace": "code-review-agent",
        "description": "审查代码质量、安全和性能"
    },
    "qc": {
        "name": "质量控制工程师",
        "emoji": "✅",
        "workspace": "qc-agent",
        "description": "执行最终质量门禁检查"
    },
    "deploy": {
        "name": "部署工程师",
        "emoji": "🚀",
        "workspace": "deploy-agent",
        "description": "执行部署和发布"
    }
}


def log(msg):
    """统一日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


async def spawn_agent(agent_id, task_description, code_dir=None):
    """使用 sessions_spawn 启动子 Agent"""
    workspace_path = BASE_DIR / AGENTS[agent_id]["workspace"]
    
    prompt = f"""你是 {AGENTS[agent_id]['name']}（{AGENTS[agent_id]['emoji']}）。

{AGENTS[agent_id]['description']}。

任务：{task_description}

{'代码目录：' + code_dir if code_dir else ''}

请执行任务，完成后将结果写入 shared-memory/results/{agent_id}-results.json

工作目录：{workspace_path}
"""
    
    log(f"🚀 启动 {AGENTS[agent_id]['name']}...")
    
    # 这里应该调用 sessions_spawn，实际使用时通过 OpenClaw CLI 或 API
    # subprocess 调用 openclaw 命令
    import subprocess
    
    cmd = [
        "openclaw", "sessions", "spawn",
        "--label", f"{agent_id}-worker",
        "--runtime", "subagent",
        "--task", prompt,
        "--cwd", str(workspace_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        log(f"✅ {AGENTS[agent_id]['name']} 完成")
        return result.stdout
    except Exception as e:
        log(f"❌ {AGENTS[agent_id]['name']} 执行失败: {e}")
        return None


async def run_tests(code_dir):
    """运行测试 Agent"""
    return await spawn_agent("test", "执行代码测试", code_dir)


async def run_code_review(code_dir):
    """运行代码审查 Agent"""
    return await spawn_agent("code-review", "审查代码质量", code_dir)


async def run_qc(code_dir):
    """运行质量控制 Agent"""
    return await spawn_agent("qc", "执行质量门禁检查", code_dir)


async def run_deploy():
    """运行部署 Agent"""
    return await spawn_agent("deploy", "执行部署任务")


def save_task_record(task_id, status, results=None):
    """保存任务记录"""
    record = {
        "task_id": task_id,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "results": results or {}
    }
    
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_file = TASKS_DIR / f"{task_id}.json"
    with open(task_file, 'w') as f:
        json.dump(record, f, indent=2)


def generate_report(task_id, test_result, review_result, qc_result, deploy_result):
    """生成最终报告"""
    report = {
        "report_id": task_id,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "test": "✅ 通过" if test_result else "❌ 失败",
            "code_review": "✅ 通过" if review_result else "❌ 失败",
            "qc": "✅ 通过" if qc_result else "❌ 失败",
            "deploy": "✅ 完成" if deploy_result else "⏳ 待部署"
        },
        "recommendation": "通过验收，发布生产" if all([test_result, review_result, qc_result]) else "需要修复后重试"
    }
    
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / f"{task_id}-report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return report


async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "开发任务"
    code_dir = sys.argv[2] if len(sys.argv) > 2 else str(BASE_DIR / "src")
    
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    log(f"📋 任务ID: {task_id}")
    log(f"📁 代码目录: {code_dir}")
    
    save_task_record(task_id, "running")
    
    log("\n" + "="*60)
    log("🤖 开始多 Agent 协作流程")
    log("="*60)
    
    # 阶段1: 并行执行测试和代码审查
    log("\n📦 阶段1: 并行执行测试和代码审查")
    test_task = asyncio.create_task(run_tests(code_dir))
    review_task = asyncio.create_task(run_code_review(code_dir))
    
    test_result = await test_task
    review_result = await review_task
    
    # 阶段2: 质量控制检查
    log("\n📦 阶段2: 质量控制检查")
    qc_result = await run_qc(code_dir)
    
    # 阶段3: 部署（仅当所有检查通过时）
    log("\n📦 阶段3: 部署决策")
    if all([test_result, review_result, qc_result]):
        log("✅ 所有检查通过，准备部署...")
        deploy_result = await run_deploy()
    else:
        log("❌ 部分检查未通过，跳过部署")
        deploy_result = False
    
    # 生成报告
    log("\n📊 生成最终报告...")
    report = generate_report(task_id, test_result, review_result, qc_result, deploy_result)
    
    log("\n" + "="*60)
    log("📋 最终报告摘要")
    log("="*60)
    for key, value in report["summary"].items():
        log(f"  {key}: {value}")
    log(f"\n📌 建议: {report['recommendation']}")
    log(f"📁 报告已保存至: shared-memory/reports/{task_id}-report.json")


if __name__ == "__main__":
    asyncio.run(main())
