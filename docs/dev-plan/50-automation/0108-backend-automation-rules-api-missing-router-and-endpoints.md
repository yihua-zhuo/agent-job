# 50-自动化 · Automation Rules API 缺失路由与端点

| 元数据 | 值 |
|---|---|
| Issue | #108 |
| 分类 | [20-platform](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [前端 Automation 页面](../40-campaigns/0065-automation-feature-plan.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

前端已完成 Automation 页面（`frontend/src/app/(app)/automation/page.tsx`），但后端缺少对应的 `/automation/rules` 端点，导致前端请求无法到达后端，阻塞关联 issue #65 的端到端联调。当前系统中没有任何 `AutomationService` 或 `AutomationRouter`，属于纯新建模块。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层后端 API。管理员在 Automation 页面进行 CRUD 操作时，后端可正常响应。
- **开发者视角**：获得完整的 `AutomationService`（含 list / create / get / update / delete / toggle 六个方法）和 `AutomationRouter`（含六个 API endpoint），所有响应均以 `ApiResponse[T]` 封装，支持多租户隔离。

### 1.3 不做什么（剔除）

- [ ] 前端 UI 修改（前端已完，参考 issue 中已有路径）
- [ ] 自动化规则触发逻辑（仅实现 CRUD 存储/查询，不含规则引擎执行）
- [ ] 规则执行日志表（作为独立 issue 处理）
- [ ] 第三方工作流集成（IFTTT/Zapier 等）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_automation_service.py -v` → ≥ 6 passed（每个 service 方法对应至少 1 个测试用例）
- `PYTHONPATH=src pytest tests/integration/test_automation_integration.py -v` → ≥ 5 passed（CRUD + toggle 场景）
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `ruff check src/services/automation_service.py src/api/routers/automation_router.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。当前代码库中不存在 `AutomationService`、`AutomationRouter`、`automation_rules` 表或任何相关模型。需从零搭建。

涉及文件清单（§2.2）中列出的「要改」文件目前均为空桩或尚未引用，本板块需要新建它们。

### 2.2 涉及文件清单

- 要改：
  - `src/api/routers/__init__.py` — 注册 `AutomationRouter` 到 app（若当前为空需补充 import）
  - `src/main.py` — 将 router 挂载到 FastAPI app（若当前无自动化相关挂载）
- 要建：
  - `src/db/models/automation_rule.py` — ORM model，`AutomationRule` 表结构
  - `src/services/automation_service.py` — `AutomationService` 类，六个业务方法
  - `src/api/routers/automation_router.py` — `AutomationRouter`，六个 endpoint
  - `alembic/versions/<id>_create_automation_rule_table.py` — 建表 migration（含 `tenant_id` 索引）
  - `tests/unit/test_automation_service.py` — 6 个 service 方法的 mock 测试
  - `tests/integration/test_automation_integration.py` — 5 个端到端测试

### 2.3 缺什么

- [ ] `AutomationRule` ORM model（无现有模型对应）
- [ ] `AutomationService` 类及其 6 个方法（list / create / get / update / delete / toggle）
- [ ] `AutomationRouter` 及 6 个 FastAPI endpoint（`GET/POST /automation/rules`、`GET/PUT/PATCH/DELETE /automation/rules/{id}`、`POST /automation/rules/{id}/toggle`）
- [ ] Alembic migration 创建 `automation_rules` 表（含 tenant_id 索引）
- [ ] 单元测试覆盖全部 6 个 service 方法
- [ ] 集成测试覆盖 CRUD + toggle 场景

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/automation_rule.py` | `AutomationRule` ORM model（tenant_id、name、rule_type、status、conditions、actions 等列） |
| `src/services/automation_service.py` | `AutomationService` 含 list/create/get/update/delete/toggle 六个 async 方法 |
| `src/api/routers/automation_router.py` | `AutomationRouter` 含六个 `/api/v1/automation/rules` endpoint |
| `alembic/versions/<id>_create_automation_rules_table.py` | 建表 migration（列：id、tenant_id、name、rule_type、status、conditions、actions、created_at、updated_at；含 tenant_id 索引） |
| `tests/unit/test_automation_service.py` | 6 个 service 方法的 mock 测试 |
| `tests/integration/test_automation_integration.py` | 5 个端到端集成测试（CRUD + toggle） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/api/routers/__init__.py` | 导入并注册 `AutomationRouter` |
| `src/main.py` | `app.include_router(automation_router.router, prefix="/api/v1")` |

### 3.3 新增能力

- **ORM model**：`AutomationRule` in `src/db/models/automation_rule.py`
- **Service method**：`AutomationService.list_rules(self, tenant_id: int, page: int, page_size: int, rule_type: str, status: str) -> tuple[list[AutomationRule], int]`
- **Service method**：`AutomationService.create_rule(self, tenant_id: int, data: CreateAutomationRule) -> AutomationRule`
- **Service method**：`AutomationService.get_rule(self, rule_id: int, tenant_id: int) -> AutomationRule`
- **Service method**：`AutomationService.update_rule(self, rule_id: int, tenant_id: int, data: UpdateAutomationRule) -> AutomationRule`
- **Service method**：`AutomationService.delete_rule(self, rule_id: int, tenant_id: int) -> None`
- **Service method**：`AutomationService.toggle_rule(self, rule_id: int, tenant_id: int) -> AutomationRule`
- **API endpoint**：`GET /api/v1/automation/rules` → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`POST /api/v1/automation/rules` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /api/v1/automation/rules/{id}` → `{"success": true, "data": {...}}`
- **API endpoint**：`PUT/PATCH /api/v1/automation/rules/{id}` → `{"success": true, "data": {...}}`
- **API endpoint**：`DELETE /api/v1/automation/rules/{id}` → `{"success": true, "data": null}`
- **API endpoint**：`POST /api/v1/automation/rules/{id}/toggle` → `{"success": true, "data": {...}}`
- **Migration**：`alembic upgrade head` 创建 `automation_rules` 表（含 `tenant_id` 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 JSONB 存储 conditions / actions 而非拆分子表**：自动化规则的条件和动作结构灵活（可能嵌套、多层），JSONB 可在无需固定 schema 的前提下支持阿json 过滤（GIN 索引）。不选拆分子表方案，因规则类型尚未收敛，schema 变化会导致频繁 migration。
- **PUT vs PATCH 均指向同一 update_rule 方法**：FastAPI 中 PUT 做完整替换，PATCH 做部分更新。两者均可通过同一个 service 方法处理，router 层根据 request body 是否含某字段判断是否覆盖，简化 service 实现。

### 4.2 版本约束

无新依赖引入。本板块使用的所有包均为已有依赖（FastAPI、SQLAlchemy 2.x、asyncpg）。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`
- `AutomationRule` model 的列名使用 `event_metadata` / `payload` 等，不得使用 `metadata`（与 `Base.metadata` 冲突）
- Router 注入 session：`session: AsyncSession = Depends(get_db)`，**禁止** `async with get_db() as session:`
- 响应统一使用 `ApiResponse[T]` 封装：`{"success": true, "data": ..., "message": ...}`

### 4.4 已知坑

1. **Alembic autogen 会将 JSONB 列写成 JSON** → 规避：migration 生成后手动将 `sa.JSON()` 改为 `sa.JSONB()`
2. **Alembic autogen 会将 `TIMESTAMP WITH TIME ZONE` 写成无时区的 `DateTime`** → 规避：migration 中手动添加 `timezone=True` 到 `DateTime(timezone=True)`
3. **列名 `metadata` 与 SQLAlchemy Base.metadata 冲突** → 规避：字段命名用 `rule_metadata` / `payload` / `attrs`，避免使用 `metadata`
4. **PYTHONPATH=src，import 必须写 `from db.models...`、`from services...`，禁止 `from src.db.models...`** → 规避：所有新建文件的 import 遵循此约定

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 AutomationRule ORM model

定义 `AutomationRule` 表结构。列包括：id（自增主键）、tenant_id（索引）、name、rule_type（枚举字符串）、status（active/inactive）、conditions（JSONB）、actions（JSONB）、created_at、updated_at。列名不使用 `metadata`。

```python
# src/db/models/automation_rule.py
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AutomationRule(Base):
    __tablename__ = "automation_rules"
    __table_args__ = (
        index("ix_automation_rules_tenant_id", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=True)
    actions: Mapped[dict] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "rule_type": self.rule_type,
            "status": self.status,
            "conditions": self.conditions,
            "actions": self.actions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
```

在 `src/db/models/__init__.py` 中添加 `from db.models.automation_rule import AutomationRule` 并在 `alembic/env.py` 中添加对应 import 以便 autogenerate 识别。

**完成判定**：`ruff check src/db/models/automation_rule.py` → 0 errors

---

### Step 2: 生成 Alembic migration 建表

按照 CLAUDE.md 的 one-time setup 启动 clean 数据库，执行 `alembic revision --autogenerate -m "create automation_rules table"`。生成后手动修正：

- `sa.JSON()` → `sa.JSONB()`（conditions、actions 列）
- DateTime 列加 `timezone=True`

```python
# alembic/versions/<id>_create_automation_rules_table.py
def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rule_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("conditions", sa.JSON(as_text_type=sa.Text())..., nullable=True),  # → sa.JSONB()
        sa.Column("actions", sa.JSON(as_text_type=sa.Text())..., nullable=True),  # → sa.JSONB()
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_rules_tenant_id", "automation_rules", ["tenant_id"])
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 3: 创建 Pydantic schema（Request / Response models）

在 `src/models/` 下创建或补充 `automation_rule.py`，定义：

```python
# src/models/automation_rule.py（schema 部分）
from pydantic import BaseModel, Field
from typing import Optional


class AutomationRuleBase(BaseModel):
    name: str = Field(..., max_length=255)
    rule_type: str = Field(..., max_length=100)
    conditions: Optional[dict] = None
    actions: Optional[dict] = None


class AutomationRuleCreate(AutomationRuleBase):
    pass


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    rule_type: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = None
    conditions: Optional[dict] = None
    actions: Optional[dict] = None


class AutomationRuleResponse(AutomationRuleBase):
    id: int
    tenant_id: int
    status: str
    created_at: Optional[str]
    updated_at: Optional[str]

    model_config = {"from_attributes": True}
```

**完成判定**：`ruff check src/models/automation_rule.py` → 0 errors

---

### Step 4: 创建 AutomationService

在 `src/services/automation_service.py` 中实现 `AutomationService` 类，构造函数接受 `session: AsyncSession`（无默认值）。

```python
# src/services/automation_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from pkg.errors.app_exceptions import NotFoundException, ValidationException

from db.models.automation_rule import AutomationRule
from src.models.automation_rule import (
    AutomationRuleCreate,
    AutomationRuleUpdate,
)


class AutomationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_rules(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        rule_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[AutomationRule], int]:
        # WHERE tenant_id = :tenant_id
        # 可选 WHERE rule_type = :rule_type AND status = :status
        # COUNT 查询 + 分页 OFFSET/LIMIT
        ...

    async def create_rule(self, tenant_id: int, data: AutomationRuleCreate) -> AutomationRule:
        rule = AutomationRule(tenant_id=tenant_id, **data.model_dump())
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_rule(self, rule_id: int, tenant_id: int) -> AutomationRule:
        result = await self.session.execute(
            select(AutomationRule).where(
                AutomationRule.id == rule_id,
                AutomationRule.tenant_id == tenant_id
            )
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            raise NotFoundException("AutomationRule")
        return rule

    async def update_rule(self, rule_id: int, tenant_id: int, data: AutomationRuleUpdate) -> AutomationRule:
        rule = await self.get_rule(rule_id, tenant_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)
        await self.session.flush()
        return rule

    async def delete_rule(self, rule_id: int, tenant_id: int) -> None:
        rule = await self.get_rule(rule_id, tenant_id)
        await self.session.delete(rule)
        await self.session.flush()

    async def toggle_rule(self, rule_id: int, tenant_id: int) -> AutomationRule:
        rule = await self.get_rule(rule_id, tenant_id)
        rule.status = "inactive" if rule.status == "active" else "active"
        await self.session.flush()
        return rule
```

import 路径：`from db.models.automation_rule import AutomationRule`（使用 PYTHONPATH=src 风格）。

**完成判定**：`ruff check src/services/automation_service.py` → 0 errors；`PYTHONPATH=src pytest tests/unit/test_automation_service.py -v` → ≥ 6 passed

---

### Step 5: 创建 AutomationRouter

在 `src/api/routers/automation_router.py` 中实现 router：

```python
# src/api/routers/automation_router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from dependencies.auth import AuthContext, require_auth

from src.services.automation_service import AutomationService
from src.models.automation_rule import (
    AutomationRuleCreate,
    AutomationRuleUpdate,
    AutomationRuleResponse,
)

router = APIRouter(prefix="/automation/rules", tags=["Automation"])

def _svc(session: AsyncSession) -> AutomationService:
    return AutomationService(session)

@router.get("/")
async def list_rules(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rule_type: str | None = Query(None),
    status: str | None = Query(None),
):
    svc = _svc(session)
    items, total = await svc.list_rules(
        tenant_id=ctx.tenant_id,
        page=page,
        page_size=page_size,
        rule_type=rule_type,
        status=status,
    )
    return {
        "success": True,
        "data": {"items": [r.to_dict() for r in items], "total": total, "page": page, "page_size": page_size},
    }

@router.post("/")
async def create_rule(
    data: AutomationRuleCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = _svc(session)
    rule = await svc.create_rule(tenant_id=ctx.tenant_id, data=data)
    return {"success": True, "data": rule.to_dict()}

@router.get("/{rule_id}")
async def get_rule(
    rule_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = _svc(session)
    rule = await svc.get_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": rule.to_dict()}

@router.put("/{rule_id}")
@router.patch("/{rule_id}")
async def update_rule(
    rule_id: int,
    data: AutomationRuleUpdate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = _svc(session)
    rule = await svc.update_rule(rule_id=rule_id, tenant_id=ctx.tenant_id, data=data)
    return {"success": True, "data": rule.to_dict()}

@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = _svc(session)
    await svc.delete_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": None}

@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = _svc(session)
    rule = await svc.toggle_rule(rule_id=rule_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": rule.to_dict()}
```

将 router 注册到 `src/main.py`（`app.include_router(automation_router.router, prefix="/api/v1")`）并更新 `src/api/routers/__init__.py` 的导出。

**完成判定**：`ruff check src/api/routers/automation_router.py src/main.py` → 0 errors

---

### Step 6: 编写单元测试

在 `tests/unit/test_automation_service.py` 中为每个 service 方法编写测试。每个测试使用 `MockState` + `make_mock_session`（参考 `tests/unit/conftest.py` 的现有 handler 模式）。若 `automation_rule` 暂无专用 handler，需在 `conftest.py` 中新增 `make_automation_rule_handler(state)`，参考现有 `make_customer_handler` 的工厂模式。

测试用例：
- `test_list_rules_returns_paginated_results`
- `test_list_rules_filters_by_tenant_id`
- `test_create_rule_returns_orm_object`
- `test_get_rule_raises_not_found`
- `test_update_rule_partial_update`
- `test_delete_rule_removes_record`
- `test_toggle_rule_switches_status`

```python
# tests/unit/test_automation_service.py（片段）
import pytest
from tests.unit.conftest import MockState, make_mock_session

@pytest.fixture
def mock_db_session():
    state = MockState()
    # 如需新 handler，在 conftest.py 添加 make_automation_rule_handler
    return make_mock_session([make_automation_rule_handler(state)])

@pytest.fixture
def svc(mock_db_session):
    from src.services.automation_service import AutomationService
    return AutomationService(mock_db_session)

@pytest.mark.asyncio
async def test_create_rule_returns_orm_object(svc):
    from src.models.automation_rule import AutomationRuleCreate
    data = AutomationRuleCreate(name="Test Rule", rule_type="email")
    result = await svc.create_rule(tenant_id=1, data=data)
    assert result.id == 1
    assert result.name == "Test Rule"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_automation_service.py -v` → ≥ 6 passed

---

### Step 7: 编写集成测试

在 `tests/integration/test_automation_integration.py` 中使用 `db_schema` + `tenant_id` + `async_session` fixtures，测试真实数据库的 CRUD + toggle 场景。需 seed 跨服务依赖（如有）。

测试用例：
- `test_create_and_get_rule`
- `test_list_rules_with_pagination`
- `test_update_rule`
- `test_delete_rule`
- `test_toggle_rule`

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_automation_integration.py -v` → ≥ 5 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/automation_rule.py src/services/automation_service.py src/api/routers/automation_router.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_automation_service.py -v` → ≥ 6 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_automation_integration.py -v` → ≥ 5 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] 端到端：`curl -X GET http://localhost:8000/api/v1/automation/rules -H "Authorization: Bearer <token>"` 返回 `{"success": true, "data": {"items": [], "total": 0}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Alembic migration 在生产 DB 因列名冲突或其他约束报错 | 中 | 高 | revert migration：运行 `alembic downgrade -1`，本板块代码保留在下个 PR 中修复后重新 migration |
| 前端请求体结构与后端 Pydantic schema 不一致导致 422 | 中 | 中 | 本板块 schema 字段与前端 UI 中的 `page.tsx` 表单字段对齐；如遇 422，在 router 层加 debug log 并通知前端协作者 |
| 新 JSONB 列导致生产 DB 写入慢（GIN 索引未建） | 低 | 中 | 立即在目标 DB 执行 `CREATE INDEX CONCURRENTLY ix_automation_rules_tenant_id ON automation_rules(tenant_id)`（已在 migration 中声明，无回退风险） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/automation_rule.py src/services/automation_service.py \
       src/api/routers/automation_router.py src/models/automation_rule.py \
       alembic/versions/<id>_create_automation_rules_table.py \
       tests/unit/test_automation_service.py tests/integration/test_automation_integration.py
git commit -m "feat(automation): add AutomationRules API router and service"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): add AutomationRules API router and service" --body "Closes #108

## Summary
- Add AutomationRule ORM model with tenant_id isolation
- Add AutomationService (list/create/get/update/delete/toggle)
- Add AutomationRouter with 6 endpoints under /api/v1/automation/rules
- Add Alembic migration for automation_rules table
- Add unit tests (6 passed) and integration tests (5 passed)

## Test plan
- [ ] ruff check src/ → 0 errors
- [ ] pytest tests/unit/test_automation_service.py → ≥6 passed
- [ ] pytest tests/integration/test_automation_integration.py → ≥5 passed
- [ ] alembic upgrade head && alembic downgrade -1 && alembic upgrade head → exit 0

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — service 模式参考（constructor + raise 风格）
- 同类参考实现：[`src/api/routers/customer_router.py`](../../src/api/routers/customer_router.py) — router 模式参考（router 注册 + 响应封装）
- 父 issue / 关联：#65（前端 Automation 页面依赖本后端 API）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
