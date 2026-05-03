"""
GitHub Project V2 作为 Agent 状态看板

把每个 Agent 的当前任务（共多少 pending/running/done）同步到
yihua-zhuo/agent-job 仓库的 Project V2 ("Agent Team Board")，
实现"每个人（Agent）在做什么"的可见性。

调用：
    python3 -c "
    import asyncio, os, subprocess
    os.environ['GITHUB_TOKEN'] = subprocess.check_output(['gh', 'auth', 'token']).decode().strip()
    from shared_memory.project_board import sync_all_agents_to_board
    asyncio.run(sync_all_agents_to_board())
    "
"""

from __future__ import annotations

import os
import time
from typing import Optional

import aiohttp

GITHUB_REPO = os.environ.get("GITHUB_REPO", "yihua-zhuo/agent-job")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"
PROJECT_ID = "PVT_kwHOCtbydM4BWjr2"

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}",
    "User-Agent": "agent-job-shared-memory/1.0",
}

AGENT_NAMES = ["supervisor", "code-review", "test", "qc", "deploy"]

STATUS_OPTIONS = {
    "Todo":        "f75ad846",
    "In Progress": "47fc9ee4",
    "Done":        "98236657",
}


# ─── GraphQL ────────────────────────────────────────────────────────────────────

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


# ─── Project Items ─────────────────────────────────────────────────────────────

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


def _todo_items(items: list[dict]) -> list[dict]:
    """返回所有 Status=Todo 的 DRAFT_ISSUE items"""
    result = []
    for item in items:
        if item.get("type") != "DRAFT_ISSUE":
            continue
        fvs = item.get("fieldValues", {}).get("nodes", [])
        statuses = [fv["name"] for fv in fvs if fv.get("__typename") == "ProjectV2ItemFieldSingleSelectValue"]
        if "Todo" in statuses:
            result.append(item)
    return result


# ─── GitHub REST（统计 Agent 任务数）──────────────────────────────────────────

async def gh_get(path: str, params: dict = None) -> dict | list | None:
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}{path}"
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url, headers=HEADERS, params=params or {}) as resp:
            if resp.status == 404:
                return None
            if resp.status not in (200, 304):
                raise Exception(f"GH API {resp.status}: {await resp.text()[:200]}")
            return await resp.json()


async def fetch_agent_statuses() -> dict:
    """从 GitHub Issues 统计每个 Agent 的 pending/running/done 任务数"""
    statuses = {agent: {"pending": 0, "running": 0, "done": 0} for agent in AGENT_NAMES}
    for agent in AGENT_NAMES:
        for status in ["pending", "running", "done"]:
            results = await gh_get("/search/issues", {
                "q": f"is:issue repo:{GITHUB_REPO} is:open label:type:task label:status:{status} label:agent:{agent}",
                "per_page": 1,
            })
            count = results.get("total_count", 0) if results else 0
            statuses[agent][status] = count
    return statuses


# ─── 主同步 ───────────────────────────────────────────────────────────────────

async def sync_agent(
    agent: str,
    counts: dict,
    field_id: str,
    option_ids: dict,
    items: list[dict],
) -> None:
    """
    对单个 Agent：
    - 有 running → In Progress（不在 board 上留 item，看 GitHub Issue）
    - 有 pending → Todo（确保有 1 个 draft issue 在 Todo 列）
    - 空闲 → Done（无 item，或把旧的 Todo item 移到 Done）
    """
    has_running = counts["running"] > 0
    has_pending = counts["pending"] > 0

    # 找现有的 Todo draft item
    todo_items = [item for item in _todo_items(items)]
    existing_todo = todo_items[0] if todo_items else None

    if has_running:
        # 有运行中 → In Progress；把旧的 Todo item 移到 Done
        if existing_todo:
            await update_item_status(existing_todo["id"], option_ids["Done"], field_id)
        print(f"[board] {agent}: running={counts['running']} → In Progress")
        return

    if has_pending:
        # 有待处理 → Todo
        if existing_todo:
            item_id = existing_todo["id"]
        else:
            item_id = await add_draft_issue(
                title=f"🤖 {agent}",
                body=(
                    f"Agent: {agent}\n"
                    f"Pending: {counts['pending']} | Running: {counts['running']} | Done: {counts['done']}\n"
                    f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                ),
            )
        await update_item_status(item_id, option_ids["Todo"], field_id)
        print(f"[board] {agent}: pending={counts['pending']} → Todo")
    else:
        # 空闲 → Done；把 Todo item 移到 Done（如果存在）
        if existing_todo:
            await update_item_status(existing_todo["id"], option_ids["Done"], field_id)
        print(f"[board] {agent}: idle (no board item)")


async def sync_all_agents_to_board(agent_statuses: dict = None) -> None:
    """汇总同步所有 Agent 状态到 GitHub Project board"""
    if agent_statuses is None:
        agent_statuses = await fetch_agent_statuses()

    field_id, option_ids = await get_status_field()
    items = await get_items_with_status()

    for agent, counts in agent_statuses.items():
        try:
            await sync_agent(agent, counts, field_id, option_ids, items)
        except Exception as e:
            print(f"[board] Failed to sync {agent}: {e}")


# ─── 调试 / 单测 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    import subprocess

    if not GITHUB_TOKEN:
        os.environ["GITHUB_TOKEN"] = subprocess.check_output(
            ["gh", "auth", "token"]
        ).decode().strip()

    print("Fetching agent task counts from GitHub Issues...")
    statuses = asyncio.run(fetch_agent_statuses())
    for agent, counts in statuses.items():
        print(f"  {agent}: {counts}")

    print("\nSyncing to GitHub Project board...")
    asyncio.run(sync_all_agents_to_board(statuses))
    print("Done.")
