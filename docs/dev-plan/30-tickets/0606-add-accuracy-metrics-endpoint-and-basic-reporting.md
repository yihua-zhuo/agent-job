# 分类准确率指标 · Add GET /tickets/categorization/metrics endpoint

| 元数据 | 值 |
|---|---|
| Issue | #606 |
| 分类 | [30-tickets](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [0605-构建工单分类数据模型](../0605-构建工单分类数据模型-and-migration.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #605 建立了工单分类结果的数据模型（`TicketCategorizationModel`），但仅有模型还不够——需要有一个 metrics 服务方法聚合统计数据，并在 Router 层暴露 `GET /tickets/categorization/metrics` 端点，供前端仪表盘或报表系统调用。没有 metrics 端点，分类系统的质量就无法量化，override 率、置信度等关键指标无从追踪。

### 1.2 做完后

- **用户视角**：`GET /tickets/categorization/metrics` 返回当前租户下工单分类系统的准确率报告：总分类数、人工 override 数、override 率、平均置信度、分类型和分优先级 breakdown。
- **开发者视角**：`TicketCategorizationService.get_metrics(tenant_id)` 方法可直接调用；Router 新增 `GET /tickets/categorization/metrics` 端点，返回 JSON envelope。

### 1.3 不做什么（剔除）

- [ ] 不实现前端 UI 展示 metrics 数据（留待前端板块）
- [ ] 不实现历史趋势分析或时间序列查询（仅返回当前时刻快照）
- [ ] 不修改 `TicketCategorizationModel` 的 schema（依赖 #605 已建立的模型）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_metrics.py -v` → ≥ 3 passed
- `ruff check src/services/ticket_categorization_service.py` → 0 errors
- `ruff check src/api/routers/tickets.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口（TBD - 待验证：issue #605 生成的新模型文件路径，预计为 `src/db/models/ticket_categorization.py`）：

Issue #605 在本分支依赖链中先完成，生成 `TicketCategorizationModel`。若无该文件，说明 #605 尚未完成，本板块无法实施。

参考同仓库相似统计方法：[`src/services/ticket_service.py`](../../src/services/ticket_service.py) L{359}-L{379}

```python:src/services/ticket_service.py
async def get_sla_breaches(self, tenant_id: int = 0) -> list[TicketModel]:
    now = datetime.now(UTC)
    result = await self.session.execute(
        select(TicketModel).where(
            and_(
                TicketModel.tenant_id == tenant_id,
                TicketModel.resolved_at.is_(None),
                ...
            )
        )
    )
    return list(result.scalars().all())
```

参考 Router 的 metrics 聚合模式：[`src/api/routers/tickets.py`](../../src/api/routers/tickets.py) L{434}-L{446}

```python:src/api/routers/tickets.py
@tickets_router.get("/sla/summary")
async def get_sla_summary(...):
    sla_svc = SLAService(session)
    counts = await sla_svc.get_sla_summary(tenant_id=ctx.tenant_id or 0)
    return {"success": True, "data": SLAStatCard(**counts).model_dump()}
```

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/tickets.py`](../../src/api/routers/tickets.py) — 新增 `GET /tickets/categorization/metrics` 端点
  - [`tests/unit/test_tickets_router.py`](../../tests/unit/test_tickets_router.py) — 新增 metrics 端点测试用例
- 要建：
  - `src/services/ticket_categorization_service.py` — 新建 `TicketCategorizationService`，含 `get_metrics()` 方法
  - `tests/unit/test_ticket_categorization_metrics.py` — 新建单元测试，验证 metrics 响应结构

### 2.3 缺什么

- [ ] `TicketCategorizationService.get_metrics(tenant_id)` — 聚合查询，统计 override 率、平均置信度、分 type/priority breakdown
- [ ] `GET /tickets/categorization/metrics` 端点 — 挂载在 `tickets_router`，返回 JSON envelope
- [ ] 单元测试覆盖 metrics 响应结构（success path + boundary + error）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/ticket_categorization_service.py` | `TicketCategorizationService` 类，含 `get_metrics(tenant_id)` 方法，返回聚合统计数据 |
| `tests/unit/test_ticket_categorization_metrics.py` | 单元测试：验证 metrics 响应 JSON 结构、边界情况（无数据） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/tickets.py`](../../src/api/routers/tickets.py) | 新增 `GET /tickets/categorization/metrics` 端点，调用 `TicketCategorizationService.get_metrics()` |
| [`tests/unit/test_tickets_router.py`](../../tests/unit/test_tickets_router.py) | 新增 `test_get_categorization_metrics` 测试用例 |

