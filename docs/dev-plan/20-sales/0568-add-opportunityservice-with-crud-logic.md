# 20-sales · 实现 OpportunityService CRUD 逻辑

| 元数据 | 值 |
|---|---|
| Issue | #568 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1.5 工作日 |
| 依赖 | [#567](), #552 |
| 启用后赋能 | [Add OpportunityRouter CRUD endpoints](#) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #567 建立了 `Opportunity` ORM model 及相关数据库 schema，而现阶段没有任何 service 层能够对销售机会（Opportunity）执行增删改查操作。没有 service，则 router 无法调用，各 API endpoint 的实现无从谈起，整个20-sales 模块的销售流程自动化将被阻塞。当前状态是"有模型、无逻辑"。

### 1.2 做完后

- **用户视角**：无直接用户可见变化 — 本板块为底层服务层，为后续 API router 提供调用入口。
- **开发者视角**：`OpportunityService` 可在 router 层注入使用，通过 `list`/`create`/`update`/`delete` 四个方法对销售机会进行读写；方法签名遵循 CLAUDE.md §Service Pattern：接收 `tenant_id` 显式鉴权，返回 ORM 对象，由 router负责序列化。

### 1.3 不做什么（剔除）

- [ ] **不实现 OpportunityRouter** — 本板块只做 service 层，router板单独的 issue/board负责。
- [ ] **不实现 stage workflow状态机** —销售阶段的自动流转（Opened→Won/Lost）不在本板块范围，待后续规则引擎时再议。
- [ ] **不实现 Opportunity 与 Customer/Contact 的关联关系验证** — 基础关联字段写入由 schema 层约束，业务规则验证在 router 层或后续 saga 类实现。

### 1.4 关键 KPI

- [ ] `PYTHONPATH=src pytest tests/unit/test_opportunity_service.py -v` →全部 passed（预计 ≥10 个用例，覆盖 list/create/update/delete +异常路径）
- [ ] `ruff check src/services/opportunity_service.py tests/unit/test_opportunity_service.py` → 0 errors
- [ ] `ruff format --check src/services/opportunity_service.py` → exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/opportunity_service.py` 文件尚不存在，本板块为新建模块。同类参考实现（已在仓库中验证的 service模式）：

TBD - 待验证：`src/services/customer_service.py` L1-L30（参照 service constructor 签名 + 方法结构）

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/opportunity.py` —参照已有的 Opportunity ORM model字段定义，提取 stage枚举值供 filter 使用 - `tests/unit/conftest.py` — 若 `opportunity_service` 需要 mock handler，需确认/新增 `make_opportunity_handler`
- 要建：
  - `src/services/opportunity_service.py` —核心新文件 - `tests/unit/test_opportunity_service.py` — 单元测试

### 2.3 缺什么

- [ ] `OpportunityService` class：尚无任何 CRUD 操作- [ ] `list` 方法：支持分页（page/page_size）并按 stage 过滤，SQL 必须含 `WHERE tenant_id = :tenant_id`
- [ ] `create` 方法：写入 name/stage/value/close_date/customer_id，返回 ORM 对象
- [ ] `update` 方法：支持更新 stage/value/close_date，缺失时抛 `NotFoundException`；无效输入抛 `ValidationException`
- [ ] `delete` 方法：软删或硬删，缺失时抛 `NotFoundException`
- [ ] 单元测试覆盖：正常路径 +异常路径（NotFound/Validation）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/opportunity_service.py` | 销售机会 CRUD service，遵循 AsyncSession-injected模式 |
| `tests/unit/test_opportunity_service.py` | 单元测试，覆盖 list/create/update/delete 及异常路径 |

### 3.2 修改文件

|路径 | 改动要点 |
|------|---------|
| `tests/unit/conftest.py` | 如需要，新增 `make_opportunity_handler(state)` 工厂函数供测试复用 |

### 3.3 新增能力

- **Service class**：`OpportunityService`
  - `list(self, tenant_id: int, page: int = 1, page_size: int = 20, stage: str | None = None) -> tuple[list[Opportunity], int]`
  - `create(self, tenant_id: int, name: str, stage: str, customer_id: int, value: float, close_date: date, **kwargs) -> Opportunity`
  - `update(self, opportunity_id: int, tenant_id: int, **fields) -> Opportunity`
  - `delete(self, opportunity_id: int, tenant_id: int) -> None`
- **ORM model**：`Opportunity`（已在 #567 创建）
- **异常**：`NotFoundException`（实体不存在）、`ValidationException`（无效输入）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Service 不返回 dict / 不调用 `.to_dict()`**：遵循 CLAUDE.md §Service Pattern，OpportunityService 直接返回 `Opportunity` ORM 对象，由调用方（router）负责序列化。这样 service 可被 batch 服务或脚本直接复用，不需跨越 HTTP envelope。
- **使用 `alembic autogenerate` 生成 migration**：schema已在 #567 确定，新增 service 层不涉及 schema变更，暂无 migration；但若 schema 有 drift，需用 alembic autogenerate。

### 4.2 版本约束

本板块无新增外部依赖，沿用 `pyproject.toml` 中的已有版本约束。

### 4.3 兼容性约束

- 多租户：所有 SQL 查询必须含 `WHERE tenant_id = :tenant_id`，禁止跨租户查询
- Session注入：构造函数 `def __init__(self, session: AsyncSession)` — **无默认值**，禁止传 `None`
- 错误处理：仅抛出 `NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`，**禁止**返回 `ApiResponse.error()`
- 返回值：返回 ORM 对象，**禁止**在 service 内部调用 `to_dict()`

### 4.4 已知坑

1. **SQLAlchemy 列名不能为 `metadata`** → 见 CLAUDE.md §Gotchas & Tips：`Opportunity` model 中的 JSON 列若命名为 `metadata` 会与 `Base.metadata` 冲突，须用 `event_metadata` / `payload` 等替代名。本板块依赖 #567 已正确命名，如有 drift 在 Review 时指出。
2. **SQLAlchemy async session 不要用 `async with get_db()`** → router 中通过 `Depends(get_db)` 注入。本板块 service 层只接收已注入的 session，不需要处理 session生命周期。
3. **Opportunity stage 值须为已定义的枚举字符串** → `create`/`update` 方法需在 #567 定义的 `Stage`枚举范围内校验，不在枚举内的值抛 `ValidationException`

---

## 5. 实现步骤（按顺序）

### Step 1: 确定 Opportunity ORM model 字段结构

[确认 #567 创建的 Opportunity model字段名、stage枚举定义、涉及的 relationship，为后续 SQL 查询打基础]

操作：
- a) 读取 `src/db/models/opportunity.py`，记录字段名（name, stage, value, close_date, customer_id 等）
- b) 确认 stage 是否为 `Enum` 类型，若是则提取枚举成员列表供 Validation 使用
- c)确认 `tenant_id`字段类型及索引情况

**完成判定**：文件 `src/db/models/opportunity.py` 存在且可正常 import，`Stage` 枚举成员可枚举---

### Step 2: 创建 `src/services/opportunity_service.py`

[定义 OpportunityService 类，实现四个公开方法及辅助 Private 方法，遵循 CLAUDE.md §Service Pattern：AsyncSession 无默认值、tenant_id 显式传入、返回 ORM 对象]

操作：
- a) 创建文件，写入 import：SQLAlchemy async 相关 + AppException 类 + Opportunity model + text()（如需 raw SQL）
- b) 定义 class `OpportunityService`
- c) 实现 `list`：含 `WHERE tenant_id = :tenant_id`、分页 OFFSET/LIMIT、按 stage 过滤（可选），返回 `tuple[list[Opportunity], int]`
- d) 实现 `create`：INSERT，字段校验（stage 枚举、value ≥ 0、close_date 非空），返回 `Opportunity`
- e) 实现 `update`：根据 ID + tenant_id 查询，缺失抛 `NotFoundException`，字段校验后 UPDATE，返回 `Opportunity`
- f) 实现 `delete`：根据 ID + tenant_id 查询，缺失抛 `NotFoundException`，执行 DELETE
- g) 所有 SQL 使用 `text()` 或 `select(Opportunity).where(...)` 风格均可，统一格式示例代码：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sql_delete, update as sql_update

from db.models.opportunity import Opportunity
from pkg.errors.app_exceptions import NotFoundException, ValidationException


class OpportunityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        tenant_id: int,
        page: int = 1,
        page_size: int = 20,
        stage: str | None = None,
    ) -> tuple[list[Opportunity], int]:
        base_filters = [Opportunity.tenant_id == tenant_id]
        if stage is not None:
            base_filters.append(Opportunity.stage == stage)

        count_q = select(func.count()).select_from(Opportunity).where(*base_filters)
        count_result = await self.session.execute(count_q)
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        list_q = (
            select(Opportunity)
            .where(*base_filters)
            .order_by(Opportunity.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(list_q)
        rows = result.scalars().all()
        return list(rows), total

    async def create(
        self,
        tenant_id: int,
        name: str,
        stage: str,
        customer_id: int,
        value: float,
        close_date,
        **kwargs,
    ) -> Opportunity:
        if not name or not name.strip():
            raise ValidationException("Opportunity name is required")
        if value< 0:
            raise ValidationException("Opportunity value must be non-negative")

        obj = Opportunity(
            tenant_id=tenant_id,
            name=name,
            stage=stage,
            customer_id=customer_id,
            value=value,
            close_date=close_date,
            **kwargs,
        )
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(
        self,
        opportunity_id: int,
        tenant_id: int,
        **fields,
    ) -> Opportunity:
        q = select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.tenant_id == tenant_id,
        )
        result = await self.session.execute(q)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise NotFoundException("Opportunity")

        for key, val in fields.items():
            if val is not None and hasattr(obj, key):
                setattr(obj, key, val)

        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, opportunity_id: int, tenant_id: int) -> None:
        q = select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.tenant_id == tenant_id,
        )
        result = await self.session.execute(q)
        obj = result.scalar_one_or_none()
        if obj is None:
            raise NotFoundException("Opportunity")
        await self.session.delete(obj)
        await self.session.commit()
```

**完成判定**：`ruff check src/services/opportunity_service.py` →0 errors

---

### Step 3: 确认/创建 `make_opportunity_handler` in `tests/unit/conftest.py`

[OpportunityService 需要 stateful mocks 以支持单元测试。参照 `make_customer_handler` 模式创建 handler工厂]

操作：
- a)读取 `tests/unit/conftest.py`，查找 `make_customer_handler` 实现格式
- b) 如不存在，则新增 `make_opportunity_handler(state)` 函数
- c) 处理：INSERT + auto ID递增、UPDATE、DELETE、SELECT（list + get）、COUNT**完成判定**：`ruff check tests/unit/conftest.py` → 0 errors（如有修改）

