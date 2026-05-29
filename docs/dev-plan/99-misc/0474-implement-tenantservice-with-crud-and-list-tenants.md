# TenantService ·基础 CRUD 与多租户列表查询

| 元数据 | 值 |
|---|---|
| Issue | #474 |
| 分类 | 99-misc |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [#473 板块](../99-misc/0473-add-tenant-model.md) |
| 启用后赋能 | [#447 板块](../20-sales/0447-???-parent.md)（父 issue，最终全租户视图依赖此服务） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

目前代码库缺少 `TenantService`，没有任何 service 层代码能对 `Tenant` ORM 模型执行增删改查操作。父 issue #447 的多租户功能无法推进，所有依赖租户查询的下游模块（如销售视图、客户归属判断）都处于阻塞状态。#473 已建立 `Tenant` ORM 模型，本板块是其后第一个必须完成的后端实现。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 本板块纯底层 service，暂无 API路由暴露。
- **开发者视角**：`from services.tenant_service import TenantService` 可直接实例化并调用 7 个方法，返回 `Tenant` ORM 对象列表或单个对象，无需自行写 SQL。

### 1.3 不做什么（剔除）

- [ ] 不实现任何 HTTP router 或 API endpoint（后续 #475 板块负责）
- [ ] 不实现租户续期、计费、或用量告警等高级业务逻辑（`get_tenant_usage` 仅返回原始 usage 数据，聚合展示由消费方负责）
- [ ] 不修改已存在的 `Tenant` ORM 模型结构（仅在使用层面操作）
- [ ] 不在 service内部调用 `.to_dict()`，序列化由 router 负责（路由未在本板块实现，但此约束早早锁定）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_tenant_service.py -v` →7 passed（每个 service 方法至少一个测试用例）
- `ruff check src/services/tenant_service.py src/db/models/tenant.py` → 0 errors
- `PYTHONPATH=src python -c "from services.tenant_service import TenantService; print('import ok')"` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：src/db/models/tenant.py L? — #473 应该已建立 Tenant ORM 模型，需确认字段名（tenant_id/name/status/usage...）和表名是否已定义现有 service 参考：

```{1:30}:src/services/customer_service.py
class CustomerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_customer(self, customer_id: int, tenant_id: int) -> CustomerModel:
        result = await self.session.execute(
            select(CustomerModel).where(
                CustomerModel.id == customer_id,
                CustomerModel.tenant_id == tenant_id,
            )
        )
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundException("Customer")
        return entity
```

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/tenant.py` —确认已在 #473 中建立（若 #473 尚未合并，本板块需等待）
  - `tests/unit/conftest.py` — 如需新增 tenant相关的 mock handler（参考 `make_customer_handler`模式）
- 要建：
  - `src/services/tenant_service.py` — 核心实现，7 个方法
  - `tests/unit/test_tenant_service.py` — 7 个方法的全量单元测试
  - `alembic/versions/<TBD>_<slug>.py` — 仅若 #473 未生成 migration，需新建 tenants 表（通常在 #473 中完成）

### 2.3 缺什么

- [ ] `TenantService` 类本身不存在，无任何租户级别的 service 方法
- [ ] 7 个业务方法缺失：create_tenant / get_tenant / update_tenant / suspend_tenant / delete_tenant（软删除）/ list_tenants（分页）/ get_tenant_usage
- [ ]缺少针对 `TenantService` 各方法的单元测试覆盖- [ ] 缺少 tenancy相关的 mock handler，以在单元测试中模拟 SQL 响应

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/tenant_service.py` | TenantService 类，提供 7 个 async 方法操作 Tenant ORM |
| `tests/unit/test_tenant_service.py` | 7 个方法各自的 happy-path + 异常路径单元测试（mock session） |
| `tests/unit/conftest.py` | 新增 `make_tenant_handler(state)`，参照 `make_customer_handler`模式（若 mock 需要） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `tests/unit/conftest.py` | 新增 `make_tenant_handler` factory function if needed |
| `src/db/models/tenant.py` | #473 已建立，本板块只使用不修改 |

### 3.3 新增能力

- **Service class**：`TenantService(session: AsyncSession)` — 7 个方法
- **Method: `create_tenant`**：创建租户，无 tenant_id 过滤（系统级操作），返回创建后 ORM 对象
- **Method: `get_tenant`**：按 id 查询，返回 Tenant ORM 或 raise `NotFoundException`
- **Method: `update_tenant`**：按 id 更新 name / plan / quota，返回更新后 ORM
- **Method: `suspend_tenant`**：将租户 status 设为 suspended，不删除数据
- **Method: `delete_tenant`**：软删除（status=deleted 或 is_deleted flag），不物理删除行
- **Method: `list_tenants`**：分页查询，返回 `(list[TenantORM], int)` 元组，遵循服务模式- **Method: `get_tenant_usage`**：返回租户当前 usage 字段（dict / dataclass），仅读取---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **软删除不物理删除**：租户数据有业务连续性要求（合同审计、账单追溯），`delete_tenant`置 `is_deleted=True` 或 `status='deleted'`，查询默认过滤软删除记录，与用户管理的软删除策略一致。
- **session 无默认值**：遵循 CLAUDE.md §Service Pattern，`TenantService.__init__` 接收 `session: AsyncSession`，拒绝默认值，保证所有 DB 操作显式注入。
- **不返回 ApiResponse / 不调用 .to_dict()**：Service 层只返回 ORM 对象，错误抛 AppException 子类，路由负责序列化（本板块无路由，但约束早早锁定）。
- **tenant_id 过滤**：`get_tenant` / `update_tenant` / `suspend_tenant` / `delete_tenant` 接受 `tenant_id` 参数防止跨租户越权（虽然是系统管理操作，防御性过滤不可少）。

### 4.2 版本约束

N/A — 无新依赖引入，使用项目已有包（SQLAlchemy 2.x async、pytest）

### 4.3 兼容性约束

- 多租户安全：所有面向租户数据的方法必须 `WHERE tenant_id = :tenant_id`（即使目前租户管理为系统级操作，也遵守此约束以备未来 RBAC 扩展）
- `TenantService.__init__(session: AsyncSession)` — 不允许 `session=None`
- 方法返回值：返回 `Tenant` ORM 对象或其列表，不在 service 层调用 `.to_dict()`
- 错误处理：仅通过 `raise NotFoundException` / `ValidationException` 等 AppException 子类传递错误

### 4.4 已知坑

1. **SQLAlchemy `metadata` 列名冲突** → 规避：若 `Tenant` ORM 模型中存在 JSON 列，不得命名为 `metadata`，须改为 `event_metadata` / `tenant_metadata`（`Base.metadata` 会与列名冲突导致 `AttributeError`）
2. **Alembic autogenerate 误写 JSON 而非 JSONB** → 规避：若 #473 生成的 migration 用了 `sa.JSON()` 而非 `sa.JSONB()`，手动改为 `sa.JSONB()`（或确认 Tenant 模型字段映射正确）
3. **单元测试 mock session 必须每测试独立** →规避：各测试方法通过 `mock_db_session` fixture注入独立 MockState，不得共享全局状态

---

## 5. 实现步骤（按顺序）

### Step 1:确认 Tenant ORM 模型并设计 tenant_handler mock

确认 #473 已创建的 `Tenant` ORM 模型的字段名（`id`, `tenant_uuid`, `name`, `status`, `plan`, `quota`, `usage` 等），读取 [`src/db/models/tenant.py`](../../src/db/models/tenant.py) 确认 schema。参考 `make_customer_handler` 工厂模式，在 `tests/unit/conftest.py` 新增 `make_tenant_handler(state)`，支持 SELECT / INSERT / UPDATE / DELETE 四类操作的 mock拦截。

操作：
- a) 读取 `src/db/models/tenant.py`，确认字段名和 `__tablename__`
- b) 在 `tests/unit/conftest.py` 中新增 `make_tenant_handler(state)` 函数，参照 `make_customer_handler` 的返回格式```python
# 测试代码（conftest.py 新增）
def make_tenant_handler(state: MockState):
    """Returns (query_handler, insert_handler, ...) for tenant table."""
    # stubs: SELECT by id, SELECT paginated, INSERT, UPDATE status, DELETE (soft)
```

**完成判定**：`PYTHONPATH=src python -c "from tests.unit.conftest import make_tenant_handler, MockState; s=MockState(); h=make_tenant_handler(s); print(len(h))"` exit 0

### Step 2: 实现 TenantService 类骨架与 create_tenant

在 `src/services/tenant_service.py` 创建 `TenantService` 类，`__init__` 接受 `session: AsyncSession`。实现 `create_tenant` 方法：接收 `name: str, plan: str, created_by: int`，插入新租户记录，返回 `Tenant` ORM 对象（不调用 `.to_dict()`）。

```python
# src/services/tenant_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from pkg.errors.app_exceptions import NotFoundException, ValidationException

class TenantService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_tenant(self, name: str, plan: str, created_by: int) -> Tenant:
        tenant = Tenant(name=name, plan=plan, status="active", created_by=created_by)
        self.session.add(tenant)
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant
```

**完成判定**：`ruff check src/services/tenant_service.py` → 0 errors

### Step 3: 实现 get_tenant / update_tenant / suspend_tenant

实现 `get_tenant(tenant_id: int, caller_tenant_id: int)` — 带 tenant_id 过滤的查询，查不到 raise `NotFoundException`。实现 `update_tenant(tenant_id, caller_tenant_id, **fields)` — 按 id + tenant_id 更新非只读字段，返回更新后 ORM。实现 `suspend_tenant(tenant_id, caller_tenant_id)` — 将 status设为 `suspended`。

```python
    async def get_tenant(self, tenant_id: int, caller_tenant_id: int) -> Tenant:
        result = await self.session.execute(
            select(Tenant).where(Tenant.id == tenant_id, Tenant.tenant_id == caller_tenant_id)
        )
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundException("Tenant")
        return entity```

**完成判定**：`ruff check src/services/tenant_service.py` → 0 errors；`PYTHONPATH=src python -c "from services.tenant_service import TenantService; print('ok')"` exit 0

### Step 4: 实现 delete_tenant（软删除）与 list_tenants（分页）

实现 `delete_tenant(tenant_id, caller_tenant_id)` — 软删除，将 `is_deleted=True` 或 `status='deleted'`。不得使用物理 DELETE SQL。
实现 `list_tenants(caller_tenant_id: int, page: int = 1, page_size: int = 20) -> tuple[list[Tenant], int]` — COUNT 查询 + 带 `is_deleted`过滤的分页 SELECT，返回 `(items, total)` 元组。

```python
    async def delete_tenant(self, tenant_id: int, caller_tenant_id: int) -> Tenant:
        tenant = await self.get_tenant(tenant_id, caller_tenant_id)
        tenant.is_deleted = True
        tenant.status = "deleted"
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant

    async def list_tenants(
        self, caller_tenant_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[Tenant], int]:
        # WHERE tenant_id=? AND is_deleted=False
        count_result = await self.session.execute(
            select(func.count(Tenant.id)).where(
                Tenant.tenant_id == caller_tenant_id,
                Tenant.is_deleted == False,  # noqa: E712
            )
        )
        total = count_result.scalar_one()
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(Tenant)
            .where(Tenant.tenant_id == caller_tenant_id, Tenant.is_deleted == False)  # noqa: E712
            .order_by(Tenant.id)
            .limit(page_size)
            .offset(offset)
        )
        return list(result.scalars().all()), total
```

**完成判定**：`ruff check src/services/tenant_service.py` →0 errors；占位 fixture 可编译### Step 5: 实现 get_tenant_usage

实现 `get_tenant_usage(tenant_id: int, caller_tenant_id: int)` — 返回租户当前 usage 数据。若 Tenant 模型中 usage字段为 JSONB 列，直接返回 `tenant.usage`；若为独立引用表（usage 由其他系统统计），则查对应聚合行。签名：`async def get_tenant_usage(self, tenant_id, caller_tenant_id) -> dict`。

```python
    async def get_tenant_usage(self, tenant_id: int, caller_tenant_id: int) -> dict:
        tenant = await self.get_tenant(tenant_id, caller_tenant_id)
        return {"tenant_id": tenant.id, "usage": tenant.usage}
```

**完成判定**：`PYTHONPATH=src python -c "from services.tenant_service import TenantService; print('usage method exists')"` exit 0

### Step 6: 编写全量单元测试

在 `tests/unit/test_tenant_service.py` 创建测试类 `TestTenantService`，为7 个方法各写1-2 个测试用例（happy-path + 异常路径）。使用 `make_mock_session` 和新建的 `make_tenant_handler` 构建 mock session。每个测试直接断言返回 ORM 属性值或 `pytest.raises`。

```python
# tests/unit/test_tenant_service.py（骨架）
import pytest
from tests.unit.conftest import make_mock_session, make_tenant_handler, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_tenant_handler(state)])

