"""
GitHub Project V2 作为 Agent 状态看板

把每个 Agent 的当前任务状态同步到
yihua-zhuo/agent-job 仓库的 Project V2 ("Agent Team Board")，
实现"每个人（Agent）在做什么"的可见性。

Usage:
    # 从本地 shared memory 读取状态并同步（推荐）
    from shared_memory.project_board import sync_all_agents_to_board
    sync_all_agents_to_board()

    # 或者手动传入状态 dict
    from shared_memory.project_board import sync_all_agents_to_board
    sync_all_agents_to_board(agent_statuses={
        "supervisor":  {"pending": 0, "running": 0, "done": 0},
        "code-review": {"pending": 2, "running": 0, "done": 0},
        ...
    })
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Optional

import aiohttp

GITHUB_REPO = os.environ.get("GITHUB_REPO", "yihua-zhuo/agent-job")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"
PROJECT_ID = "PVT_kwHOCtbydM4BWjr2"

AGENT_NAMES = ["supervisor", "code-review", "test", "qc", "deploy"]


# ─── GitHub GraphQL ─────────────────────────────────────────────────────────────

async def gql(query: str, variables: dict = None) -> dict:
    async with aiohttp.ClientSession() as sess:
        async with sess.post(
            f"{GITHUB_API}/graphql",
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}"},
            json={"query": query, "variables": variables or {}},
        ) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise Exception(f"GQL {resp.status}: {text[:300]}")
            result = await resp.json()
            if result.get("errors"):
                raise Exception(f"GQL errors: {result['errors']}")
            return result["data"]


async def get_items_with_status() -> list[dict]:
    """获取 Project 所有 items，含 id + type + fieldValues（Status 字段）"""
    data = await gql(
        """
        query GetItems($project: ID!) {
            node(id: $project) {
                ... on ProjectV2 {
                    items(first: 100) {
                        nodes {
                            id
                            type
                            fieldValues(first: 10) {
                                nodes {
                                    __typename
                                    ... on ProjectV2ItemFieldSingleSelectValue {
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """,
        {"project": PROJECT_ID},
    )
    return data["node"]["items"]["nodes"]


async def get_status_field() -> tuple[str, dict]:
    """返回 (field_id, {option_name: option_id})"""
    data = await gql(
        """
        query GetFields($project: ID!) {
            node(id: $project) {
                ... on ProjectV2 {
                    fields(first: 20) {
                        nodes {
                            __typename
                            ... on ProjectV2SingleSelectField {
                                id name options { id name color }
                            }
                        }
                    }
                }
            }
        }
        """,
        {"project": PROJECT_ID},
    )
    for field in data["node"]["fields"]["nodes"]:
        if field.get("__typename") == "ProjectV2SingleSelectField" and field.get("name") == "Status":
            options = {opt["name"]: opt["id"] for opt in field.get("options", [])}
            return field["id"], options
    raise Exception("Status field not found in project")


async def add_draft_issue(title: str, body: str) -> str:
    """在 Project 创建 draft issue，返回 item id"""
    data = await gql(
        """
        mutation AddDraft($project: ID!, $title: String!, $body: String) {
            addProjectV2DraftIssue(input: {projectId: $project, title: $title, body: $body}) {
                projectItem { id }
            }
        }
        """,
        {"project": PROJECT_ID, "title": title, "body": body},
    )
    return data["addProjectV2DraftIssue"]["projectItem"]["id"]


async def update_item_status(item_id: str, status_option_id: str, field_id: str) -> None:
    """将 Project item 的 Status 字段更新为指定 option"""
    await gql(
        """
        mutation SetStatus($project: ID!, $item: ID!, $field: ID!, $value: String!) {
            updateProjectV2ItemFieldValue(input: {
                projectId: $project
                itemId: $item
                fieldId: $field
                value: { singleSelectOptionId: $value }
            }) { projectV2Item { id } }
        }
        """,
        {
            "project": PROJECT_ID,
            "item": item_id,
            "field": field_id,
            "value": status_option_id,
        },
    )


# ─── Project item helpers ───────────────────────────────────────────────────────

def _todo_items(items: list[dict]) -> list[dict]:
    """返回所有 Status=Todo 的 DRAFT_ISSUE items"""
    result = []
    for item in items:
        if item.get("type") != "DRAFT_ISSUE":
            continue
        fvs = item.get("fieldValues", {}).get("nodes", [])
        statuses = [
            fv["name"]
            for fv in fvs
            if fv.get("__typename") == "ProjectV2ItemFieldSingleSelectValue"
        ]
        if "Todo" in statuses:
            result.append(item)
    return result


# ─── Agent 状态读取（从本地 shared memory）──────────────────────────────────

def fetch_agent_statuses_from_memory() -> dict:
    """
    从本地 shared memory JSON 文件读取各 Agent 的 pending/running/done 任务数。
    读取 orchestrator_queue.json，统计每个 agent 在 tasks[].agents[] 中的状态分布。
    """
    import json as _json
    from pathlib import Path

    root = Path(os.environ.get(
        "AGENT_JOB_SHARED_MEMORY",
        "/home/node/.openclaw/workspace/agent-job-shared-memory",
    ))
    queue_path = root / "orchestrator_queue.json"

    statuses = {agent: {"pending": 0, "running": 0, "done": 0} for agent in AGENT_NAMES}

    if not queue_path.exists():
        return statuses

    try:
        with open(queue_path, "r", encoding="utf-8") as f:
            queue = _json.load(f)
    except Exception:
        return statuses

    for task in queue.get("tasks", []):
        for agent in task.get("agents", []):
            agent_id = agent.get("agent_id")
            if agent_id not in statuses:
                continue
            s = agent.get("status", "pending")
            if s == "pending":
                statuses[agent_id]["pending"] += 1
            elif s == "running":
                statuses[agent_id]["running"] += 1
            elif s in ("completed", "done"):
                statuses[agent_id]["done"] += 1

    return statuses


# ─── 主同步逻辑 ────────────────────────────────────────────────────────────────

async def sync_agent(
    agent: str,
    counts: dict,
    field_id: str,
    option_ids: dict,
    items: list[dict],
) -> None:
    """
    对单个 Agent：
    - 有 running  → In Progress（board 不留 item，GitHub Issues 上可见）
    - 有 pending  → Todo（确保有 1 个 draft issue 在 Todo 列）
    - 空闲        → Done（把旧的 Todo item 移到 Done 列）
    """
    has_running = counts["running"] > 0
    has_pending = counts["pending"] > 0

    todo_items = [item for item in _todo_items(items)]
    existing_todo = todo_items[0] if todo_items else None

    if has_running:
        if existing_todo:
            await update_item_status(existing_todo["id"], option_ids["Done"], field_id)
        print(f"[board] {agent}: running={counts['running']} → In Progress")
        return

    if has_pending:
        if existing_todo:
            item_id = existing_todo["id"]
        else:
            item_id = await add_draft_issue(
                title=f"🤖 {agent}",
                body=(
                    f"**Agent:** `{agent}`\n"
                    f"**Pending:** {counts['pending']} | **Running:** {counts['running']} | **Done:** {counts['done']}\n"
                    f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                ),
            )
        await update_item_status(item_id, option_ids["Todo"], field_id)
        print(f"[board] {agent}: pending={counts['pending']} → Todo")
    else:
        if existing_todo:
            await update_item_status(existing_todo["id"], option_ids["Done"], field_id)
        print(f"[board] {agent}: idle → Done")


async def sync_all_agents_to_board(agent_statuses: dict = None) -> None:
    """
    同步所有 Agent 状态到 GitHub Project V2 board。

    Args:
        agent_statuses: 可选，默认为从本地 shared memory 读取。
                        格式: {agent_name: {"pending": int, "running": int, "done": int}}
    """
    if agent_statuses is None:
        agent_statuses = fetch_agent_statuses_from_memory()

    field_id, option_ids = await get_status_field()
    items = await get_items_with_status()

    for agent, counts in agent_statuses.items():
        try:
            await sync_agent(agent, counts, field_id, option_ids, items)
        except Exception as e:
            print(f"[board] Failed to sync {agent}: {e}")


# ─── 调试 / CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio

    if not GITHUB_TOKEN:
        os.environ["GITHUB_TOKEN"] = subprocess.check_output(
            ["gh", "auth", "token"]
        ).decode().strip()

    print("Fetching agent task counts from local shared memory...")
    statuses = fetch_agent_statuses_from_memory()
    for agent, counts in statuses.items():
        print(f"  {agent}: {counts}")

    print("\nSyncing to GitHub Project board...")
    asyncio.run(sync_all_agents_to_board(statuses))
    print("Done.")