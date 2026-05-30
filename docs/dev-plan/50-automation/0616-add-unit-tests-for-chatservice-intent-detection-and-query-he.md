# ChatService · Add unit tests for intent detection and query helpers

| 元数据 | 值 |
|---|---|
| Issue | #616 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | #615 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

ChatService currently has intent detection logic and query helper methods (get_active_conversation, classify_intent, build_context_dict) with no unit test coverage. Without tests, any regression in intent classification or query helper behavior goes undetected. The intent classification switch covers multiple branches (support, sales, cancel, feedback, escalation, unknown) that need isolated assertion coverage.

### 1.2 做完后

- **用户视角**：无用户可见变化 — pure unit-test addition.
- **开发者视角**：Developers can run `pytest tests/unit/test_chat_service.py -v` and get a green signal before merging intent-detection changes. The mock session infrastructure (`make_chat_session_handler`, `make_chat_message_handler`) becomes reusable across all chat-adjacent test files.

### 1.3 不做什么（剔除）

- [ ] No integration tests — real DB not used; all SQL is mocked via `MockResult` / `MockRow` pattern.
- [ ] No router-level tests (no HTTP layer, no FastAPI `TestClient`).
- [ ] No changes to `ChatService` itself or any ORM model; only test file and conftest helpers.
- [ ] No Alembic migration; no schema change.

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → ≥ 8 passed]
- [指标 2：`ruff check tests/unit/test_chat_service.py tests/unit/conftest.py` → 0 errors]
- [指标 3：intent classification branch count ≥ 6 (support / sales / cancel / feedback / escalation / unknown/fallback)]

---

## 2. 当前现状（起点）

### 2.1 现有实现

ChatService implementation is expected at `src/services/chat_service.py`.

```
TBD - 待验证：src/services/chat_service.py — 需要确认以下方法存在：
  - classify_intent(user_message: str) -> str
  - get_active_conversation(tenant_id: int, session: AsyncSession) -> Conversation | None
  - build_context_dict(conversation: Conversation) -> dict
```

If the file does not exist, this board will need to be split to cover the service implementation first (tracked separately).

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/conftest.py` — 添加 `make_chat_session_handler` 和 `make_chat_message_handler`
- 要建：
  - `tests/unit/test_chat_service.py` — 新建，完整 mock session 隔离测试

### 2.3 缺什么

- [ ] `tests/unit/conftest.py` 缺少 `make_chat_session_handler` — 需要参照 `make_customer_handler`/`make_user_handler` 的工厂模式实现，以支持 chat_session 表的 INSERT/SELECT/COUNT mock
- [ ] `tests/unit/conftest.py` 缺少 `make_chat_message_handler` — 同上，用于 chat_message 表 mock
- [ ] `tests/unit/test_chat_service.py` 不存在 — 无任何 intent classification 或 query helper 测试
- [ ] Intent classification branches (support/sales/cancel/feedback/escalation/unknown) 没有隔离覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_chat_service.py` | ChatService intent detection + query helper 单元测试，mock session，无真实 DB |
| `alembic/versions/<id>_add_chat_tables.sql` | 不需要 — 本 issue 不涉及 schema 变更 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) | 新增 `make_chat_session_handler(state)` 和 `make_chat_message_handler(state)` — 参照现有 `make_customer_handler` 工厂模式实现 |

### 3.3 新增能力

- **Test fixture**：`make_chat_session_handler(state)` — 返回可注册到 `make_mock_session(handlers)` 的 SQL mock handler
- **Test fixture**：`make_chat_message_handler(state)` — 同上，for chat_message 表
- **Unit test**：6 intent classification cases (support / sales / cancel / feedback / escalation / unknown fallback) + 1 fallback unknown
- **Unit test**：2 query helper cases (get_active_conversation returns dict / returns None)
- **Unit test**：1 build_context_dict case — asserts correct domain dict shape

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Mock session pattern**（`make_mock_session(handlers)`）不选 `unittest.mock.patch` — 与 CLAUDE.md §Unit Test SQL Mocks 一致；每个测试文件定义自己的 `mock_db_session` fixture，不使用全局 autouse patch。
- **Factory function `make_chat_session_handler(state)` over inline dict** — 保持与 `make_customer_handler` 等已有 handler 的一致性；stateful（tenant-scoped）mock 更容易维护。

### 4.2 版本约束

<!-- 无新依赖引入，本段删掉 -->

### 4.3 兼容性约束

- Mock handler 必须实现 `execute(sql, params=None)` 方法，返回 `MockResult`；参考 `make_customer_handler` 的调用签名。
- `make_mock_session(handlers)` 的 `handlers` 参数顺序不影响查询路由 — 匹配按 statement type 而不是顺序。
- 测试文件不可 import `from src.db.models...` 以外的真实模型；使用 `MockRow` / `MockResult` 替代。

### 4.4 已知坑

1. **conftest.py handler 签名漂移** → 规避：实现前对照 `make_customer_handler` 确认 `execute` 方法和 `MockState` 用法完全一致。
2. **`MockRow` 属性拼写** → 规避：测试中引用 `row.tenant_id` 时必须确认 mock row 返回的 key 与 service 代码中访问的属性名一致（不要用 `row['tenant_id']` 除非 service 也这样写）。
3. **intent classification 硬编码分支** → 规避：测试case 标题应注明「当 X 时 → Y」，若 service 实现变更导致分支增减，测试应报错而非静默跳过未知分支。

