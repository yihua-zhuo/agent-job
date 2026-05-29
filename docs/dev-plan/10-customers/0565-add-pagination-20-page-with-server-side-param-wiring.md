# 客户列表分页（20/页）+ 服务端参数接入| 元数据 | 值 |
|---|---|
| Issue | #565 |
| 分类 | [10-customers](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1.5 工作日 |
| 依赖 | [556-数据模型-新增字段-客户分级标签](../10-customers/0556-add-customer-tier-field.md)（#557 子任务，本身为 #557 子任务；依赖 #564 后端分页基础能力） |
| 启用后赋能 | [566-前端子模块-分页控件渲染](../90-frontend/0566-frontend-pagination-widget.md)（前端控件接入方） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 GET /customers 接口不具备服务端分页能力，返回全量客户列表。对大租户而言数据量可达数万行，既浪费带宽又拖慢响应。前端已具备翻页 UI，需在后端接入 page / page_size 参数，将分页计算下沉至数据库层（SQL OFFSET/LIMIT）。这是 #557 客户模块的核心交互改进，本身为 #557 的子任务，依赖上游 #564 打通分页基础能力。

### 1.2 做完后

- **用户视角**：客户列表默认每次加载 20 条记录，翻页后立即展示对应页数据，底栏显示"第 N 页 / 共 M 页"及上一页/下一页操作。
- **开发者视角**：CustomerService 提供标准化分页方法 `list_customers(tenant_id, page, page_size)`，router接收 page/page_size 查询参数并透传，ORM 层通过 SQL OFFSET/LIMIT 在数据库内完成切片。

### 1.3 不做什么（剔除）

- [ ] 不实现前端分页 UI控件本身（交由 #566 负责）
- [ ] 不实现排序字段、升降序参数（保持在单页内默认排序规则）
- [ ] 不实现导出/批量操作相关的跨页行为### 1.4 关键 KPI

- [指标1：`PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 所有测试 passed]
- [指标 2：`PYTHONPATH=src pytest tests/integration/test_customer_pagination_integration.py -v` → 所有测试 passed]
- [指标 3：`ruff check src/services/customer_service.py src/api/routers/customers.py` →0 errors]
- [指标 4：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如需 migration）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/customers.py` L? —现有 GET /customers 接口签名及返回结构TBD - 待验证：`src/services/customer_service.py` L? — 现有 list 方法签名（是否支持 page/page_size 参数）

```{x}:{y}:TBD
# 占位；由 orchestrator 在生成前填入实际代码片段
```

<!-- 新建模块时，§2.1 直接写：N/A — 新建模块 -->

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/services/customer_service.py` — list 方法接入 page/page_size 逻辑
  - TBD - 待验证：`src/api/routers/customers.py` — 路由增加 page/page_size 查询参数
  - TBD - 待验证：`tests/unit/test_customer_service.py` — 补充分页参数测试 case
- 要建：
  - `tests/integration/test_customer_pagination_integration.py` —端到端分页集成测试### 2.3 缺什么

- [ ] 分页参数接收：router 层 path/ query 参数定义，验证 page >= 1、page_size 上限- [ ] 服务层分页逻辑：SQLAlchemy 查询增加 OFFSET / LIMIT / COUNT(total)
- [ ] 分页响应包装：返回 items + total + page + page_size + total_pages
- [ ] 前端参数透传：paginated fetch携带 page/page_size 到 API 调用
- [ ]集成测试：with real DB 验证分页切片正确性（page 2 不含 page 1 数据等）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/integration/test_customer_pagination_integration.py` | 端到端分页集成测试（real Postgres） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/services/customer_service.py` | list_customers 方法新增 page/page_size 参数，返回 (items, total) |
| TBD - 待验证：`src/api/routers/customers.py` | GET /customers 增加 page=1&page_size=20 查询参数，返回分页元数据 |
| TBD - 待验证：`tests/unit/test_customer_service.py` | 补充分页参数化测试 fixture |

### 3.3 新增能力

- **Service method**：`CustomerService.list_customers(self, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[CustomerModel], int]`
- **API endpoint**：`GET /customers?page=1&page_size=20` → `{"success": true, "data": {"items": [...], "total": N, "page": 1, "page_size": 20, "total_pages": M}}`
- **ORM 修改**：TBD - 待验证：是否需为 customers 表 tenant_id 以外的索引（如 id复合索引）以支撑 OFFSET性能

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **服务端分页不选客户端分页**：大租户数据量大，客户端分页需一次性拉取全部数据，带宽和内存开销不划算；服务端分页由 SQL LIMIT/OFFSET 在数据库层完成，仅返回当页数据。
- **page/page_size 参数不选 cursor方式**：CRM 列表以"页"为单位符合用户心智，无需复杂游标管理；page 为整数自然映射前端翻页控件。
- **COUNT(total) 单独查询不选 window functions**：SQLAlchemy 2.x async 下窗口函数语法较繁琐，拆为 LIMIT+OFFSET 主查询和 `SELECT COUNT(*)` 子查询实现更直接。

### 4.2 版本约束

<!-- 无新增外部依赖，整段删掉 -->

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- 新增 page/page_size 参数需兼容旧调用方（默认值1 和 20 保证向后兼容）
- router 层 session注入必须用 `session: AsyncSession = Depends(get_db)`，禁止 `async with get_db()`

### 4.4 已知坑

1. **Alembic autogenerate 将 JSONB 列生成为 JSON** →规避：migration 文件中手动将 `sa.JSON()` 改回 `sa.JSONB()`，并在 down_revision注明
2. **OFFSET 数值大时查询性能差（MySQL/Postgres 均如此）** → 规避：数据库层确保 tenant_id 上有索引，OFFSET 在 1000 以内性能可接受；如未来需深度分页可考虑 keyset pagination，但当前 scope 不含此优化
3. **page_size 未设上限可能被滥用** → 规避：router 层 validation 使 page_size 上限为 100，超出抛 ValidationException

---

## 5. 实现步骤（按顺序）

### Step 1: 修改 CustomerService.list_customers 接入分页参数

在 CustomerService 中将现有 list_customers 方法改造为支持 page/page_size，新增 total 返回值，SQLAlchemy 查询增加 LIMIT 和 OFFSET（SQLAlchemy 2.x async）。

操作：
- a)确认 TBD - 待验证：`src/services/customer_service.py` 中 list_customers 方法签名
- b) 修改方法签名：`async def list_customers(self, tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[CustomerModel], int]`
- c) 在查询末加入 `.limit(page_size).offset((page - 1) * page_size)`
- d) 新增一条 `SELECT COUNT(*) FROM customers WHERE tenant_id = :tenant_id` 查询，`result.scalar_one()` 获取 total

示例代码（≤15 行）：

```python
async def list_customers(
    self,
    tenant_id: int,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[CustomerModel], int]:
    offset = (page - 1) * page_size
    count_result = await self.session.execute(
        select(func.count()).select_from(CustomerModel).where(
            CustomerModel.tenant_id == tenant_id
        )
    )
    total: int = count_result.scalar_one()
    result = await self.session.execute(
        select(CustomerModel)
        .where(CustomerModel.tenant_id == tenant_id)
        .limit(page_size)
        .offset(offset)
        .order_by(CustomerModel.id)
    )
    customers = list(result.scalars().all())
    return customers, total
```

**完成判定**：`PYTHONPATH=src ruff check src/services/customer_service.py` → 0 errors

---

### Step 2: 修改 customers router 增加分页参数并返回分页元数据

在 GET /customers路由增加 page=1（default）和 page_size=20（default）查询参数，调用 service 并将结果包装为分页结构。

操作：
- a) TBD - 待验证：`src/api/routers/customers.py` 当前 router 定义- b) 增加 Query 参数：`page: int = Query(default=1, ge=1)` 和 `page_size: int = Query(default=20, ge=1, le=100)`
- c) 调用 `svc.list_customers(ctx.tenant_id, page, page_size)`
- d) 计算 `total_pages = ceil(total / page_size)` 并写入响应 data

示例代码（≤15 行）：

```python
from math import ceil

@router.get("/")
async def list_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CustomerService(session)
    customers, total = await svc.list_customers(ctx.tenant_id, page, page_size)
    total_pages = ceil(total / page_size) if total > 0 else 0
    return {
        "success": True,
        "data": {
            "items": [c.to_dict() for c in customers],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }
```

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/customers.py` → 0 errors

---

### Step 3: 在 CustomerService 抛出 ValidationException 处理参数边界在 Step1 方法首部加入 page/page_size 参数校验，非法值抛 ValidationException（400 转422）。

操作：
- a) 在 list_customers 方法体首行调用参数校验：
  - `if page < 1: raise ValidationException("page must be >= 1")`
  - `if page_size not in range(1, 101): raise ValidationException("page_size must be 1-100")`
- b) 确保 TBD - 待验证：`src/services/customer_service.py`头部 `from pkg.errors.app_exceptions import ValidationException` 已导入

示例代码（≤10 行）：

```python
from pkg.errors.app_exceptions import ValidationException

async def list_customers(self, tenant_id: int, page: int = 1, page_size: int = 20) -> ...:
    if page < 1:
        raise ValidationException("page must be >= 1")
    if page_size not in range(1, 101):
        raise ValidationException("page_size must be 1-100")
    offset = (page - 1) * page_size
    ...
```

**完成判定**：`PYTHONPATH=src mypy src/services/customer_service.py` →0 errors（如 mypy 配置存在）；否则 `ruff check src/services/customer_service.py` → 0 errors

---

### Step 4:补充单元测试覆盖分页路径

在 `tests/unit/test_customer_service.py` 新增 fixture 和 test cases：默认分页、第二页、page_size 边界、total 为零等场景。

操作：
- a) TBD - 待验证：`tests/unit/test_customer_service.py` 现有 fixture 结构
- b) 新增 `mock_db_session` 中的 `page_size=20` 数据切片的 mock handler（参看 conftest.py MockRow / MockResult 用法）
- c) 写测试函数：`test_list_customers_returns_paginated(self, customer_service)`、`test_list_customers_page2_offset(self, customer_service)`、`test_list_customers_invalid_page_raises(self, customer_service)`

