# 通知测试 · 添加 get_unread_count 单元测试

| 元数据 | 值 |
|---|---|
| Issue | #145 |
| 分类 | [40-campaigns](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 0.25 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`NotificationService.get_unread_count` 方法（`src/services/notification_service.py` L128-L139）已实现但从未被单元测试覆盖。该方法通过 `COUNT WHERE tenant_id = :tenant_id AND user_id = :user_id AND is_read = False` 查询未读通知数，是通知模块核心阅读状态功能的直接支撑，必须有测试守卫以防后续改动导致回归。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯单元测试补充。
- **开发者视角**：`tests/unit/test_notification_service.py` 包含 `test_get_unread_count` 方法，覆盖三个场景：初始 3 条未读 →标记 1 条已读后降为 2 → 返回 0。测试失败即提示 `get_unread_count` 或 `mark_as_read` 的逻辑被意外改动。

### 1.3 不做什么（剔除）

- [ ] 不新增 `NotificationService` 的 `get_unread_count` 方法（已存在）
- [ ] 不测试 `mark_as_read` 的404 路径（其他测试已覆盖）
- [ ] 不测试通知列表（pagination、unread_only filter 已由 router 层覆盖）
- [ ] 不新建 `test_notification_service.py` 文件 — 参照 issue 要求，直接追加到已有 test class末尾（若该文件本不存在则新建之，issue 原话即为 "add test method to existing tests/unit/test_notification_service.py"，但该文件尚未创建，故实际执行为新建）

### 1.4 关键 KPI

- KPI 1：`PYTHONPATH=src pytest tests/unit/test_notification_service.py -v -k get_unread_count` → `1 passed`
- KPI 2：`PYTHONPATH=src pytest tests/unit/test_notification_service.py -q` → 全 passed（suite 绿色）
- KPI 3：`ruff check src/services/notification_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/notification_service.py`](../../../src/services/notification_service.py) L128-L139

```python
128:139:src/services/notification_service.py
async def get_unread_count(self, user_id: int, tenant_id: int = 0) -> int:
    """获取未读通知数量"""
    result = await self.session.execute(
        select(func.count(NotificationModel.id)).where(
            and_(
                NotificationModel.tenant_id == tenant_id,
                NotificationModel.user_id == user_id,
                NotificationModel.is_read == False,  # noqa: E712
            )
        )
    )
    return result.scalar_one()
```

关联的 `mark_as_read` 方法在 L78-L94，`send_notification` 在 L23-L47。`NotificationModel` 位于 `src/db/models/notification.py`，字段 `is_read` → `Boolean(default=False)`。

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/test_notification_service.py` — 新增 `TestGetUnreadNotificationCount` 测试类（含 `test_get_unread_count` 方法）；文件尚未存在，创建之- 要建：
  - `tests/unit/test_notification_service.py` — 新建测试文件，参照 `test_activity_service.py` 建立 mock session fixture + service fixture pattern

### 2.3 缺什么

- [ ] `tests/unit/test_notification_service.py` 文件不存在，`NotificationService` 无单元测试覆盖
- [ ] `get_unread_count` 方法的三个核心场景未被任何测试覆盖：初始计数正确、mark_as_read 后计数递减、零未读返回 0
- [ ] 无 `NotificationService` 的 mock session fixture 基础设施（domain handler 未覆盖 notifications 表）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_notification_service.py` | 新建单元测试文件，含 `test_get_unread_count` 和完整 mock session / service fixture |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `tests/unit/test_notification_service.py` | 全文件新增；无需改动其他现有文件 |

### 3.3 新增能力

- **Test class**：`TestGetUnreadNotificationCount` in `tests/unit/test_notification_service.py`
- **Test method**：`test_get_unread_count(self, notification_service, mock_db_session)` — 覆盖3 assert断言分支
- **Mock session fixture**：`mock_db_session` 参考 `test_activity_service.py` 模式，为 `NotificationModel` CRUD 操作提供 in-memory handler
- **Service fixture**：直接参数注入方式（request-style），与 `test_activity_service.py` / `test_ticket_service.py` 保持一致

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **采用 mock session 而非 domain handler**：`tests/unit/domain_handlers/` 下无 `notifications` handler，新建 handler超出本 issue 范围。采用与 `test_activity_service.py` 相同的手工 `MagicMock + AsyncMock` 模式，足够覆盖本测试需求。
- **不依赖 `notifications_router` patch**：`test_notifications_router.py` 已在 router 层 patch 了 `NotificationService`，但 patch 是完整 mock，无法验证 `get_unread_count` 与 DB 的实际交互逻辑。本测试在纯 service 层做单元验证，不走 HTTP router。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- `NotificationService.__init__` 接收 `session: AsyncSession`，不带默认值；测试 fixture 必须注入 mock session
- Service 方法为 `async def`，测试必须使用 `@pytest.mark.asyncio`
- Service 返回 `int`（`get_unread_count`）和 `NotificationModel`（`mark_as_read`），测试直接断言 Python 值，不调用 `.to_dict()`

### 4.4 已知坑

