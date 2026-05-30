# tests/unit/domain_handlers/agent_tasks.py
from tests.unit.conftest import MockRow, MockResult

ORDER = 60  # load after stateless handlers, before customerdef make_agent_task_handler(state: MockState):
    def handler(sql_text: str, params: dict):
        low = sql_text.lower()
        if "insert into agent_tasks" in low:
            task_id = f"atask_{state.agent_tasks_next_id:08x}"
            state.agent_tasks_next_id += 1
            row = MockRow({"task_id": task_id, "tenant_id": params.get("tenant_id"),
 "description": params.get("description", ""),
                           "status": "pending", "subtasks": "[]",
                           "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z"})
            state.agent_tasks[task_id] = row
            return MockResult([row])
        if "from agent_tasks where task_id" in low and "delete" not in low:
            key = params.get("task_id")
            if key in state.agent_tasks and state.agent_tasks[key]["tenant_id"] == params.get("tenant_id"):
                return MockResult([state.agent_tasks[key]])
            return MockResult([])
        if "delete from agent_tasks" in low:
            key = params.get("task_id")
            if key in state.agent_tasks:
                del state.agent_tasks[key]
            return MockResult([])
        if "count" in low and "agent_tasks" in low:
            return MockResult([{"count": len(state.agent_tasks)}])
        # list / filter by status + tenant
        if " from agent_tasks" in low:
            rows = [r for r in state.agent_tasks.values()
                    if r["tenant_id"] == params.get("tenant_id")]
            if "status" in params and params["status"]:
                rows = [r for r in rows if r["status"] == params["status"]]
            return MockResult(rows)
        return None
    return handler

def get_handlers(state):
    return [make_agent_task_handler(state)]

__all__ = ["get_handlers", "make_agent_task_handler"]
```

**完成判定**：`PYTHONPATH=src python -c "from tests.unit.domain_handlers.agent_tasks import get_handlers, make_agent_task_handler; print('ok')"` → `ok`

---

### Step 3: Create `tests/unit/test_agent_task_service.py`

创建 service 层测试文件，引用 `test_customer_service.py` + `test_sla_service.py` 的模式。直接实例化 `AgentTaskService(make_mock_session(...))` 并调用方法。

**文件结构（≥4 个测试用例）：**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from tests.unit.conftest import make_mock_session, MockState
from tests.unit.domain_handlers.agent_tasks import make_agent_task_handler

# 1. Happy path — create returns task_id with 'atask_' prefix
#2. Error path — get_agent_task raises NotFoundException (missing task_id, fixture empties list)
# 3. Filter path — list_agent_tasks with status='completed' returns only matching rows
# 4. Tenant isolation — task created under tenant1 is not visible under tenant 2
# 5. Delete path — delete_agent_task removes from state (rowcount check)

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_agent_task_handler(state)], state)

class TestAgentTaskServiceMethods:
    @pytest.mark.asyncio
    async def test_create_returns_task_id_with_prefix(self, mock_db_session):
        from src.services.agent_task_service import AgentTaskService
        svc = AgentTaskService(mock_db_session)
        result = await svc.create_agent_task(description="Fix login bug", tenant_id=1)
        assert result.task_id.startswith("atask_")
        assert result.description == "Fix login bug"

    @pytest.mark.asyncio
    async def test_get_task_raises_not_found_for_missing_id(self, mock_db_session):
        svc = AgentTaskService(mock_db_session)
        with pytest.raises(NotFoundException):
            await svc.get_agent_task("atask_xxxxxxxx", tenant_id=1)

    @pytest.mark.asyncio
    async def test_list_tasks_filters_by_status(self, mock_db_session):
        # 需要先创建几个 task，然后按 status 过滤
        ...

    @pytest.mark.asyncio
    async def test_list_tasks_tenant_isolation(self, mock_db_session):
        # tenant2 returns empty list
        ...

    @pytest.mark.asyncio
    async def test_delete_removes_task(self, mock_db_session):
        # create then delete, verify NotFoundException after        ...
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_task_service.py -v` → `5 passed`（或运行时的实际数量）

---

### Step 4: Create `tests/unit/test_agent_task_router.py`

创建路由层测试文件，参考 `tests/unit/test_tasks.py` 的 `client_with_service` fixture 工厂模式。

**文件结构（≥ 6 个测试用例）：**