示例测试结构（≤15 行）：

```python
import pytest
from unittest.mock import AsyncMock
from pkg.errors.app_exceptions import ValidationException

class TestCustomerServicePagination:
    async def test_list_customers_returns_total(self, customer_service, mock_db_session):
        customers, total = await customer_service.list_customers(tenant_id=1, page=1, page_size=20)
        assert total == 20
        assert len(customers) <= 20

    async def test_list_customers_page2_offset(self, customer_service):
        customers, total = await customer_service.list_customers(tenant_id=1, page=2, page_size=20)
        assert isinstance(customers, list)

    async def test_list_customers_invalid_page_raises(self, customer_service):
        with pytest.raises(ValidationException):
            await customer_service.list_customers(tenant_id=1, page=0, page_size=20)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed

---

### Step 5: 新建集成测试验证真分页行为

在 `tests/integration/` 新建 `test_customer_pagination_integration.py`，使用 real Postgres（db_schema fixture），插入45 条 customers 数据，验证 page 1 返回 ≤20 条、page 2 返回后续数据且不与 page 1 重复。

操作：
- a) 创建 `tests/integration/test_customer_pagination_integration.py`
- b) 使用 `db_schema` fixture 创建表，使用 `tenant_id` fixture注入 tenant- c)插入 45 条 seed 数据，复用 `_seed_customer` helper
- d) 断言 page=1 & page_size=20 返回 20 条；page=2 返回剩余 25 条中的 ≤20 条；total=45 total_pages=3

示例（≤20 行）：

```python
import pytest
from services.customer_service import CustomerService