### 3.3 新增能力

- **Service method**：`TicketCategorizationService.get_metrics(self, tenant_id: int) -> dict`
- **API endpoint**：`GET /tickets/categorization/metrics` → `{"success": true, "data": {...}}`
- 返回字段：`total_categorized`, `override_count`, `override_rate` (float, 0-1), `average_confidence` (float), `by_type` (dict), `by_priority` (dict)

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **返回 dict 而非 Pydantic model**：metrics 数据是即时聚合结果，无持久化需求，直接返回 dict 由 Router 序列化更简洁，避免定义过多 stats schema 类
- **用 SQL COUNT + AVG 聚合，不在 Python 侧计算**：减少内存占用，数据库层面直接算 `COUNT(*)`, `AVG(confidence)`, `SUM(CASE WHEN overridden THEN 1 ELSE 0 END)`

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：`get_metrics` 必须 `WHERE tenant_id = :tenant_id`
- Service 返回 dict（聚合结果不需要 ORM 模型），Router 调用 `.to_dict()` 是错误的（无 ORM 对象）
- Service 错误抛 `AppException` 子类，不返回 `ApiResponse.error()`
- 所有统计查询按 `tenant_id` 过滤，防止跨租户数据泄露

### 4.4 已知坑

1. **SQL AVG(NULL) 行为** → 规避：当所有记录 confidence 为 NULL 时，`AVG(confidence)` 返回 NULL 而非 0 → 在 service 层做 `coalesce(avg(confidence), 0.0)`
2. **count=0 时 override_rate 需显式返回 0.0** → 规避：当 total=0 时避免除以零，单独处理 `override_rate = override_count / total if total > 0 else 0.0`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/services/ticket_categorization_service.py`

新建 service 文件，定义 `TicketCategorizationService`，实现 `get_metrics()` 方法。

操作：
- a) 创建 `src/services/ticket_categorization_service.py`
- b) import `TicketCategorizationModel`（来自 #605 生成的文件 `src/db/models/ticket_categorization.py`）
- c) 使用 `func.count`, `func.avg`, `func.sum` 做 SQL 聚合
- d) 分 group by `category` 和 `priority` 统计

示例代码：

```python
"""Ticket categorization metrics service."""

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.ticket_categorization import TicketCategorizationModel


class TicketCategorizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_metrics(self, tenant_id: int) -> dict:
        # Overall stats
        total_result = await self.session.execute(
            select(
                func.count(TicketCategorizationModel.id).label("total"),
                func.coalesce(func.avg(TicketCategorizationModel.confidence), 0.0).label("avg_confidence"),
                func.sum(
                    case((TicketCategorizationModel.overridden == True, 1), else_=0)
                ).label("override_count"),
            ).where(TicketCategorizationModel.tenant_id == tenant_id)
        )
        row = total_result.one()
        total = row.total or 0
        override_count = row.override_count or 0
        override_rate = override_count / total if total > 0 else 0.0

        # Breakdown by type (category)
        type_result = await self.session.execute(
            select(
                TicketCategorizationModel.category,
                func.count(TicketCategorizationModel.id).label("count"),
                func.coalesce(func.avg(TicketCategorizationModel.confidence), 0.0).label("avg_confidence"),
                func.sum(case((TicketCategorizationModel.overridden == True, 1), else_=0)).label("overrides"),
            )
            .where(TicketCategorizationModel.tenant_id == tenant_id)
            .group_by(TicketCategorizationModel.category)
        )
        by_type = {r.category: {"count": r.count, "avg_confidence": round(float(r.avg_confidence), 4), "overrides": r.overrides} for r in type_result}

        # Breakdown by priority
        priority_result = await self.session.execute(
            select(
                TicketCategorizationModel.priority,
                func.count(TicketCategorizationModel.id).label("count"),
                func.coalesce(func.avg(TicketCategorizationModel.confidence), 0.0).label("avg_confidence"),
                func.sum(case((TicketCategorizationModel.overridden == True, 1), else_=0)).label("overrides"),
            )
            .where(TicketCategorizationModel.tenant_id == tenant_id)
            .group_by(TicketCategorizationModel.priority)
        )
        by_priority = {r.priority: {"count": r.count, "avg_confidence": round(float(r.avg_confidence), 4), "overrides": r.overrides} for r in priority_result}

        return {
            "total_categorized": total,
            "override_count": override_count,
            "override_rate": round(override_rate, 4),
            "average_confidence": round(float(row.avg_confidence), 4),
            "by_type": by_type,
            "by_priority": by_priority,
        }