---

## 5. 实现步骤（按顺序）

### Step 1: Add `make_chat_session_handler` to conftest.py

参照 `make_customer_handler` 的工厂模式实现：

```python
# tests/unit/conftest.py 新增
def make_chat_session_handler(state: MockState) -> dict:
    """Returns a SQL mock handler for chat_session table."""
    def handler(sql: str, params: dict | None = None):
        params = params or {}
        if re.match(r'\ASELECT\b', sql, re.IGNORECASE):
            if 'WHERE id' in sql and 'tenant_id' in sql:
                row = next((r for r in state.chat_sessions if r['id'] == params.get('id') and r['tenant_id'] == params.get('tenant_id')), None)
                return MockResult([MockRow(row)] if row else [])
        return MockResult([])
    return {'execute': handler}
```

在 `conftest.py` 顶部添加 `import re`（如尚未存在）。

**完成判定**：`ruff check tests/unit/conftest.py` → 0 errors

---

### Step 2: Add `make_chat_message_handler` to conftest.py

同上；mock chat_message 表 SELECT（按 conversation_id + tenant_id filter）。

**完成判定**：`ruff check tests/unit/conftest.py` → 0 errors

---

### Step 3: Create `tests/unit/test_chat_service.py` with mock_db_session fixture

文件结构：

```python
import pytest
from tests.unit.conftest import (
    make_mock_session,
    make_chat_session_handler,
    make_chat_message_handler,
    MockState,
)
from unittest.mock import AsyncMock

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([
        make_chat_session_handler(state),
        make_chat_message_handler(state),
    ])

@pytest.fixture
def chat_service(mock_db_session):
    from services.chat_service import ChatService  # import here to avoid module-load in conftest
    return ChatService(mock_db_session)
```

**完成判定**：`ruff check tests/unit/test_chat_service.py` → 0 errors

---

### Step 4: Write intent classification test cases

每个 case 独立测试一个分类分支：

```python
class TestClassifyIntent:
    @pytest.mark.parametrize("message,expected", [
        ("I need help with my order", "support"),
        ("I'd like to upgrade my plan", "sales"),
        ("I want to cancel my subscription", "cancel"),
        ("Your product broke", "feedback"),
        ("This is unacceptable, I want a manager", "escalation"),
        ("What is the weather today", "unknown"),
    ])
    def test_classify_intent_returns_correct_domain(self, chat_service, message, expected):
        result = chat_service.classify_intent(message)
        assert result == expected

    def test_classify_intent_fallback_unknown(self, chat_service):
        result = chat_service.classify_intent("asdfghjkl")
        assert result == "unknown"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_chat_service.py::TestClassifyIntent -v` → 7 passed

---

### Step 5: Write query helper test cases

```python
class TestQueryHelpers:
    def test_get_active_conversation_returns_dict(self, chat_service, mock_db_session):
        result = await chat_service.get_active_conversation(tenant_id=1, session=mock_db_session)
        assert isinstance(result, dict)
        assert 'id' in result

    def test_get_active_conversation_returns_none_when_no_row(self, chat_service, mock_db_session):
        result = await chat_service.get_active_conversation(tenant_id=9999, session=mock_db_session)
        assert result is None

    def test_build_context_dict_returns_correct_keys(self, chat_service):
        mock_conv = MockRow({'id': 1, 'tenant_id': 1, 'user_id': 10, 'status': 'open'})
        result = chat_service.build_context_dict(mock_conv)
        assert isinstance(result, dict)
        assert result.get('id') == 1
        assert 'tenant_id' in result
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_chat_service.py::TestQueryHelpers -v` → 3 passed

---

### Step 6: Final verification — run full file

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → ≥ 10 passed

---

## 6. 验收

- [ ] `ruff check tests/unit/conftest.py tests/unit/test_chat_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → ≥ 10 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → 0 failed
- [ ] No new alembic migration generated (git status 确认无 `alembic/versions/` 变更)
- [ ] `ruff check tests/unit/conftest.py` → 0 errors (conftest 不引入新依赖)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `ChatService` 方法签名与预期不符（e.g. 返回 `Conversation` ORM 对象而非 dict） | 低 | 中 | 调整 MockRow 返回的 mock 对象结构；测试不依赖 service 实现细节，只验证返回类型/dict key |
| `make_chat_session_handler` 与 service 查询语句语法不匹配 | 中 | 中 | 在 conftest 中添加 debug print temporarily，或在 Step 1-2 后先写一个 integration smoke test 验证 SQL 语句 |
| conftest handler 注册到 `make_mock_session` 后路由不到（空结果） | 低 | 高 | 参照 `make_customer_handler` 的 `execute` 正则匹配模式，确保 regex 覆盖实际生成的 SQL（可用 `print(sql)` 在测试内临时 debug） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/conftest.py tests/unit/test_chat_service.py
git commit -m "test(chat): add unit tests for intent detection and query helpers (#616)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(chat): unit tests for ChatService intent detection (#616)" --body "Closes #616"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — make_customer_handler 工厂模式
- 同类参考实现：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — parametrize + MockState pattern
- 父 issue / 关联：#43, #615

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