@pytest.mark.integration
class TestCustomerPaginationIntegration:
    async def test_page1_returns_20_rows(self, db_schema, tenant_id, async_session):
        svc = CustomerService(async_session)
        for i in range(45):
            await _seed_customer(async_session, tenant_id, name=f"Customer {i}")
        customers, total = await svc.list_customers(tenant_id=tenant_id, page=1, page_size=20)
        assert len(customers) == 20
        assert total == 45

    async def test_page2_returns_different_rows(self, db_schema, tenant_id, async_session):
        svc = CustomerService(async_session)
        page1_ids = {c.id for c in (await svc.list_customers(tenant_id, page=1, page_size=20))[0]}
        page2_customers, _ = await svc.list_customers(tenant_id, page=2, page_size=20)
        page2_ids = {c.id for c in page2_customers}
        assert page1_ids.isdisjoint(page2_ids)
```

**完成判定**：`DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_customer_pagination_integration.py -v` → 全 passed

---

### Step 6: ruff lint 全量检查对本次涉及的三个文件运行 `ruff check` 和 `ruff format --check`。

操作：
运行 `PYTHONPATH=src ruff check src/services/customer_service.py src/api/routers/customers.py tests/unit/test_customer_service.py tests/integration/test_customer_pagination_integration.py`

运行 `PYTHONPATH=src ruff format --check src/services/customer_service.py src/api/routers/customers.py`

**完成判定**：两命令均 exit 0 无输出

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/services/customer_service.py src/api/routers/customers.py` → 0 errors
- [ ] `PYTHONPATH=src ruff format --check src/services/customer_service.py src/api/routers/customers.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed
- [ ] `DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_customer_pagination_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如涉及 migration；无 DB改动则跳过）
- [ ] 端到端：`curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/customers?page=1&page_size=20"` 返回 `{"success": true, "data": {"items": [...], "total": N, "page": 1, "page_size": 20, "total_pages": M}}`（需先启动服务：`PYTHONPATH=src uvicorn src.main:app --reload`）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| OFFSET 大页码查询超时（大租户、深度分页） | 低 | 中 | 回退至 `page_size=100` 上限，限制前端翻页深度；或降级为前端一次性拉全量（降级时注明性能风险） |
| page_size 上限 100 被前端无限循环调用耗尽 DB 连接池 | 中 | 中 | 接入 API rate limit（源自 #567 限流模块）；短期可临时将 page_size 上限降至 50 并通知前端 |
| 新增参数导致旧前端未传参时 page 默认1（向后兼容正常） | 极低 | 低 | 已通过 Query(default=...) 保证默认值；无需回退 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/customer_service.py src/api/routers/customers.py tests/unit/test_customer_service.py tests/integration/test_customer_pagination_integration.py
git commit -m "feat(customers): add server-side pagination page/page_size (20/page)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#565): add server-side pagination to GET /customers" --body "Closes #565"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 需检索仓库内其他已实现分页的 router（如 tickets 或 opportunities），参考其分页包装格式
- 父 issue / 关联：#557（客户模块整体），#564（后端分页基础能力），#566（前端子模块分页控件接入）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
