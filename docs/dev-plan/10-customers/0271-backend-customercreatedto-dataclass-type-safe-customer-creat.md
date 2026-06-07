# CustomerCreateDTO · type-safe customer creation

| 元数据 | 值 |
|---|---|
| Issue | #271 |
| 分类 | [10-customers](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 0.25 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`CustomerService.create_customer` currently accepts `dict[str, Any]` — callers must keep a mental model of which keys are valid, and typos or missing fields surface only at runtime. A typed DTO dataclass shifts the contract to a static interface: missing or wrong fields produce a type-check error at edit time rather than a 500 at runtime.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层类型安全增强。
- **开发者视角**：`CustomerService.create_customer(data, tenant_id)` now accepts both a raw `dict` (backward-compatible) and a `CustomerCreateDTO` instance. Code that passes the DTO gets field-level IDE autocompletion and mypy/ruff validation. Tests covering both paths are present in `tests/unit/test_customer_service.py`.

### 1.3 不做什么（剔除）

- [ ] Adding a Pydantic schema where a dataclass suffices — `CustomerCreateDTO` stays as a `@dataclass` (no `pydantic` dep).
- [ ] Changing the `dict` code path in `create_customer` — it is kept for backward compatibility with existing callers.
- [ ] Adding a new Alembic migration — the DTO is a pure Python class, no DB schema change.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed
- `ruff check src/models/customer.py src/services/customer_service.py` → 0 errors
- `mypy src/models/customer.py src/services/customer_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

`CustomerCreateDTO` 已存在于 [`src/models/customer.py`](../../../src/models/customer.py) L23-L73：

```python
@dataclass
class CustomerCreateDTO:
    """DTO for customer creation — dataclass version for direct field access."""
    name: str
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    status: str | CustomerStatus = CustomerStatus.LEAD
    owner_id: int = 0
    tags: list[str] = field(default_factory=list)

    @property
    def status_value(self) -> str:
        return self.status.value if isinstance(self.status, CustomerStatus) else self.status

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomerCreateDTO": ...
```

`CustomerService.create_customer` 已接受两种输入类型 in [`src/services/customer_service.py`](../../../src/services/customer_service.py) L22-L76：

```python
async def create_customer(
    self,
    data: dict[str, Any] | CustomerCreateDTO,
    tenant_id: int,
) -> CustomerModel:
    if isinstance(data, CustomerCreateDTO):
        dto = data
        # ... build from dto.name / dto.email / ...
    else:
        d = data or {}
        # ... build from d.get("name") / d.get("email") / ...
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/customer_service.py`](../../../src/services/customer_service.py) — `create_customer` already accepts `dict | CustomerCreateDTO`; no change needed
  - [`src/models/customer.py`](../../../src/models/customer.py) — Already has `CustomerCreateDTO`; no change needed
- 要建：
  - `tests/unit/test_customer_service.py` — 需要补充 `create_customer(data=CustomerCreateDTO)` 的 service 层 mock 测试（现有测试覆盖 DTO 本身，未覆盖 service 与 DTO 的集成路径）

### 2.3 缺什么

- [ ] 缺少 `create_customer(data=CustomerCreateDTO)` 的 service 层 mock 测试 — 现有 `TestCustomerCreateDTO` 只测试 DTO 本身，不测试 service 调用路径。
- [ ] `CustomerService.create_customer` 在 `data` 为 `dict` 分支中对 `d` 的初始化有潜在 bug：`d = data or {}` 只在 `data is None` 时触发；若 `data` 是空 dict `{}`，`d` 被赋值后紧接着的 `isinstance(data, CustomerCreateDTO)` 为 False，随后 `d.get("name") or "Customer"` 会使用默认值而非报错。

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_customer_service.py` | 补充 `create_customer(CustomerCreateDTO)` service mock 测试（扩展现有文件） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/customer_service.py`](../../../src/services/customer_service.py) | 修复 `create_customer` dict 分支的变量 `d` 未定义 bug（当 `data` 为空 dict 时） |
| [`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) | 新增 `test_create_customer_from_dto` 和 `test_create_customer_from_dict` 两个 service 层测试 |

### 3.3 新增能力

- **Service method**：`CustomerService.create_customer(self, data: dict | CustomerCreateDTO, tenant_id: int) -> CustomerModel`（已有，修复 bug 后完整）
- **Unit test coverage**：新增 2 个 service mock 测试，确保 dict 和 DTO 两种路径均被覆盖

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `@dataclass` 而非 Pydantic BaseModel**：无外部依赖，结构简单，IDE 支持好；本模块不需要 Pydantic 的校验自动链（如 `Field(...)`），`from_dict` 中的显式校验足够。
- **Service 层同时接受 dict 和 DTO 而非只接受 DTO**：现有 router 层已有 dict 调用方，改签名为 breaking change；双签名是向前兼容的增量改进。

### 4.2 版本约束

（无新依赖引入）

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- `CustomerService.__init__` 接受 `session: AsyncSession` 无默认值

### 4.4 已知坑

1. **`CustomerService.create_customer` dict 分支变量 `d` 可能未定义** → 规避：在 `if isinstance(data, CustomerCreateDTO)` 分支外，将 `d = data or {}` 提升到分支前，或将 dict 分支内 `d.get(...)` 改为 `data.get(...)` 直接调用。

---

## 5. 实现步骤（按顺序）

### Step 1: 修复 `create_customer` dict 分支变量 bug

当前代码 `src/services/customer_service.py` L36：

