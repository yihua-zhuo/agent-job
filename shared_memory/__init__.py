"""
Shared Memory — 基于 GitHub Issues 的多 Agent 共享记忆层

核心原理：
- yihua-zhuo/agent-job 仓库的 GitHub Issues 作为分布式 KV 数据库
- 每条任务 = 1 个 Issue，Body = JSON 任务结构，Comments = 各 Agent 执行日志
- Labels 实现状态机（pending → running → done）和 Agent 路由
- 无需自建 Redis，任何能访问 GitHub 的 Agent 都可以参与

Issue 标题约定：
  [task] <task_id>              — 任务
  [memory] <memory_id>          — 共享记忆（追加到 task comment）
  [context] <key>               — 全局上下文

标签约定：
  status:pending / status:running / status:done    — 任务状态
  type:task / type:memory / type:context             — 内容类型
  agent:supervisor / agent:test / agent:code-review   — 负责 Agent
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp


# ─── 常量 ───────────────────────────────────────────────────────────────────

GITHUB_REPO = os.environ.get("GITHUB_REPO", "yihua-zhuo/agent-job")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API   = "https://api.github.com"

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}",
    "User-Agent": "agent-job-shared-memory/1.0",
}

# 标签
LABEL_TASK        = "type:task"
LABEL_MEMORY      = "type:memory"
LABEL_CONTEXT     = "type:context"
LABEL_PENDING     = "status:pending"
LABEL_RUNNING     = "status:running"
LABEL_DONE        = "status:done"
LABEL_SUPERVISOR  = "agent:supervisor"
LABEL_CODE_REVIEW = "agent:code-review"
LABEL_TEST        = "agent:test"
LABEL_QC          = "agent:qc"
LABEL_DEPLOY      = "agent:deploy"

AGENT_LABELS = {
    "supervisor":  LABEL_SUPERVISOR,
    "code-review": LABEL_CODE_REVIEW,
    "test":        LABEL_TEST,
    "qc":          LABEL_QC,
    "deploy":      LABEL_DEPLOY,
}

POLL_INTERVAL = 3  # 秒


# ─── 数据模型 ─────────────────────────────────────────────────────────────────

@dataclass
class Task:
    task_id: str
    description: str
    agent: str
    parent_id: Optional[str] = None
    context: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    issue_number: int = 0


@dataclass
class MemoryEntry:
    memory_id: str
    author: str
    parent_id: Optional[str] = None
    content: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


# ─── GitHub API ───────────────────────────────────────────────────────────────

async def gh_get(path: str, params: dict = None, session: aiohttp.ClientSession = None) -> Optional[dict | list]:
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}{path}"
    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
    try:
        async with session.get(url, headers=HEADERS, params=params or {}) as resp:
            if resp.status == 404:
                return None
            if resp.status not in (200, 304):
                raise Exception(f"GH API {resp.status} {path}: {await resp.text()[:200]}")
            return await resp.json()
    finally:
        if own_session:
            await session.close()


async def gh_post(path: str, data: dict, session: aiohttp.ClientSession = None) -> dict | list:
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}{path}"
    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
    try:
        async with session.post(url, headers=HEADERS, json=data) as resp:
            if resp.status not in (200, 201):
                raise Exception(f"GH API {resp.status} {path}: {await resp.text()[:200]}")
            return await resp.json()
    finally:
        if own_session:
            await session.close()


async def gh_patch(path: str, data: dict, session: aiohttp.ClientSession = None) -> dict:
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}{path}"
    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
    try:
        async with session.patch(url, headers=HEADERS, json=data) as resp:
            if resp.status not in (200, 201):
                raise Exception(f"GH API {resp.status} {path}: {await resp.text()[:200]}")
            return await resp.json()
    finally:
        if own_session:
            await session.close()


async def gh_post_comment(issue_number: int, body: str, session: aiohttp.ClientSession = None) -> dict:
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/issues/{issue_number}/comments"
    own_session = False
    if session is None:
        session = aiohttp.ClientSession()
        own_session = True
    try:
        async with session.post(url, headers=HEADERS, json={"body": body}) as resp:
            if resp.status not in (200, 201):
                raise Exception(f"GH API {resp.status} comment: {await resp.text()[:200]}")
            return await resp.json()
    finally:
        if own_session:
            await session.close()


async def gh_relabel(issue_number: int, add: list, remove: list, session: aiohttp.ClientSession = None) -> None:
    """批量添加/删除标签"""
    # GitHub 单独处理 add 和 remove
    if add:
        await gh_post(f"/issues/{issue_number}/labels", {"labels": add}, session)
    if remove:
        for label in remove:
            label_escaped = label.replace(" ", "-")
            await gh_patch(f"/issues/{issue_number}/labels/{label_escaped}", {}, session)
            # 直接用 DELETE
            url = f"{GITHUB_API}/repos/{GITHUB_REPO}/issues/{issue_number}/labels/{label_escaped}"
            own_session = False
            if session is None:
                session = aiohttp.ClientSession()
                own_session = True
            try:
                async with session.delete(url, headers=HEADERS) as resp:
                    pass  # 204 / 404 都算 ok
            finally:
                if own_session:
                    await session.close()


# ─── SharedMemory ─────────────────────────────────────────────────────────────

class SharedMemory:
    """
    基于 GitHub Issues 的无中心共享记忆。

    任务流程：
    1. submit_task()  → 创建 [task] issue，状态 pending
    2. Agent 轮询 get_pending_tasks(agent=xxx)
    3. Agent claim_task() → running
    4. Agent 完成，complete_task(result=xxx) → done，评论写入结果
    5. 其他 Agent 可通过 read_task_comments() 读取同伴结果
    """

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _session_(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _task_body(self, task: Task) -> str:
        return json.dumps({
            "task_id":    task.task_id,
            "parent_id":  task.parent_id,
            "agent":      task.agent,
            "description": task.description,
            "context":    task.context,
            "result":     task.result,
            "status":     task.status,
            "created_at": task.created_at,
        }, ensure_ascii=False, indent=2)

    # ── 任务 CRUD ───────────────────────────────────────────────────────────

    async def submit_task(
        self,
        description: str,
        agent: str,
        parent_id: Optional[str] = None,
        context: dict = None,
    ) -> Task:
        s = await self._session_()
        task_id = f"task-{int(time.time() * 1000)}"
        task = Task(
            task_id=task_id,
            description=description,
            agent=agent,
            parent_id=parent_id,
            context=context or {},
            status="pending",
            issue_number=0,
        )

        issue = await gh_post("/issues", {
            "title": f"[task] {task_id}",
            "body": self._task_body(task),
            "labels": [LABEL_TASK, LABEL_PENDING, AGENT_LABELS.get(agent, LABEL_SUPERVISOR)],
        }, s)

        task.issue_number = issue["number"]
        return task

    async def get_pending_tasks(self, agent: str) -> list[Task]:
        """
        轮询指定 Agent 的 pending 任务。
        使用 GitHub 搜索 API 按标签组合查询。
        """
        s = await self._session_()
        agent_label = AGENT_LABELS.get(agent, LABEL_SUPERVISOR)
        label_filter = f"is:issue repo:{GITHUB_REPO} is:open label:{LABEL_TASK} label:{LABEL_PENDING} label:{agent_label}"

        # GitHub 搜索 API
        tasks = []
        page = 1
        while True:
            results = await gh_get("/search/issues", {
                "q": label_filter,
                "per_page": 100,
                "page": page,
            }, s)

            if not results or results.get("total_count", 0) == 0:
                break

            for item in results.get("items", []):
                try:
                    data = json.loads(item["body"])
                    tasks.append(Task(
                        task_id=data["task_id"],
                        description=data.get("description", ""),
                        agent=data.get("agent", agent),
                        parent_id=data.get("parent_id"),
                        context=data.get("context", {}),
                        result=data.get("result", {}),
                        status=data.get("status", "pending"),
                        created_at=data.get("created_at", time.time()),
                        issue_number=item["number"],
                    ))
                except (json.JSONDecodeError, KeyError):
                    pass

            if len(results.get("items", [])) < 100:
                break
            page += 1

        return tasks

    async def claim_task(self, task: Task) -> bool:
        """Agent 认领任务：pending → running"""
        s = await self._session_()
        task.status = "running"
        await gh_patch(f"/issues/{task.issue_number}", {
            "body": self._task_body(task),
        }, s)
        await gh_relabel(task.issue_number, add=[LABEL_RUNNING], remove=[LABEL_PENDING], session=s)
        return True

    async def complete_task(self, task: Task, result: dict) -> None:
        """任务完成：写入结果，pending → done"""
        s = await self._session_()
        task.result = result
        task.status = "done"
        await gh_patch(f"/issues/{task.issue_number}", {
            "body": self._task_body(task),
        }, s)
        await gh_relabel(task.issue_number, add=[LABEL_DONE], remove=[LABEL_RUNNING], session=s)

        # 写入结果到 comment
        await gh_post_comment(task.issue_number,
            f"## ✅ {task.agent} completed\n\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```",
            s)

    async def read_task_comments(self, issue_number: int) -> list[dict]:
        """读取任务的所有评论（各 Agent 写入的执行结果）"""
        s = await self._session_()
        comments = []
        page = 1
        while True:
            data = await gh_get(f"/issues/{issue_number}/comments", {
                "per_page": 100, "page": page,
            }, s)
            if not data or not isinstance(data, list):
                break
            for c in data:
                try:
                    body = c["body"]
                    # 提取 ```json ``` 块
                    if "```json" in body:
                        start = body.index("```json") + 7
                        end = body.index("```", start)
                        comments.append(json.loads(body[start:end].strip()))
                    else:
                        comments.append({"raw": body})
                except (json.JSONDecodeError, KeyError, ValueError):
                    comments.append({"raw": c.get("body", "")[:100]})
            if len(data) < 100:
                break
            page += 1
        return comments

    async def get_task(self, task_id: str) -> Optional[Task]:
        """根据 task_id 找 task（task-{timestamp} 中的 timestamp 部分即 issue number）"""
        s = await self._session_()
        parts = task_id.split("-")
        if len(parts) >= 2:
            # task-{timestamp}，取 timestamp 部分尝试作为 issue number
            possible_num = parts[-1] if parts[-1].isdigit() else None
            if possible_num:
                try:
                    issue = await gh_get(f"/issues/{possible_num}", session=s)
                    if issue and issue.get("state") == "open" and f"[task] {task_id}" == issue["title"]:
                        data = json.loads(issue["body"])
                        return Task(
                            task_id=data["task_id"],
                            description=data.get("description", ""),
                            agent=data.get("agent", ""),
                            parent_id=data.get("parent_id"),
                            context=data.get("context", {}),
                            result=data.get("result", {}),
                            status=data.get("status", "pending"),
                            created_at=data.get("created_at", time.time()),
                            issue_number=issue["number"],
                        )
                except Exception:
                    pass

        # Fallback: 搜索
        results = await gh_get("/search/issues", {
            "q": f"is:issue repo:{GITHUB_REPO} is:open [task] {task_id}",
            "per_page": 5,
        }, s)
        if results and results.get("total_count", 0) > 0:
            item = results["items"][0]
            data = json.loads(item["body"])
            return Task(
                task_id=data["task_id"],
                description=data.get("description", ""),
                agent=data.get("agent", ""),
                parent_id=data.get("parent_id"),
                context=data.get("context", {}),
                result=data.get("result", {}),
                status=data.get("status", "pending"),
                created_at=data.get("created_at", time.time()),
                issue_number=item["number"],
            )
        return None

    async def write_memory(self, author: str, parent_id: str, content: dict) -> None:
        """
        写入共享记忆：作为 comment 追加到父 task issue。
        其他 Agent 通过 read_task_comments() 读取。
        """
        s = await self._session_()
        memory_body = json.dumps({
            "author": author,
            "parent_id": parent_id,
            "content": content,
            "ts": time.time(),
        }, ensure_ascii=False, indent=2)

        # parent_id 可能是 task-{ts}，从中取出 issue number
        task = await self.get_task(parent_id)
        if task:
            await gh_post_comment(task.issue_number, f"## 💬 {author} memory\n\n```json\n{memory_body}\n```", s)

    async def write_context(self, key: str, value: dict) -> None:
        """写入全局上下文（单独的 context issue）"""
        s = await self._session_()
        title = f"[context] {key}"
        results = await gh_get("/search/issues", {
            "q": f"is:issue repo:{GITHUB_REPO} is:open {title}",
            "per_page": 5,
        }, s)

        body = json.dumps({"key": key, "value": value, "updated_at": time.time()}, ensure_ascii=False, indent=2)
        if results and results.get("total_count", 0) > 0:
            await gh_patch(f"/issues/{results['items'][0]['number']}", {"body": body}, s)
        else:
            await gh_post("/issues", {
                "title": title,
                "body": body,
                "labels": [LABEL_CONTEXT],
            }, s)

    async def read_context(self, key: str) -> Optional[dict]:
        """读取全局上下文"""
        s = await self._session_()
        results = await gh_get("/search/issues", {
            "q": f"is:issue repo:{GITHUB_REPO} is:open [context] {key}",
            "per_page": 5,
        }, s)
        if results and results.get("total_count", 0) > 0:
            try:
                return json.loads(results["items"][0]["body"])["value"]
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# ─── 全局单例 ─────────────────────────────────────────────────────────────────

_memory: Optional[SharedMemory] = None

def get_shared_memory() -> SharedMemory:
    global _memory
    if _memory is None:
        _memory = SharedMemory()
    return _memory