@pytest.fixture
def tenant_service(mock_db_session):
    return TenantService(mock_db_session)

class TestTenantService:
    async def test_create_tenant(self, tenant_service, mock_db_session):
        # ... 调用 assert
```

每个方法需覆盖：
- `create_tenant`：正常创建 +验证 id 自增
- `get_tenant`：查到 +查不到抛 NotFoundException
- `update_tenant`：更新字段成功
- `suspend_tenant`：status变为 suspended
- `delete_tenant`：is_deleted 变为 True
- `list_tenants`：返回数量符合分页
- `get_tenant_usage`：返回格式正确

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_tenant_service.py -v` → 7 passed（或 ≥7 passed）

### Step 7: 运行全量 lint +确认依赖关系已满足

对所有变更文件执行 ruff check。确认 `src/db/models/tenant.py` 与 `alembic/versions/` 中的 migration 均已就绪（由 #473 提供），本板块仅使用不修改。

**完成判定**：`ruff check src/services/tenant_service.py tests/unit/test_tenant_service.py tests/unit/conftest.py` → 0 errors---

## 6. 验收

- [ ] `ruff check src/services/tenant_service.py tests/unit/test_tenant_service.py tests/unit/conftest.py` →0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_tenant_service.py -v` → ≥ 7 passed- [ ] `PYTHONPATH=src python -c "from services.tenant_service import TenantService; from pkg.errors.app_exceptions import NotFoundException,ValidationException,ForbiddenException; print('imports ok')"` → 0 errors
- [ ] `PYTHONPATH=src python -c "from tests.unit.conftest import make_tenant_handler, MockState; s=MockState(); h=make_tenant_handler(s); print('tenant mock ok')"` → 0 errors
- [ ] `ruff format --check src/services/tenant_service.py tests/unit/test_tenant_service.py` →0 differences（格式合规）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #473尚未合并，Tenant ORM 模型字段未知，导致 mock handler 与实际 schema 不匹配 | 中 | 高 | 本板块在 #473 合并后再实施；两板块设置序衔依赖，合并后补 dev-plan |
| `delete_tenant` 与 `suspend_tenant` 的 status 值（`deleted` vs `suspended`）与前端期望不一致 | 低 | 中 | 与前端对齐后修改常量值；不涉及数据迁移 |
| `list_tenants` 的 `is_deleted` 过滤逻辑与租户软删除字段设计（软删除字段是 `status` 还是独立 `is_deleted` 列）不一致 | 低 | 中 | 若模型采用 status = 'deleted' 而非独立 flag，调整 WHERE条件；立即在 §4.4 已知坑中记录此模糊点 |
| 单元测试 mock handler遗漏边界条件（如空表 ZERO results） | 低 | 中 |补充对应 mock handler 处理 `scalar_one()` 在空结果时报错场景 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/tenant_service.py tests/unit/test_tenant_service.py tests/unit/conftest.py
git commit -m "feat(service): implement TenantService with 7 CRUD and list methods"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat: implement TenantService (#474)" --body "Closes #474"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../src/services/customer_service.py) — 参照其结构（session / raise / return ORM）
- 同类测试实现：[`tests/unit/conftest.py`](../../tests/unit/conftest.py) — `make_customer_handler` / `make_user_handler` 工厂函数提供 mock handler 模式参考
- 父 issue /关联：#447（父 issue，多租户 CRM整体规划）、#473（Tenant ORM 模型，先决条件）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
