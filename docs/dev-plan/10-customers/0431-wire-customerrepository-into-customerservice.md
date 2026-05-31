# 客户 · Wire CustomerRepository into CustomerService

| 元数据 | 值 |
|---|---|
| Issue | #431 |
| 分类 | 10-customers |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [创建 CustomerRepository（#430）](0430-create-src-db-repositories-customer-py-with-customerreposito.md) |
| 启用后赋能 | [实现客户功能 Service 层](../99-misc/0432-update-test-customer-service-py-mocks-for-customerrepository.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CustomerService currently calls `self.session.execute(...)` directly throughout its methods. This couples the service layer to SQLAlchemy query mechanics, making the code harder to unit-test and blocking the repository abstraction established in #430. Without wiring the repository in, the refactoring in #430 is incomplete and downstream code cannot consume CustomerService without also coupling to the async session.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层重构
- **开发者视角**：`CustomerService` now accepts a `CustomerRepository` instance via `__init__`. All DB access is delegated to the repository, keeping query logic in one place. Validation (status checks, DTO parsing, `to_dict`) remains in the service layer.

### 1.3 不做什么（剔除）

- [ ] Do not modify `CustomerRepository` interface or add new repository methods — #430 owns that contract
- [ ] Do not touch database schema or create migrations — no schema changes in this issue
- [ ] Do not change any API router signatures or add new endpoints

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all existing tests pass (no regression)
- `ruff check src/services/customer_service.py` → 0 errors
- All `self.session.execute(...)` calls in `CustomerService` replaced with repository method calls

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/customer_service.py` L1-L20 — 现有 `__init__` signature (是否接受 session param); 需要确认有多少处 `self.session.execute(...)` 调用

TBD - 待验证：`src/db/repositories/customer.py` L1-L10 — `CustomerRepository` 接口（由 #430 创建）；需要确认 `__init__` 签名和已有方法列表

### 2.2 涉及文件清单

- 要改：
  - `src/services/customer_service.py` — 替换 `self.session.execute(...)` → repository 方法调用
  - `tests/unit/test_customer_service.py` — 更新 mock fixture（接受 repository 而非 session）
- 要建：
  - 无新文件（本issue是纯重构）

### 2.3 缺什么

- [ ] `CustomerService.__init__` does not accept a repository argument — only a session
- [ ] Service methods call `self.session.execute(...)` directly instead of delegating to `CustomerRepository`
- [ ] Unit test mock fixtures still inject a SQLAlchemy `AsyncSession` mock into `CustomerService`

---

## 3. 目标产物（终点）

### 3.1 新文件

无新文件。

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/customer_service.py` | `__init__` 接受 `CustomerRepository`（无 default）；替换所有 `self.session.execute(...)` 为 repository 方法调用 |
| `tests/unit/test_customer_service.py` | `mock_db_session` fixture → `mock_customer_repository` fixture；所有测试使用 repository mock 而非 session mock |

### 3.3 新增能力

- **Service method**：`CustomerService.__init__(self, repository: CustomerRepository)` — no `session` param, no `None` default
- **Repository delegation**：所有 SELECT / INSERT / UPDATE / DELETE 通过 `self.repository.<method>()` 执行

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **接受 repository 不接受 session**：遵循 CLAUDE.md §Service Pattern，`__init__` 只接受 `CustomerRepository`，session 生命周期由调用方管理。选此项而非 `Optional[CustomerRepository]` 因为 #430 已建立完整 repository 接口，服务层不应降级退化。
- **保留 validation in service**：状态枚举校验 (`VALID_STATUSES`)、DTO 解析、`to_dict()` 序列化保持在 `CustomerService` 内，不下推到 repository — 职责分离，repository 只管数据访问。

### 4.2 版本约束

无新依赖。

### 4.3 兼容性约束

- 多租户：repository 层的每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()`
- 不改变任何 public method 签名（只改 `__init__` 的参数来源，内部方法调用路径变更不影响外部接口）

### 4.4 已知坑

1. **SQLAlchemy `metadata` 列名冲突** → 规避：`CustomerRepository` 模型中如需存 JSON 元数据，使用 `event_metadata` / `payload` / `meta` 而非 `metadata`，避免与 `Base.metadata` 冲突
2. **测试 mock 需要完全替换** → 规避：迁移 `test_customer_service.py` 时，将 `mock_db_session` fixture 整体替换为 `mock_customer_repository`，不再 mock `AsyncSession.execute`，改为 mock repository 方法返回值

---

## 5. 实现步骤（按顺序）

### Step 1: Update CustomerService.__init__ signature

在 `src/services/customer_service.py` 中修改 `__init__`：

```python
# 旧
def __init__(self, session: AsyncSession) -> None:
    self.session = session

# 新
def __init__(self, repository: CustomerRepository) -> None:
    self.repository = repository
```

将 `self.session` 的所有引用改为 `self.repository`。

**完成判定**：`ruff check src/services/customer_service.py` → 0 errors

### Step 2: Replace self.session.execute(...) calls with repository methods

逐个方法扫描 `src/services/customer_service.py`，将每处 `self.session.execute(...)` 替换为对应的 `self.repository.<method>(...)` 调用：

| 原调用 | 替换为 |
|--------|--------|
| `self.session.execute(select(CustomerModel).where(...))` | `self.repository.get_by_id(...)` |
| `self.session.execute(select(CustomerModel).where(...).offset(...).limit(...))` | `self.repository.list(...)` |
| `self.session.execute(insert(CustomerModel).values(...))` | `self.repository.create(...)` |
| `self.session.execute(update(CustomerModel).where(...).values(...))` | `self.repository.update(...)` |

具体替换顺序按方法在文件中的出现顺序，每换一个方法运行一次 `ruff check` 验证无新增 lint 错误。

**完成判定**：`grep -c "self.session.execute" src/services/customer_service.py` → `0`

### Step 3: Remove AsyncSession import if no longer needed

检查 `src/services/customer_service.py` 顶部 `from sqlalchemy.ext.asyncio import AsyncSession` 是否还有其他引用（注释除外）。如无，删除该 import。

**完成判定**：`ruff check src/services/customer_service.py` → 0 errors（import 删除后不应报 unused）

### Step 4: Update test fixture in test_customer_service.py

在 `tests/unit/test_customer_service.py` 中：

a) 添加 `mock_customer_repository` fixture（参考 `tests/unit/conftest.py` 的 `MockState` + `make_mock_session` 模式）：

```python
@pytest.fixture
def mock_customer_repository():
    return MockCustomerRepository()  # returns structured mock responses

@pytest.fixture
def customer_service(mock_customer_repository):
    return CustomerService(mock_customer_repository)
```

b) 每个测试方法中，将 `mock_db_session` 替换为 `mock_customer_repository`，将 assert 中的 `result.to_dict()` 对比改为直接 assert ORM 对象属性。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all pass, no `AttributeError` for `to_dict` without ORM object

### Step 5: Verify no regression on full unit test suite

```bash
PYTHONPATH=src pytest tests/unit/ -v
```

预期：无 `FAILED` 行，测试数量与修改前持平（因无功能变化，只是注入路径重构）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/ -v` → exit 0，输出包含 `N passed`

---

## 6. 验收

- [ ] `ruff check src/services/customer_service.py` → 0 errors
- [ ] `grep "self.session.execute" src/services/customer_service.py` → no output（全部替换完毕）
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → exit 0（无回归）
- [ ] `ruff check src/services/customer_service.py src/services/__init__.py` → 0 errors（如 `__init__` 签名变化影响 `__init__.py` 的 re-export）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 迁移过程中漏替换某处 `self.session.execute(...)`，导致运行时 `AttributeError`（repository 无 `execute` 属性） | 低 | 中 | 逐方法 grep 验证；若有遗漏，在该方法内临时加 `self.session = self.repository._session` 桥接，回退到 session 模式，逐步迁移 |
| `CustomerRepository` 方法签名与 `CustomerService` 调用侧不匹配（如缺少 `tenant_id` 参数） | 中 | 中 | 在 `CustomerRepository` 中补齐方法签名（#430 的实现细节）；本 issue 与 #430 串行开发，集成时会发现 |
| 测试 mock 迁移遗漏导致 `AttributeError: 'MockAsyncSession' object has no attribute 'execute'` | 低 | 低 | 回到 Step 4，重跑 `test_customer_service.py` 单独调试 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/customer_service.py tests/unit/test_customer_service.py
git commit -m "refactor(customer): wire CustomerRepository into CustomerService"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(customers): wire CustomerRepository into CustomerService (#431)" --body "Closes #431"

# 2. 更新进度
# 在本板块文档 §Changelog 表格新增一行
# PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/services/sales_service.py` — 已有 service 接受 repository 的成熟模式
- 父 issue：#252
- 依赖 issue：#430（创建 `CustomerRepository` 接口）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
