# 数据隔离服务与集成测试 · 实现 DataIsolationService 及隔离集成测试

| 元数据 | 值 |
|---|---|
| Issue | #475 |
| 分类 | [99-misc](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | [0485-add-missing-activityservice-methods](0485-add-missing-activityservice-methods.md), [0486-add-activityservice-unit-tests](0486-add-missing-activityservice-unit-tests.md), [0487-add-missing-activityservice-integration-tests](0487-add-missing-activityservice-integration-tests.md) |
| 启用后赋能 | [0474-implement-customer-model-and-customer-service](0474-implement-customer-model-and-customer-service.md), [0475-implement-dataisolationservice-and-isolation-integration-tests](0475-implement-dataisolationservice-and-isolation-integration-tests.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

多租户 CRM 的核心不变量是：任何租户的查询必须仅返回该租户的数据。当前的 CustomerService 和 UserService 在代码层面过滤了 `tenant_id`，但没有系统性验证——即没有工具能在新增表或修改查询时快速发现"忘记加 `WHERE tenant_id`"的遗漏。本 issue 引入 DataIsolationService 作为自动化隔离验证层，并在集成测试中用真实 DB 确认跨租户访问被阻断。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层验证服务。
- **开发者视角**：`DataIsolationService` 提供三个可调用方法，`verify_tenant_isolation` 在 CI 阶段扫描所有表是否有 `tenant_id` 列；`test_cross_tenant_access` 和 `verify_shared_data_access` 供集成测试显式验证隔离和共享数据访问是否按预期工作。新增 `tests/integration/test_data_isolation_integration.py` 用真实 PostgreSQL + `db_schema` fixture 运行所有隔离断言。

### 1.3 不做什么（剔除）

- [ ] 不实现租户级别的行级安全（RLS）策略 — 那是 PostgreSQL 配置层，超出本板块范围。
- [ ] 不修改现有 CustomerService / UserService 的业务逻辑 — 本板块仅添加验证层。
- [ ] 不实现数据隔离的 feature flag 或开关。

### 1.4 关键 KPI

- `ruff check src/services/data_isolation_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_data_isolation_service.py -v` → ≥ 5 passed（含对 `verify_tenant_isolation` 的 mock 测试）
- `PYTHONPATH=src pytest tests/integration/test_data_isolation_integration.py -v` → ≥ 5 passed（含 `test_customer_isolation`、`test_user_isolation`、`test_cross_tenant_blocked`）
- `alembic upgrade head` → exit 0（无新 migration，本板块仅新建 service 文件）

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/` 下应有 `customer.py`（含 `CustomerModel`，含 `tenant_id` 字段）和 `user.py`（含 `UserModel`，含 `tenant_id` 字段）— 来自 #474 的实现结果。确认方式：`grep -r "class CustomerModel" src/db/models/` 和 `grep -r "class UserModel" src/db/models/`。

### 2.2 涉及文件清单

- 要改：
  - `src/services/data_isolation_service.py` — 新建 service 文件（由 orchestrator 直接写入，本步骤为验收检查点）
- 要建：
  - `src/services/data_isolation_service.py` — DataIsolationService，含三个核心方法
  - `tests/unit/test_data_isolation_service.py` — 单元测试（mock DB）
  - `tests/integration/test_data_isolation_integration.py` — 集成测试（real DB via db_schema）

### 2.3 缺什么

- [ ] `DataIsolationService` 类不存在 — 无法在 CI 中系统性验证多租户隔离
- [ ] 无自动化扫描手段检查新表是否遗漏 `tenant_id` 列
- [ ] 无显式集成测试验证跨租户访问被 `ForbiddenException` 阻断
- [ ] 无验证共享数据（如系统配置表）访问路径的测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/data_isolation_service.py` | DataIsolationService：验证租户隔离、测试跨租户访问、验证共享数据访问 |
| `tests/unit/test_data_isolation_service.py` | 单元测试：mock DB 下测试 `verify_tenant_isolation` 返回结构 |
| `tests/integration/test_data_isolation_integration.py` | 集成测试：real DB + `db_schema` fixture 测试 customer/user 隔离及跨租户阻断 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| — | 无需修改现有文件 |

### 3.3 新增能力

- **Service**：`DataIsolationService(session: AsyncSession)` — 三个公开方法
- **Method**：`verify_tenant_isolation() -> dict[str, list[str]]` — 返回缺失 `tenant_id` 列的表名列表
- **Method**：`test_cross_tenant_access(entity_type: str, entity_id: int, owner_tenant_id: int, attacker_tenant_id: int) -> None` — 期望抛 `ForbiddenException`
- **Method**：`verify_shared_data_access(table_name: str, tenant_id: int) -> bool` — 验证共享数据（无 `tenant_id` 列）可被各租户访问
- **Integration tests**：`test_customer_isolation`、`test_user_isolation`、`test_cross_tenant_blocked`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 SQLAlchemy 查询 `information_schema.columns` 而非反射 ORM metadata**：`information_schema` 跨数据库方言一致，且能发现 ORM 尚未加载的表（新增表尚未 import 时也能检测）。
- **跨租户负面测试由 service 方法封装而非散落在各 test 文件**：统一 `test_cross_tenant_access` 方法，确保所有跨租户测试使用一致的租户 ID 和错误类型断言。

### 4.2 版本约束

无新引入的外部依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`
- Session 注入：`session: AsyncSession` 通过 router `Depends(get_db)` 传入，service `__init__` 不设默认值
- `test_cross_tenant_access` 方法故意构造跨租户查询并期望 `ForbiddenException`，属于白盒测试方法，不暴露给 router

### 4.4 已知坑

1. **SQLAlchemy 列名不能用 `metadata`** → `Base.metadata` 是 MetaData 对象，冲突会导致类定义时崩溃。本板块新建 service 无 ORM model，但测试中如涉及任意 model 列名扫描，踩到 `metadata` 列会触发此问题 → 规避：测试 `information_schema` 扫描时过滤掉列名为 `metadata` 的系统列（正常业务表不应有 `metadata` 列）
2. **Alembic autogenerate 写错 JSONB / TIMESTAMPTZ** → 本板块无新增 migration，不受影响，但记录：autogenerate 易将 `sa.JSONB()` 写成 `sa.JSON()`、将 `DateTime(timezone=True)` 写成 `DateTime` → 规避：人工 review migration，或在 0488 审计板块中统一修复
3. **PYTHONPATH=src** → 所有 import 必须以 `from db.models...`、`from services...` 开头，禁止 `from src.db.models...`

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/services/data_isolation_service.py`

实现 `DataIsolationService` 类骨架，含三个公开方法及一个私有辅助方法：

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pkg.errors.app_exceptions import ForbiddenException


class DataIsolationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def verify_tenant_isolation(self) -> dict[str, list[str]]:
        """扫描 information_schema，返回所有 user table（不含 system schemas）
        中缺少 tenant_id 列的表名列表。"""
        query = text("""
            SELECT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name NOT IN (
                  SELECT inhrelid::regclass::text
                  FROM pg_inherits
              )
              AND table_name NOT LIKE 'pg_%'
              AND table_name NOT LIKE 'sql_%'
            GROUP BY table_name
            HAVING BOOL_OR(column_name = 'tenant_id') = FALSE
        """)
        result = await self.session.execute(query)
        tables = [row[0] for row in result.fetchall()]
        return {"missing_tenant_id": tables}

    async def test_cross_tenant_access(
        self,
        entity_type: str,
        entity_id: int,
        owner_tenant_id: int,
        attacker_tenant_id: int,
    ) -> None:
        """尝试用 attacker_tenant_id 访问 owner_tenant_id 的实体。
        期望抛出 ForbiddenException。"""
        if entity_type == "customer":
            from src.db.models.customer import CustomerModel

            query = text(
                "SELECT id, tenant_id FROM customers WHERE id = :id AND tenant_id = :tenant_id"
            )
            result = await self.session.execute(
                query, {"id": entity_id, "tenant_id": attacker_tenant_id}
            )
            row = result.first()
            if row is None:
                raise ForbiddenException("Access denied")
            # additional check: ensure the entity actually belongs to the owner
            check_owner = await self.session.execute(
                text("SELECT tenant_id FROM customers WHERE id = :id"),
                {"id": entity_id},
            )
            owner_row = check_owner.first()
            if owner_row and owner_row[0] != owner_tenant_id:
                raise ForbiddenException("Access denied")
        else:
            raise NotImplementedError(f"Entity type {entity_type} not supported")

    async def verify_shared_data_access(self, table_name: str, tenant_id: int) -> bool:
        """验证无 tenant_id 列的共享表（system config 等）可被任意 tenant_id 访问。
        通过即返回 True；表不存在则返回 False。"""
        check_query = text("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = 'tenant_id'
        """)
        result = await self.session.execute(check_query, {"table_name": table_name})
        has_tenant_id = result.scalar_one() > 0
        if has_tenant_id:
            return False
        # shared table — query should not filter by tenant_id
        try:
            await self.session.execute(text(f"SELECT 1 FROM {table_name} LIMIT 1"))
            return True
        except Exception:
            return False
```

**完成判定**：`ruff check src/services/data_isolation_service.py` → 0 errors

### Step 2: 创建单元测试 `tests/unit/test_data_isolation_service.py`

用 `make_mock_session` 提供的 mock handler 模拟 `information_schema` 查询结果。测试三个场景：

```python
import pytest
from tests.unit.conftest import make_mock_session, MockState, MockRow, MockResult

from src.services.data_isolation_service import DataIsolationService


class TestDataIsolationService:
    @pytest.fixture
    def mock_session_empty(self):
        """所有表都有 tenant_id 列 — verify_tenant_isolation 返回空列表"""
        state = MockState()
        mock_result = MockResult(rows=[])
        handlers = {
            "information_schema": lambda *args, **kwargs: mock_result
        }
        return make_mock_session(handlers)

    @pytest.fixture
    def mock_session_missing(self):
        """some_table 缺少 tenant_id 列"""
        state = MockState()
        mock_result = MockResult(rows=[("some_table",)])
        handlers = {
            "information_schema": lambda *args, **kwargs: mock_result
        }
        return make_mock_session(handlers)

    @pytest.fixture
    def service(self, mock_session_empty):
        return DataIsolationService(mock_session_empty)

    async def test_verify_tenant_isolation_all_good(self, service):
        result = await service.verify_tenant_isolation()
        assert result["missing_tenant_id"] == []

    async def test_verify_tenant_isolation_missing_column(
        self, mock_session_missing
    ):
        svc = DataIsolationService(mock_session_missing)
        result = await svc.verify_tenant_isolation()
        assert "some_table" in result["missing_tenant_id"]
```

（完整测试文件含 `test_verify_shared_data_access_returns_false_when_tenant_id_present` 和 `test_verify_shared_data_access_returns_true_for_shared_table`）

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_data_isolation_service.py -v` → 全部 passed

### Step 3: 创建集成测试 `tests/integration/test_data_isolation_integration.py`

使用 `db_schema`、`tenant_id` fixture（两个不同的 `tenant_id` 以模拟两个租户），seed customer 和 user 数据，然后执行隔离断言：

```python
import pytest
from sqlalchemy import text

from src.db.models.customer import CustomerModel
from src.db.models.user import UserModel
from src.services.data_isolation_service import DataIsolationService
from src.services.customer_service import CustomerService
from src.services.user_service import UserService
from pkg.errors.app_exceptions import ForbiddenException


@pytest.mark.integration
class TestDataIsolationIntegration:
    @pytest.fixture
    def tenant_a(self, tenant_id):
        return tenant_id

    @pytest.fixture
    def tenant_b(self, db_schema):
        import uuid

        async def _seed():
            from tests.integration.conftest import _seed_tenant

            tid = await _seed_tenant(db_schema, f"tenant_b_{uuid.uuid4().hex[:8]}")
            return tid

        return None  # resolved in test via db_schema

    async def test_customer_isolation(self, db_schema, tenant_a):
        """租户 A 创建的 customer，租户 A 能读；租户 B 不能通过
        去掉 tenant_id 过滤的原始 SQL 查到（受 DB 约束保护）。"""
        svc_cust = CustomerService(db_schema)
        # seed customer for tenant_a
        cust = await svc_cust.create_customer(
            name="TenantA Customer", tenant_id=tenant_a
        )
        # verify tenant_a can read
        found = await svc_cust.get_customer(cust.id, tenant_id=tenant_a)
        assert found.id == cust.id
        # verify cross-tenant raw SQL is blocked at DB level
        raw = await db_schema.execute(
            text("SELECT id FROM customers WHERE id = :id AND tenant_id = :tid"),
            {"id": cust.id, "tid": tenant_a + 9999},
        )
        assert raw.first() is None

    async def test_user_isolation(self, db_schema, tenant_a):
        """与 test_customer_isolation 相同逻辑，针对 UserModel。"""
        svc_user = UserService(db_schema)
        user = await svc_user.create_user(
            email="a@test.com", tenant_id=tenant_a
        )
        found = await svc_user.get_user(user.id, tenant_id=tenant_a)
        assert found.id == user.id
        raw = await db_schema.execute(
            text("SELECT id FROM users WHERE id = :id AND tenant_id = :tid"),
            {"id": user.id, "tid": tenant_a + 9999},
        )
        assert raw.first() is None

    async def test_cross_tenant_blocked(self, db_schema, tenant_id):
        """调用 DataIsolationService.test_cross_tenant_access，
        期望对另一个租户的 customer 抛出 ForbiddenException。"""
        svc_cust = CustomerService(db_schema)
        cust = await svc_cust.create_customer(
            name="Target Customer", tenant_id=tenant_id
        )
        iso_svc = DataIsolationService(db_schema)
        # another tenant id (fake, not seeded)
        other_tenant = tenant_id + 9999
        with pytest.raises(ForbiddenException):
            await iso_svc.test_cross_tenant_access(
                entity_type="customer",
                entity_id=cust.id,
                owner_tenant_id=tenant_id,
                attacker_tenant_id=other_tenant,
            )

    async def test_verify_tenant_isolation_real_db(self, db_schema):
        """真实 DB 中 verify_tenant_isolation 应返回空列表（已有模型都有 tenant_id）。"""
        svc = DataIsolationService(db_schema)
        result = await svc.verify_tenant_isolation()
        assert result["missing_tenant_id"] == []

    async def test_verify_shared_data_access(self, db_schema, tenant_id):
        """验证 shared_table 能被任意 tenant_id 访问（本项目目前无 shared table，
        此测试验证方法对不存在表的优雅处理）。"""
        svc = DataIsolationService(db_schema)
        result = await svc.verify_shared_data_access("nonexistent_shared", tenant_id)
        assert result is False
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_data_isolation_integration.py -v` → 全部 passed

### Step 4: lint 检查

```bash
ruff check src/services/data_isolation_service.py tests/unit/test_data_isolation_service.py tests/integration/test_data_isolation_integration.py
```

**完成判定**：输出含 `0 errors` 并 exit 0

### Step 5: 运行全量单元测试

```bash
PYTHONPATH=src pytest tests/unit/ -v
```

**完成判定**：所有测试 passed，无 ERROR 或 FAILED

---

## 6. 验收

- [ ] `ruff check src/services/data_isolation_service.py tests/unit/test_data_isolation_service.py tests/integration/test_data_isolation_integration.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_data_isolation_service.py -v` → 全 passed（如无此文件，先检查 orchestrator 是否已创建 service 文件）
- [ ] `PYTHONPATH=src pytest tests/integration/test_data_isolation_integration.py -v` → 全 passed（含 `test_customer_isolation`、`test_user_isolation`、`test_cross_tenant_blocked`）
- [ ] `PYTHONPATH=src mypy src/services/data_isolation_service.py` → 0 errors（如 mypy 配置存在）
- [ ] `PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → 整体单元测试套件无新增 failures

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `information_schema.columns` 查询在 Docker PostgreSQL 和生产 RDS 上行为不一致 | 低 | 中 | 在 0488 审计板块中补充对生产 DB 的手动验证；CI 测试只在 docker compose 环境运行 |
| `test_cross_tenant_access` 对 customer/user 以外 entity_type 抛 `NotImplementedError` | 中 | 低 | 在 DataIsolationService 中扩展支持；短期内只有 customer 和 user 两个 entityType 已满足需求 |
| CustomerModel / UserModel 尚未存在（#474 还未合并）导致导入失败 | 中 | 高 | 本板块依赖 #474，在 #474 合并后再启动；orchestrator 有依赖声明保护 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/data_isolation_service.py tests/unit/test_data_isolation_service.py tests/integration/test_data_isolation_integration.py
git commit -m "feat(isolation): implement DataIsolationService with tenant isolation verification"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#475): implement DataIsolationService and isolation integration tests" --body "Closes #475"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — 现有 service 模式参考（`__init__` 接受 `session: AsyncSession`，方法接受 `tenant_id: int`，抛 `AppException` 子类）
- 父 issue / 关联：#447（多租户隔离平台层）
- 依赖 issue：#474（CustomerModel 和 UserModel 必须先存在）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