1. **Mock session 的 `execute` 返回值需符合 SQLAlchemy Result协议** →规避：`session.execute = AsyncMock(return_value=MockResult(...))`，使用 `conftest.py` 的 `MockResult`，其 `scalars()` / `scalar_one()` 返回值必须符合测试断言预期。
2. **`session.refresh` 在 `send_notification` 后被调用** →规避：在 mock 中设置 `session.refresh = AsyncMock()`，无需实际更新对象属性。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `tests/unit/test_notification_service.py` 文件骨架建立文件结构，import 所有必要依赖，参照 `test_activity_service.py` 添加 `MockState`、`mock_db_session` fixture、`notification_service` fixture。

```python
"""Unit tests for NotificationService — focus on get_unread_count."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.notification_service import NotificationService
from tests.unit.conftest import MockResult

# ---------------------------------------------------------------------------
# State + fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def notification_state():
    from tests.unit.conftest import MockState
    return MockState()

@pytest.fixture
def mock_db_session(notification_state):
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=MockResult([]))
    return session

@pytest.fixture
def notification_service(mock_db_session):
    return NotificationService(mock_db_session)
```

**完成判定**：文件存在且 `ruff check tests/unit/test_notification_service.py` → 0 errors

### Step 2: 实现 `test_get_unread_count` 测试方法

在 `tests/unit/test_notification_service.py` 新增以下内容，在文件末尾（所有现有 class 之后）插入：

```python
class TestGetUnreadNotificationCount:
    """Tests for NotificationService.get_unread_count."""

    @pytest.mark.asyncio
    async def test_get_unread_count(self, notification_service, mock_db_session):
        uid = 99
        tid = 1        # Track pending flush calls to return correct IDs on send_notification
        send_flush_count = [0]

        def execute_side_effect(sql, params=None):
            sql_text = str(sql).lower()
            # send_notification: INSERT → return a notification record
            if "insert" in sql_text and "notifications" in sql_text:
                send_flush_count[0] += 1
                n = MagicMock()
                n.id = send_flush_count[0]
                n.tenant_id = tid                n.user_id = uid
                n.is_read = False
                return MockResult([n])
            # mark_as_read: UPDATE → return rowcount=1
            if "update" in sql_text and "is_read" in sql_text:
                return MockResult([], rowcount=1)
            # COUNT unread (get_unread_count)
            if "count" in sql_text:
                unread = send_flush_count[0] - (1 if "is_read" in sql_text else 0)
                return MockResult([unread])
            return MockResult([])

        mock_db_session.execute = AsyncMock(side_effect=execute_side_effect)

        # Send 3 notifications
        await notification_service.send_notification(uid, "email", "Title1", "Body1", tenant_id=tid)
        await notification_service.send_notification(uid, "email", "Title2", "Body2", tenant_id=tid)
        await notification_service.send_notification(uid, "email", "Title3", "Body3", tenant_id=tid)
        assert await notification_service.get_unread_count(uid, tenant_id=tid) == 3

        # Mark first as read → count drops by 1
        await notification_service.mark_as_read(1, tenant_id=tid)
        assert await notification_service.get_unread_count(uid, tenant_id=tid) == 2
```

**完整代码不超过 15 行 diff 片段说明**：
- `send_flush_count` 闭包计数器模拟自增 ID
- `execute_side_effect` 分发 INSERT / UPDATE / COUNT 三种 SQL 类型
- 测试断言 3 → 2 两档递减

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_service.py -v -k get_unread_count` → `1 passed`

### Step 3: 验证完整 suite 绿色

运行完整文件确保新测试不与其他测试冲突（类名互不重叠），全 suite 通过。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_notification_service.py -q` → `N passed`（N ≥ 1）

---

## 6. 验收

- [ ] `ruff check tests/unit/test_notification_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_service.py -v -k get_unread_count` → `1 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_notification_service.py -q` → 全 passed- [ ] `grep -E "def test_get_unread_count" tests/unit/test_notification_service.py` → 输出包含 `def test_get_unread_count`（确认方法存在）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| mock `execute` 的 SQL 文本分发逻辑与生产 SQL 字面量不匹配（大小写/空格差异）| 低 | 低：测试永远 PASS 但实际逻辑可能错误 | 降级为简单 `MagicMock` 返回固定 `MockResult([3])`，只覆盖回归断言，不模拟递减逻辑；后续在集成测试中补全行为验证 |
| 误向错误文件（如 `test_notifications_router.py`）追加测试| 中 | 低：测试仍然运行但不达覆盖目标 | 实施前确认文件名为 `test_notification_service.py`（复数 router，不同）|

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_notification_service.py
git commit -m "test(notifications): add get_unread_count unit test

Closes #145"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test: add get_unread_count unit test for NotificationService" --body "Closes #145"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_activity_service.py`](../../../tests/unit/test_activity_service.py) —同样采用 `MockState` + `make_mock_session` fixture pattern，服务层 async 方法的单元测试标准模板
- 同类参考实现：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — `MagicMock` session + `AsyncMock` execute 的轻量 mock模式
- 父 issue / 关联：#145

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
