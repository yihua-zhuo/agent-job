# 板③ · 补充 Identity 系列模型单元测试

| 元数据 | 值 |
|---|---|
| Issue | #429 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [板① 补充 Identity 系列 ORM 模型与关系定义](../40-campaigns/0428-add-orm-identity-models-and-relationships.md) |
| 启用后赋能 | [板④ 补充 WorkflowService 工作流状态机与规则匹配](../50-automation/0463-build-workflowservice-with-crud-execute-methods.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #428 已为多租户 CRM 引入了 OrganizationModel / DepartmentModel（身份层级）及 RolePermissionModel / UserRoleModel（RBAC 关系）四个 ORM 模型，并已在 Service 层建立了相应的 CRUD 操作。为确保这些模型及其级联关系在后续迭代中不出现回归，需要在单元测试层建立完整的覆盖。

目前 `tests/unit/`目录下仅有 `test_tenant_model.py` 和 `test_user_model.py` 两个参考实现，缺乏对新增 identity模型的测试。若不补齐，Model 层或 Service 层的改动无法在 CI 阶段被捕获，只能在集成测试（慢 +依赖 DB 环境）才能发现。

### 1.2 做完后

- **用户视角**：无用户可见变化 —纯底层测试补充。
- **开发者视角**：`tests/unit/test_identity_model.py` 和 `tests/unit/test_rbac_model.py` 两个文件完整覆盖 OrganizationModel、DepartmentModel、RolePermissionModel、UserRoleModel 的创建、查询及租户隔离行为；CI 在 `pytest tests/unit/` 阶段即可拦截 Model/Service 层回归。

### 1.3 不做什么（剔除）

- [ ] 不测试 Integration 层（real DB 行为由集成测试覆盖，不在本板块范围）
- [ ] 不测试 Router / HTTP 层（API 行为另立专项测试）
- [ ] 不改任何已上线 Model 的 schema（仅新增测试）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_identity_model.py tests/unit/test_rbac_model.py -v` → 全 passed
- `PYTHONPATH=src pytest tests/unit/ -v` → 全 passed（回归保证）
- `ruff check src/db/models/identity*.py src/services/*identity*.py tests/unit/test_identity*.py tests/unit/test_rbac*.py` → 0 errors
- 所有新测试均通过 Mock 机制，不使用真实 DB

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/db/models/` 下是否存在 `organization.py`、`department.py`、`role_permission.py`、`user_role.py`；以及 `src/services/` 下是否有对应 service（如 IdentityService）。建议用以下命令确认：

```bash
PYTHONPATH=src python -c "from db.models.organization import OrganizationModel; print('OK')"
PYTHONPATH=src python -c "from db.models.department import DepartmentModel; print('OK')"
```

参考测试模式（已有实现）：

主入口：[`tests/unit/test_tenant_model.py`](../../tests/unit/test_tenant_model.py) L{1}

```{python}:{示例结构}:
# tests/unit/test_tenant_model.py 结构（参考）
import pytest
from tests.unit.conftest import make_mock_session, make_count_handler, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_count_handler(state)])

@pytest.fixture
def tenant_service(mock_db_session):
    return TenantService(mock_db_session)

class TestTenantModel:
    async def test_get_tenant_by_id(self, tenant_service, mock_db_session):
        # ... 测试体        pass
```

主入口：[`tests/unit/test_user_model.py`](../../tests/unit/test_user_model.py) L{1}

```{python}:{示例结构}:
# tests/unit/test_user_model.py 结构（参考）
import pytest
from tests.unit.conftest import make_mock_session, make_user_handler, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_user_handler(state)])

@pytest.fixture
def user_service(mock_db_session):
    return UserService(mock_db_session)

class TestUserModel:
    async def test_create_user(self, user_service, mock_db_session):
        # ... tenant_id 隔离验证
        pass
```

### 2.2 涉及文件清单

- 要改：
  - [`tests/unit/conftest.py`](../../tests/unit/conftest.py) — 新增 `make_organization_handler`、`make_department_handler`、`make_role_permission_handler`、`make_user_role_handler`（如果 Issue #428 已在 conftest.py 中预置，跳过此步）
- 要建：
  - `tests/unit/test_identity_model.py` — OrganizationModel + DepartmentModel 单元测试
  - `tests/unit/test_rbac_model.py` — RolePermissionModel + UserRoleModel + cascade 行为测试
  - TBD - 待确认：`src/db/models/organization.py`、`department.py`、`role_permission.py`、`user_role.py`（来自 Issue #428）
  - TBD - 待确认：`src/services/identity_service.py` 或类似（来自 Issue #428）

### 2.3 缺什么

- [ ] `test_identity_model.py`：缺少 OrganizationModel 的按 ID 查询、列表查询（含租户隔离）测试- [ ] `test_identity_model.py`：缺少 DepartmentModel 的按 ID 查询、列表查询（含租户隔离）测试
- [ ] `test_rbac_model.py`：缺少 RolePermissionModel 的创建、角色过滤查询测试
- [ ] `test_rbac_model.py`：缺少 UserRoleModel 的创建、用户过滤查询测试
- [ ] `test_rbac_model.py`：缺少 UserRoleModel 的级联删除行为测试（当 User 被 mock-delete 时关联角色记录是否正确处理）
- [ ] 所有 identity 测试均缺少对 `tenant_id` 隔离校验的覆盖---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_identity_model.py` | OrganizationModel + DepartmentModel 单元测试（含租户隔离验证） |
| `tests/unit/test_rbac_model.py` | RolePermissionModel + UserRoleModel + 级联行为单元测试 |
| TBD - 待确认（来自 #428）：`src/db/models/organization.py` | 组织 ORM 模型定义 |
| TBD - 待确认（来自 #428）：`src/db/models/department.py` | 部门 ORM 模型定义 |
| TBD - 待确认（来自 #428）：`src/db/models/role_permission.py` | 角色-权限关联 ORM 模型定义 |
| TBD - 待确认（来自 #428）：`src/db/models/user_role.py` | 用户-角色关联 ORM 模型定义 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/unit/conftest.py`](../../tests/unit/conftest.py) | 新增 `make_organization_handler`、`make_department_handler`、`make_role_permission_handler`、`make_user_role_handler` 四个 mock SQL handler（如 Issue #428 已提供则跳过） |

### 3.3 新增能力

- **Service method**：`IdentityService.create_organization`、`get_organization`、`list_departments`、`assign_role`、`list_user_roles`（确认具体签名后填写）
- **Unit test 文件**：`tests/unit/test_identity_model.py`（≥ 6 个测试用例）
- **Unit test 文件**：`tests/unit/test_rbac_model.py`（≥ 6 个测试用例，含 cascade 测试）
- **Mock handler**：4 个 SQLAlchemy handler 供单元测试复用

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选单元测试（Mock）不选集成测试（Real DB）**：identity 模型测试不依赖 DB fixture，测试执行时间从秒级提升到毫秒级，可在 CI unit stage覆盖；集成测试仅在 PR合并阶段跑。
- **复用 conftest.py handler 而非每个测试文件独立 mock**：参考 `test_tenant_model.py` 和 `test_user_model.py` 的模式，统一在 conftest.py 中维护 SQL handler，避免测试间 mock逻辑不一致。

### 4.2 版本约束

无新增外部依赖，沿用现有版本。

### 4.3 兼容性约束

- 多租户：每个 SELECT / INSERT 查询必须 `WHERE tenant_id = :tenant_id`；测试必须覆盖跨租户隔离（Tenant A 查不到 Tenant B 的数据）
- Service错误抛出 `AppException` 子类，测试用 `pytest.raises()` 验证
- 所有 mock handler 必须使用 `AsyncSession` 类型签名，与生产代码一致

### 4.4 已知坑

1. **SQLAlchemy handler 返回值类型不匹配** → 规避：严格按 `test_tenant_model.py` 中 `MockRow` 的字段结构返回 dict，确保每个 `result.scalar_one_or_none()` / `result.scalars().all()` 能正确解包
2. **`tenant_id` 过滤缺失（最常见遗漏）** → 规避：每个查询测试必须包含"本租户数据能查到、另一租户数据查不到"两个断言

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 Issue #428 产物并补充 conftest.py mock handler

确认 Issue #428 生成的 ORM 模型文件及 Service 方法签名，并检查 `tests/unit/conftest.py` 是否已有所需 handler。

操作：

**完成判定**：`PYTHONPATH=src python -c "from db.models.organization import OrganizationModel; from db.models.department import DepartmentModel; from db.models.role_permission import RolePermissionModel; from db.models.user_role import UserRoleModel; print('all OK')"` exit 0
+`ruff check tests/unit/conftest.py` exit 0

---

### Step 2: 编写 `tests/unit/test_identity_model.py`

参照 `test_tenant_model.py` 的 Class-based风格，新增 OrganizationModel + DepartmentModel 测试类。

操作：

在 `tests/unit/test_identity_model.py` 中实现：

```python
# tests/unit/test_identity_model.py
import pytest
from tests.unit.conftest import make_mock_session, MockState

# 如 Issue #428 已在 conftest.py 提供 handler，按以下模式使用：
# from tests.unit.conftest import make_organization_handler, make_department_handler

class TestOrganizationModel:
    @pytest.fixture
    def mock_db_session(self):
        state = MockState()
        # 如已有 make_organization_handler(state)
        return make_mock_session([make_organization_handler(state)])

    @pytest.fixture
    def identity_service(self, mock_db_session):
        return IdentityService(mock_db_session)  # 确认Issue#428的服务类名

    async def test_create_organization(self, identity_service):
        org = await identity_service.create_organization(
            name="Acme Corp", tenant_id=1        )
        assert org.name == "Acme Corp"
        assert org.tenant_id == 1

    async def test_get_organization_tenant_isolation(self, identity_service):
        # Tenant A 创建的组织，Tenant B 查询时返回 None 或抛出 NotFoundException
        org_a = await identity_service.create_organization(
            name="TenantA Org", tenant_id=1
        )
        with pytest.raises(NotFoundException):
            await identity_service.get_organization(org_a.id, tenant_id=2)

    async def test_list_organizations_pagination(self, identity_service):
        for name in ["A", "B", "C"]:
            await identity_service.create_organization(name=name, tenant_id=1)
        items, total = await identity_service.list_organizations(tenant_id=1, page=1, page_size=2)
        assert len(items) == 2
        assert total >= 3

class TestDepartmentModel:
    # 同理：test_create_department、test_get_department_tenant_isolation、
    # test_list_departments_pagination
    pass
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_identity_model.py -v` → 全 passed

---

### Step 3: 编写 `tests/unit/test_rbac_model.py`

参照 `test_user_model.py` 的风格，新增 RolePermissionModel + UserRoleModel + cascade 测试。

操作：

在 `tests/unit/test_rbac_model.py` 中实现：

```python
# tests/unit/test_rbac_model.py
import pytest
from tests.unit.conftest import make_mock_session, MockState
from pkg.errors.app_exceptions import NotFoundException, ValidationException

class TestRolePermissionModel:
    @pytest.fixture
    def mock_db_session(self):
        state = MockState()
        return make_mock_session([make_role_permission_handler(state)])

    @pytest.fixture
    def rbac_service(self, mock_db_session):
        return RBACService(mock_db_session)  # 确认Issue#428的服务类名

    async def test_create_role_permission(self, rbac_service):
        rp = await rbac_service.create_role_permission(
            role_id=1, permission="campaign:read", tenant_id=1
        )
        assert rp.role_id == 1
        assert rp.permission == "campaign:read"

    async def test_list_permissions_by_role(self, rbac_service):
        await rbac_service.create_role_permission(role_id=1, permission="x", tenant_id=1)
        await rbac_service.create_role_permission(role_id=1, permission="y", tenant_id=1)
        items, total = await rbac_service.list_permissions_by_role(role_id=1, tenant_id=1)
        assert total == 2

class TestUserRoleModel:
    @pytest.fixture
    def mock_db_session(self):
        state = MockState()
        return make_mock_session([make_user_role_handler(state)])

    @pytest.fixture
    def rbac_service(self, mock_db_session):
        return RBACService(mock_db_session)

    async def test_assign_role_to_user(self, rbac_service):
        ur = await rbac_service.assign_role(user_id=10, role_id=1, tenant_id=1)
        assert ur.user_id == 10
        assert ur.role_id == 1

    async def test_user_role_tenant_isolation(self, rbac_service):
        ur = await rbac_service.assign_role(user_id=10, role_id=1, tenant_id=1)
        with pytest.raises(NotFoundException):
            await rbac_service.get_user_role(ur.id, tenant_id=2)

    async def test_user_role_cascade_on_user_delete(self, rbac_service):
        # Mock：user deletion 触发关联 user_role 清理由 service 层处理
        #验证：当 User 被标记删除时，list_user_roles 返回空
        await rbac_service.assign_role(user_id=99, role_id=1, tenant_id=1)
        await rbac_service.mark_user_deleted(user_id=99, tenant_id=1)
        items, _ = await rbac_service.list_user_roles(user_id=99, tenant_id=1)
        assert len(items) == 0
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_rbac_model.py -v` → 全 passed

---

### Step 4: 全量单元测试回归 + lint操作：

```bash
PYTHONPATH=src ruff check src/db/models/organization.py src/db/models/department.py src/db/models/role_permission.py src/db/models/user_role.py tests/unit/test_identity_model.py tests/unit/test_rbac_model.py
PYTHONPATH=src pytest tests/unit/ -v
```

**完成判定**：两命令均 exit 0，无 test failures---

## 6. 验收

- [ ] `ruff check tests/unit/test_identity_model.py tests/unit/test_rbac_model.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_identity_model.py -v` → OrganizationModel + DepartmentModel 全部 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_rbac_model.py -v` → RolePermissionModel + UserRoleModel + cascade 全部 passed
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → **全 passed**（回归保证，不破坏已有测试）
- [ ]租户隔离验证：每个模型至少有一个测试断言 Tenant A 无法读 Tenant B 的数据---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Issue #428 未完成导致 IdentityService / ORM 模型尚不存在，测试无法运行 | 中 | 中 | 阻塞本板块直至 #428 合入；本板块基于 #428 的最终产物编写 |
| Mock handler 与生产 Service SQL 对不上（字段名差异） | 低 | 高 | 通过 `PYTHONPATH=src mypy src/services/*identity*.py` 交叉验证字段名；如有不符在 handler 中对齐 |
| 新增测试引入已有测试的 flake 或 mock冲突 | 低 | 低 | 单独运行 `pytest tests/unit/test_identity_model.py -v` 和 `pytest tests/unit/test_rbac_model.py -v` 定位；必要时将新 Fixtures 隔离到独立 conftest |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_identity_model.py tests/unit/test_rbac_model.py tests/unit/conftest.py
git commit -m "test(unit): add identity & RBAC model unit tests"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#429): unit tests for identity & RBAC models" --body "Closes #429"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_tenant_model.py`](../../tests/unit/test_tenant_model.py)
- 同类参考实现：[`tests/unit/test_user_model.py`](../../tests/unit/test_user_model.py)
- 依赖 Issue /关联：#428（板① —补充 Identity 系列 ORM 模型与关系定义）、#270（父 issue）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