```

**完成判定**：`ls src/services/ticket_categorization_service.py` → 文件存在 / `ruff check src/services/ticket_categorization_service.py` → 0 errors

### Step 2: 在 `src/api/routers/tickets.py` 追加 metrics 端点

在 `tickets_router` 末尾（SLA 分区之后）新增 `GET /tickets/categorization/metrics` 端点。

操作：
- a) 在 `tickets.py` 顶部 import 中追加 `from services.ticket_categorization_service import TicketCategorizationService`
- b) 在文件末尾（L446 后）插入新 endpoint

```python
@tickets_router.get("/tickets/categorization/metrics")
async def get_categorization_metrics(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Return categorization accuracy metrics for the current tenant.

    Returns: total_categorized, override_count, override_rate (%),
    average_confidence, breakdown by type and by priority.
    """
    svc = TicketCategorizationService(session)
    metrics = await svc.get_metrics(tenant_id=ctx.tenant_id or 0)
    return {"success": True, "data": metrics}
```

**完成判定**：`ruff check src/api/routers/tickets.py` → 0 errors

### Step 3: 创建单元测试 `tests/unit/test_ticket_categorization_metrics.py`

测试 `TicketCategorizationService.get_metrics()` 和 Router `GET /tickets/categorization/metrics` 响应。

测试用例（3 个）：

1. **成功路径**：mock session 返回多行分类记录，验证 `get_metrics` 返回结构正确（含 total, override_rate, by_type, by_priority）
2. **边界：空结果**：total=0 时 `override_rate` 返回 0.0，`by_type` / `by_priority` 返回空 dict
3. **边界：NULL confidence 处理**：当 confidence 全为 NULL 时，`average_confidence` 返回 0.0

```python
import pytest
from unittest.mock import AsyncMock

from services.ticket_categorization_service import TicketCategorizationService


class MockResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class MockScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class TestTicketCategorizationService:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        return TicketCategorizationService(mock_session)

    async def test_get_metrics_returns_structure(self, service, mock_session):
        """Happy path: verify all required keys are present."""
        mock_session.execute = AsyncMock(
            return_value=MockResult(
                type("Row", (), {"total": 100, "avg_confidence": 0.85, "override_count": 12})()
            )
        )
        type_session = AsyncMock()
        type_session.execute = AsyncMock(
            return_value=MockScalarResult([
                type("R", (), {"category": "technical", "count": 60, "avg_confidence": 0.9, "overrides": 5})(),
                type("R", (), {"category": "billing", "count": 40, "avg_confidence": 0.8, "overrides": 7})(),
            ])
        )
        priority_session = AsyncMock()
        priority_session.execute = AsyncMock(
            return_value=MockScalarResult([
                type("R", (), {"priority": "high", "count": 30, "avg_confidence": 0.85, "overrides": 4})(),
            ])
        )
        # swap execute for subsequent calls
        service.session.execute = AsyncMock(side_effect=[
            mock_session.execute(),
            type_session.execute(),
            priority_session.execute(),
        ])

        result = await service.get_metrics(tenant_id=1)
        assert "total_categorized" in result
        assert "override_count" in result
        assert "override_rate" in result
        assert "average_confidence" in result
        assert "by_type" in result
        assert "by_priority" in result

    async def test_get_metrics_empty_result(self, service, mock_session):
        """Boundary: total=0 → override_rate must be 0.0, not division error."""
        mock_session.execute = AsyncMock(
            return_value=MockResult(type("Row", (), {"total": 0, "avg_confidence": None, "override_count": 0})())
        )
        service.session.execute = AsyncMock(return_value=mock_session.execute())
        result = await service.get_metrics(tenant_id=1)
        assert result["override_rate"] == 0.0
        assert result["total_categorized"] == 0

    async def test_get_metrics_null_confidence_defaults_to_zero(self, service, mock_session):
        """Boundary: all NULL confidence → average_confidence returns 0.0."""
        mock_session.execute = AsyncMock(
            return_value=MockResult(type("Row", (), {"total": 5, "avg_confidence": None, "override_count": 0})())
        )
        type_session = AsyncMock()
        type_session.execute = AsyncMock(return_value=MockScalarResult([]))
        priority_session = AsyncMock()
        priority_session.execute = AsyncMock(return_value=MockScalarResult([]))
        service.session.execute = AsyncMock(side_effect=[
            mock_session.execute(),
            type_session.execute(),
            priority_session.execute(),
        ])
        result = await service.get_metrics(tenant_id=1)
        assert result["average_confidence"] == 0.0
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ticket_categorization_metrics.py -v` → ≥ 3 passed

### Step 4: 在 `tests/unit/test_tickets_router.py` 追加 Router 集成测试

在 `test_tickets_router.py` 中新增 `test_get_categorization_metrics` 测试，验证端到端响应结构。

```python
async def test_get_categorization_metrics(client, auth_headers):
    mock_metrics = {
        "total_categorized": 50,
        "override_count": 5,
        "override_rate": 0.1,
        "average_confidence": 0.82,
        "by_type": {"technical": {"count": 30, "avg_confidence": 0.85, "overrides": 3}},
        "by_priority": {"high": {"count": 20, "avg_confidence": 0.8, "overrides": 2}},
    }
    with patch("services.ticket_categorization_service.TicketCategorizationService.get_metrics", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_metrics
        response = client.get("/api/v1/tickets/categorization/metrics", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total_categorized"] == 50
    assert data["data"]["override_rate"] == 0.1
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_tickets_router.py::test_get_categorization_metrics -v` → passed

---

## 6. 验收

- [ ] `ruff check src/services/ticket_categorization_service.py` → 0 errors
- [ ] `ruff check src/api/routers/tickets.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_ticket_categorization_metrics.py -v` → ≥ 3 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_tickets_router.py::test_get_categorization_metrics -v` → passed
- [ ] 端到端：`curl -X GET http://localhost:8000/api/v1/tickets/categorization/metrics -H "Authorization: Bearer ..."` 返回 JSON 含 `success: true` 和所有 metrics 字段

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #605 未完成导致 `TicketCategorizationModel` 不存在，service import 失败 | 中 | 高 | 先完成 #605；本板块依赖 #605 的 ORM 模型，阻塞时暂停 |
| SQL AVG/COUNT 在空结果时返回 None，Python 侧未处理导致 KeyError | 低 | 中 | 用 `func.coalesce(..., 0)` 包裹 AVG；在 service 层对 None 做防御处理 |
| Router 端点路径与现有路径冲突（`/tickets/categorization` 前缀） | 极低 | 中 | 检查 `tickets.py` 中无重复路由注册；`categorization` 为新前缀，无冲突 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/ticket_categorization_service.py src/api/routers/tickets.py tests/unit/test_ticket_categorization_metrics.py tests/unit/test_tickets_router.py
git commit -m "feat(tickets): add GET /tickets/categorization/metrics endpoint"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(tickets): add categorization accuracy metrics endpoint" --body "Closes #606

## Summary
- Add TicketCategorizationService.get_metrics(tenant_id) — aggregates total_categorized, override_count, override_rate, average_confidence, by_type and by_priority
- Expose GET /tickets/categorization/metrics in tickets router
- Unit test metrics response shape (happy path + empty result + null confidence)

## Test plan
- [ ] ruff check src/services/ticket_categorization_service.py → 0 errors
- [ ] ruff check src/api/routers/tickets.py → 0 errors
- [ ] PYTHONPATH=src pytest tests/unit/test_ticket_categorization_metrics.py -v → ≥ 3 passed
- [ ] PYTHONPATH=src pytest tests/unit/test_tickets_router.py::test_get_categorization_metrics -v → passed"
```

---

## 9. 参考

- 同类参考实现：[`src/services/ticket_service.py`](../../src/services/ticket_service.py) — `get_sla_breaches` 统计方法，SQL COUNT/AVG 聚合模式
- 同类参考实现：[`src/api/routers/tickets.py`](../../src/api/routers/tickets.py) — `get_sla_summary` 端点，metrics 聚合返回 SLAStatCard
- 父 issue / 关联：#45
- 依赖 issue / 关联：#605（工单分类数据模型，为本板块提供 `TicketCategorizationModel`）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