---

### Step 4: 创建单元测试 `tests/unit/test_opportunity_service.py`

[覆盖 list/create/update/delete 的正常路径，以及 NotFound/Validation 异常路径]

操作：
- a) 在 `tests/unit/test_opportunity_service.py` 创建文件
- b) 定义 `mock_db_session` fixture（使用 `make_mock_session([make_opportunity_handler(state), make_count_handler(state)])`）
- c) 定义 `opportunity_service` fixture（`OpportunityService(mock_db_session)`）
- d) 编写测试用例：
  - `test_list_returns_opportunities_paginated`
  - `test_list_filters_by_stage`
  - `test_create_returns_opportunity`
  - `test_create_invalid_value_raises_validation`
  - `test_update_returns_updated_opportunity`
  - `test_update_unknown_id_raises_not_found`
  - `test_delete_success`
  - `test_delete_unknown_id_raises_not_found`

示例代码框架：

```python
import pytest
from tests.unit.conftest import (
    make_mock_session,
    make_opportunity_handler,
    make_count_handler,
    MockState,
)
from services.opportunity_service import OpportunityService


@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([
        make_opportunity_handler(state),
        make_count_handler(state),
    ])


@pytest.fixture
def svc(mock_db_session):
    return OpportunityService(mock_db_session)


class TestOpportunityServiceList:
    async def test_list_returns_opportunities(self, svc, mock_db_session):
        state = mock_db_session._state
        state.opportunities.extend([...])
        items, total = await svc.list(tenant_id=1, page=1, page_size=20)
        assert total == 2
        assert len(items) == 2

    async def test_list_empty_for_unknown_tenant(self, svc):
        items, total = await svc.list(tenant_id=9999)
        assert total == 0
        assert items == []
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity_service.py -v` → 全部 passed