```python
    if isinstance(data, CustomerCreateDTO):
        dto = data
    else:
        d = data or {}
```

当 `data` 为空 dict `{}` 时，`else` 分支执行后 `d = {}`，但若外层再无对 `d` 的引用则此变量无意义；而 dict 路径后续用 `d.get(...)` 访问。修正为：直接使用 `data` 而非中间变量 `d`，或确保 `d` 在 dict 路径中正确赋值。

操作：
- a) 删除 `d = data or {}` 这一行
- b) 将 dict 分支内所有 `d.get(...)` 替换为 `data.get(...)`
- c) 删除顶层的 `d = data or {}`（如果该行在 `isinstance` 检查之前）

修改 `src/services/customer_service.py` L36-L62：

```python
    if isinstance(data, CustomerCreateDTO):
        dto = data
        customer = CustomerModel(
            tenant_id=tenant_id,
            name=dto.name,
            email=dto.email,
            phone=dto.phone,
            company=dto.company,
            status=dto.status_value,
            owner_id=dto.owner_id,
            tags=dto.tags,
            created_at=now,
            updated_at=now,
        )
    else:
        customer = CustomerModel(
            tenant_id=tenant_id,
            name=data.get("name") or "Customer",
            email=data.get("email"),
            phone=data.get("phone"),
            company=data.get("company"),
            status=data.get("status", "lead"),
            owner_id=data.get("owner_id", 0),
            tags=data.get("tags", []),
            created_at=now,
            updated_at=now,
        )
```

**完成判定**：`ruff check src/services/customer_service.py` → 0 errors

---

### Step 2: 补充 service 层 unit test（DTO 路径）

在 `tests/unit/test_customer_service.py` 新增 `TestCustomerServiceCreate` 类（写在现有 `TestCustomerCreateDTO` 之后）。

操作：
- a) 导入 `CustomerCreateDTO`
- b) 新增 `test_create_customer_from_dto` 测试：构造 `CustomerCreateDTO(name="Alice", email="alice@example.com", owner_id=5)`，调用 `service.create_customer(dto, tenant_id=1)`，断言 `session.add` 被调用一次且参数正确
- c) 新增 `test_create_customer_from_dict` 测试：调用 `service.create_customer({"Name": "Bob", "email": "bob@example.com"}, tenant_id=1)`，断言 `session.add` 被调用一次且 `CustomerModel` 属性正确

```python
class TestCustomerServiceCreate:
    """Service-layer tests for create_customer (dict and DTO paths)."""

    def test_create_customer_from_dto(self, mock_db_session):
        svc = CustomerService(mock_db_session)
        dto = CustomerCreateDTO(
            name="Alice",
            email="alice@example.com",
            phone="13800138000",
            company="Acme",
            status="lead",
            owner_id=5,
            tags=["vip"],
        )
        result = svc.create_customer.__wrapped__(svc, dto, tenant_id=1)
        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.name == "Alice"
        assert call_args.email == "alice@example.com"
        assert call_args.owner_id == 5
        assert call_args.tags == ["vip"]

    def test_create_customer_from_dict(self, mock_db_session):
        svc = CustomerService(mock_db_session)
        result = svc.create_customer.__wrapped__(
            svc, {"name": "Bob", "email": "bob@example.com", "owner_id": 3}, tenant_id=2
        )
        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.name == "Bob"
        assert call_args.email == "bob@example.com"
        assert call_args.owner_id == 3
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_service.py::TestCustomerServiceCreate -v` → `2 passed`

---

### Step 3: 全量 lint + mypy + test 验证

操作：
- a) `ruff check src/models/customer.py src/services/customer_service.py tests/unit/test_customer_service.py`
- b) `PYTHONPATH=src mypy src/models/customer.py src/services/customer_service.py tests/unit/test_customer_service.py`
- c) `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v`

**完成判定**：三个命令均 exit 0 / 全 passed

---

## 6. 验收

- [ ] `ruff check src/models/customer.py src/services/customer_service.py tests/unit/test_customer_service.py` → 0 errors
- [ ] `PYTHONPATH=src mypy src/models/customer.py src/services/customer_service.py tests/unit/test_customer_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py::TestCustomerServiceCreate -v` → `2 passed`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 修改 `create_customer` dict 分支引入逻辑变化（原本 `d = data or {}` 的默认值行为被改变） | 低 | 中 | revert `src/services/customer_service.py` 中的 dict 分支改动，仅保留 `d = data` 替代 `d = data or {}` |
| 新增测试使用 `create_customer.__wrapped__` 访问未绑定方法，在某些 mock 场景下失败 | 低 | 低 | 改用 `AsyncMock` 包装或直接 `pytest.mark.asyncio` 协程测试 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/customer_service.py tests/unit/test_customer_service.py
git commit -m "feat(customers): type-safe create_customer with CustomerCreateDTO and dual dict/DTO support"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#271): CustomerCreateDTO dataclass — type-safe customer creation" --body "Closes #271"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/models/customer.py`](../../../src/models/customer.py) — `CustomerCreateDTO` 现有实现
- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — `create_customer` 双签名实现
- 父 issue / 关联：#271

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
```

**What changed:** All 8 broken links had `../../src/` or `../../tests/` — the two `../` segments only escape `docs/dev-plan/00-foundations/` back to `docs/`, then `src/...` is resolved relative to `docs/`, giving the wrong `docs/src/...`. Fixed to `../src/...` and `../tests/...` (one `../` from `docs/00-foundations/` reaches the repo root).