```python
# Pattern: monkeypatch AgentTaskService in api.routers.agent_tasks to a MagicMock
# App with require_auth overridden + get_db overridden → AsyncClient

async def test_create_returns_envelope_with_task_id():
    mock_svc = MagicMock()
    mock_svc.create_agent_task = AsyncMock(return_value=MockAgentTask(...))
    with monkeypatch.context() as mp:
        mp.setattr("api.routers.agent_tasks.AgentTaskService", lambda _: mock_svc)
        async with AsyncClient(...) as ac:
            resp = await ac.post("/agents/tasks", json={"description": "..."})
 assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["task_id"].startswith("atask_")

async def test_list_returns_envelope_with_items_and_total():
    ...

async def test_get_returns_correct_envelope():
    ...

async def test_get_missing_returns_404():
    # service raises NotFoundException → global handler → 404
    ...

async def test_filter_by_status_query_param():
    ...
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_agent_task_router.py -v` → `6 passed`（或运行时的实际数量）

---

### Step 5: Verify total test run and lint

确保所有新文件通过 ruff 和 pytest：

```bash
ruff check tests/unit/test_agent_task_service.py tests/unit/test_agent_task_router.py tests/unit/domain_handlers/agent_tasks.py
#期望 exit 0

PYTHONPATH=src pytest tests/unit/test_agent_task_service.py tests/unit/test_agent_task_router.py -v
# 期望 ≥10 passed total（service: ≥4 + router: ≥6）
```

**完成判定**：`ruff check tests/unit/test_agent_task_service.py tests/unit/test_agent_task_router.py tests/unit/domain_handlers/agent_tasks.py` → exit 0

---

## 6. 验收

- [ ] `ruff check tests/unit/test_agent_task_service.py tests/unit/test_agent_task_router.py tests/unit/domain_handlers/agent_tasks.py` →0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_agent_task_service.py -v` → ≥4 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_agent_task_router.py -v` → ≥ 6 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_agent_task_service.py tests/unit/test_agent_task_router.py -v` → ≥10 passed total
- [ ] `PYTHONPATH=src python -c "from tests.unit.conftest import MockState; s = MockState(); assert hasattr(s, 'agent_tasks')"` → 无输出（pass）/ exit 0
- [ ] `PYTHONPATH=src python -c "from tests.unit.domain_handlers.agent_tasks import get_handlers, make_agent_task_handler"` → exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `#622` 的接口签名与本文档假设不符，导致测试中的 `.task_id` / `.description` 等属性访问失败 | 中 | 中 | 修改测试文件中的 mock 返回值和属性名；AgentTaskService 的接口在 #622 的 router单元测试（`test_agent_task_router.py` 本身）中已验证，不阻塞 #629 |
| `MockState` 新增字段被其他模块的 `MockState` 子类覆盖导致 AttributeError | 低 | 中 | 将 `agent_tasks` / `agent_tasks_next_id` 加到 `MockState` 声明处，明确要求新 handler 使用 `getattr(state, 'agent_tasks', {})` 的 getattr fallback 模式 |
| Domain handler 新增的文件导致 `conftest.py` 的 `_load_domain_handler_modules()` 启动时加载失败 | 低 | 高 | 若模块导入报错，`RuntimeError` 在 collection 时立即暴露；快速修复：删除 `__init__.py` 中的错误 import |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_agent_task_service.py tests/unit/test_agent_task_router.py tests/unit/domain_handlers/agent_tasks.py tests/unit/conftest.py
git commit -m "test(unit): add unit tests for AgentTaskService and agent_tasks router"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#623): unit tests for AgentTaskService and router" --body "Closes #623## Summary
- Add `tests/unit/domain_handlers/agent_tasks.py` with `make_agent_task_handler(state)` + `get_handlers(state)`
- Add `MockState.agent_tasks` / `MockState.agent_tasks_next_id` fields in conftest
- Add `tests/unit/test_agent_task_service.py` (4 tests: create-atask_ prefix, NotFoundException, list-filters, tenant isolation)
- Add `tests/unit/test_agent_task_router.py` (6 tests: envelope shape, 201/200/404 responses, query param filters)

## Test plan
- [ ] ruff check + exit 0
- [ ] pytest tests/unit/test_agent_task_service.py → ≥ 4 passed
- [ ] pytest tests/unit/test_agent_task_router.py → ≥ 6 passed

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"

# 2. 更新进度# 本板块文档 §Changelog 表格新增一行由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_tasks.py`](../../tests/unit/test_tasks.py) — router-level test pattern (`monkeypatch + AsyncClient`，`client_with_service` fixture factory）
- 同类参考实现：[`tests/unit/domain_handlers/automation.py`](../../tests/unit/domain_handlers/automation.py) — stateful domain handler pattern (`make_automation_handler(state)` / `get_handlers(state)`)
- 同类参考实现：[`tests/unit/domain_handlers/tasks.py`](../../tests/unit/domain_handlers/tasks.py) — stateless domain handler for tasks table
- 父 issue / 关联：#42（Agent Task Router — natural language task dispatch, defines entity shape）
- 依赖 issue：#622（Add POST and GET /agents/tasks router endpoints — creates the service and router being tested）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