---

## 6. 验收

- [ ] `ruff check src/services/opportunity_service.py tests/unit/test_opportunity_service.py` → 0 errors
- [ ] `ruff format --check src/services/opportunity_service.py` → exit 0
- [ ] `PYTHONPATH=src pytest tests/unit/test_opportunity_service.py -v` →全部 passed（或显示预期用例数，如 `12 passed`）
- [ ] `PYTHONPATH=src python -c "from services.opportunity_service import OpportunityService; print('import ok')"` → `import ok`
- [ ] `PYTHONPATH=src python -c "from db.models.opportunity import Opportunity, Stage; print('model ok')"` → `model ok`（验证 ORM model依赖可用）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #567 Opportunity model字段与预期不符，导致 service 字段映射错误 | 低 | 高 | service 层独立于 model变更，只影响相应字段名/类型；通过 §6 的 import check 可较早发现问题，修正 field mapping即可 |
| `make_opportunity_handler` 实现复杂度超出预期（Opportunity 有关联 relationship） | 中 | 中 | 若 mock handler 无法覆盖 relationship，临时降级：改用 `tests/unit/conftest.py` 的通用 SQL mock 框架，或在 integration test 层补充覆盖，单元测试标记 `pytest.skip` 并注明原因 |
| Alembic migration drift（#567 遗留 schema 问题） | 低 | 中 | 在 §5 Step 1 中增加 schema 检查；如需 migration修正，由 #567 board 补发迁移文件后再合入 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/opportunity_service.py tests/unit/test_opportunity_service.py
git commit -m "feat(20-sales): add OpportunityService with list/create/update/delete"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#568): add OpportunityService CRUD logic" --body "Closes #568"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：CLAUDE.md §Service Pattern（项目内置约定）
- 父 issue /关联：#552（父 Epic），#567（Opportunity model schema 依赖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
