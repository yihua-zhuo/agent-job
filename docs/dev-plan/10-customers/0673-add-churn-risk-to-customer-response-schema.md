# 0673 · Add churn risk to customer response schema

| 元数据 | 值 |
|---|---|
| Issue | #673 |
| 分类 | [10-customers](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 0.25 工作日 |
| 依赖 | [TBD — issue #672 未创建](TBD) |
| 启用后赋能 | [TBD — 下游消费方待定](TBD) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The existing `Customer` dataclass in [`src/models/customer.py`](../../src/models/customer.py) L22-L93 and the `CustomerModel` ORM in [`src/db/models/customer.py`](../../src/db/models/customer.py) L40-L56 expose the core customer fields (`id`, `name`, `email`, `status`, `owner_id`, `tags`, etc.) but have no representation for churn risk data. An upstream analytics/ML pipeline (driven by issue #672) will compute a churn risk score per customer; the GET endpoints must be able to surface it without schema changes on the service/router layer.

### 1.2 做完后

- **用户视角**：`GET /api/v1/customers/{id}` and `GET /api/v1/customers` now include `churn_risk` (float, 0.0–1.0) and `churn_risk_tier` (string, one of `low` / `medium` / `high`) when those fields are present on the model. Fields are `null` when no score has been computed yet — no breaking change to existing callers.
- **开发者视角**：The `Customer` dataclass and `CustomerModel.to_dict()` both expose `churn_risk` / `churn_risk_tier`. Downstream services (analytics dashboards, automated workflows) can consume these fields from the existing endpoints.

### 1.3 不做什么（剔除）

- [ ] No new database column for `churn_risk` — storage is owned by the analytics pipeline (issue #672) which may write to a separate `customer_scores` table. This board only augments the response schema.
- [ ] No new service method or business logic — computation logic stays in the upstream board.
- [ ] No new API endpoints — existing `GET /customers` and `GET /customers/{id}` are the only touchpoints.

### 1.4 关键 KPI

- `ruff check src/models/customer.py src/db/models/customer.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_customer_model.py tests/unit/test_customers_router.py -v` → all passed (no regression)
- `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all passed (no regression)

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/models/customer.py`](../../src/models/customer.py) L22-L50

```python:src/models/customer.py
@dataclass
class Customer:
    name: str
    email: str
    owner_id: int
    id: int | None = None
    phone: str | None = None
    company: str | None = None
    status: CustomerStatus = CustomerStatus.LEAD
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "status": self.status.value if isinstance(self.status, CustomerStatus) else self.status,
            "owner_id": self.owner_id,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }
```

[`src/db/models/customer.py`](../../src/db/models/customer.py) L40-L56 — `CustomerModel.to_dict()` currently returns 12 fields, no churn risk fields.

### 2.2 涉及文件清单

- 要改：
  - [`src/models/customer.py`](../../src/models/customer.py) — add `churn_risk: float | None` and `churn_risk_tier: str | None` fields to `Customer` dataclass; update `to_dict()`
  - [`src/db/models/customer.py`](../../src/db/models/customer.py) — add `churn_risk` and `churn_risk_tier` to `CustomerModel.to_dict()`
  - [`tests/unit/test_customer_model.py`](../../tests/unit/test_customer_model.py) — add tests for new fields
  - [`tests/unit/test_customers_router.py`](../../tests/unit/test_customers_router.py) — add test coverage for `churn_risk` in GET response
- 要建：
  - 无

### 2.3 缺什么

- [ ] `Customer` dataclass has no `churn_risk` / `churn_risk_tier` fields — analytics pipeline has no schema slot to write into.
- [ ] `CustomerModel.to_dict()` does not serialize `churn_risk` / `churn_risk_tier` — GET responses always omit these fields.
- [ ] No unit test covers `churn_risk` field in customer response.

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| 无新建文件 | 本次为纯 schema 扩充，无新文件创建 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/models/customer.py`](../../src/models/customer.py) | dataclass 新增 `churn_risk: float | None = None` 和 `churn_risk_tier: str | None = None`；更新 `to_dict()` 输出这两字段 |
| [`src/db/models/customer.py`](../../src/db/models/customer.py) | `to_dict()` 返回值追加 `churn_risk` 和 `churn_risk_tier` 字段（如值为 `None` 则不出现，或显式返回 `None`） |
| [`tests/unit/test_customer_model.py`](../../tests/unit/test_customer_model.py) | 新增 `TestChurnRiskFields` 测试类：验证字段存在、to_dict 输出正确、边界值（0.0 / 1.0 / None） |
| [`tests/unit/test_customers_router.py`](../../tests/unit/test_customers_router.py) | 在 `TestGetCustomer` 中验证响应 JSON 包含 `churn_risk` 和 `churn_risk_tier` 键 |

### 3.3 新增能力

- **Dataclass fields**：`Customer.churn_risk: float | None`, `Customer.churn_risk_tier: str | None`
- **ORM serialization**：已存在的 `CustomerModel.to_dict()` 追加两字段输出
- **API response**：已存在的 `GET /api/v1/customers/{id}` → response body 包含 `churn_risk` 和 `churn_risk_tier`（无值时为 `null`）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **字段命名 `churn_risk`（浮点）与 `churn_risk_tier`（枚举字符串）**：`churn_risk` 是连续分数（0.0–1.0），`churn_risk_tier` 是 derived categorical label（`low` / `medium` / `high`），两者都暴露给 API consumer，避免 client-side duplicate computation.
- **选 `float | None` 不选 `Optional[float]`**：Python 3.10+ style, consistent with existing codebase pattern.
- **选 `str | None` for tier 不选 `Literal["low","medium","high"]`**：严格验证 tier 值应在写入端（issue #672）负责；本 schema 只负责传输，容忍 `None` 表示未评分。

### 4.2 版本约束

无新增依赖。

### 4.3 兼容性约束

- 新字段为 `| None`，所有现有调用点无破坏性变更。
- Service 层不调用 `.to_dict()`（由 router 负责），现有 `CustomerService` 方法无需修改。
- 多租户要求不变——两字段不带 tenant_id，均以 customer_id 为粒度。

### 4.4 已知坑

1. **Pydantic `Field(default=None)` 在 dataclass 中不生效** → 规避：`churn_risk: float | None = None` 直接写默认值，与 codebase 现有模式一致（如 `phone: str | None = None`）。
2. **JSON 序列化 `datetime` 时 `isoformat()` 可能抛 `AttributeError`** → 规避：已有的 `isinstance(x, datetime)` guard 已覆盖新增字段无需特殊处理。

---

## 5. 实现步骤（按顺序）

### Step 1: Add churn_risk fields to `Customer` dataclass

操作：
- a) 在 [`src/models/customer.py`](../../src/models/customer.py) 的 `Customer` dataclass 中，`updated_at` 字段声明后追加：

```python
    churn_risk: float | None = None
    churn_risk_tier: str | None = None
```

- b) 在 `to_dict()` 方法的 `return` dict 中，`"updated_at": ...` 条目后追加：

```python
            "churn_risk": self.churn_risk,
            "churn_risk_tier": self.churn_risk_tier,
```

- c) 在 `from_dict()` 方法中，解析 `updated_at` 之后追加：

```python
        churn_risk = data.get("churn_risk")
        churn_risk_tier = data.get("churn_risk_tier")
        # validate range if provided
        if churn_risk is not None and not (0.0 <= churn_risk <= 1.0):
            raise ValueError("churn_risk must be between 0.0 and 1.0")
```

- d) 在 `from_dict()` 返回的 `cls(...)` 调用中，加入 `churn_risk=churn_risk, churn_risk_tier=churn_risk_tier`。

**完成判定**：`ruff check src/models/customer.py` → 0 errors. `PYTHONPATH=src python -c "from models.customer import Customer; c = Customer(name='x', email='x@x.com', owner_id=1, churn_risk=0.75, churn_risk_tier='high'); print(c.to_dict())"` exits 0 and prints `churn_risk` and `churn_risk_tier`.

---

### Step 2: Add churn_risk fields to `CustomerModel.to_dict()`

操作：
- a) 在 [`src/db/models/customer.py`](../../src/db/models/customer.py) 的 `to_dict()` 方法中，`"updated_at": ...` 条目后追加：

```python
            "churn_risk": getattr(self, "churn_risk", None),
            "churn_risk_tier": getattr(self, "churn_risk_tier", None),
```

使用 `getattr(..., None)` 兼容已有 rows 不含新列的情况（向后兼容）。

**完成判定**：`ruff check src/db/models/customer.py` → 0 errors.

---

### Step 3: Add unit tests for churn_risk in `test_customer_model.py`

操作：
- a) 在 [`tests/unit/test_customer_model.py`](../../tests/unit/test_customer_model.py) 新增测试类：

```python
from models.customer import Customer, CustomerStatus


class TestChurnRiskFields:
    def test_churn_risk_defaults_to_none(self):
        c = Customer(name="Test", email="t@t.com", owner_id=1)
        assert c.churn_risk is None
        assert c.churn_risk_tier is None

    def test_churn_risk_set_on_construction(self):
        c = Customer(name="Test", email="t@t.com", owner_id=1,
                     churn_risk=0.42, churn_risk_tier="medium")
        assert c.churn_risk == 0.42
        assert c.churn_risk_tier == "medium"

    def test_to_dict_includes_churn_risk_fields(self):
        c = Customer(name="Test", email="t@t.com", owner_id=1,
                     churn_risk=0.8, churn_risk_tier="high")
        d = c.to_dict()
        assert "churn_risk" in d
        assert "churn_risk_tier" in d
        assert d["churn_risk"] == 0.8
        assert d["churn_risk_tier"] == "high"

    def test_to_dict_churn_risk_none_when_unset(self):
        c = Customer(name="Test", email="t@t.com", owner_id=1)
        d = c.to_dict()
        assert d["churn_risk"] is None
        assert d["churn_risk_tier"] is None

    def test_from_dict_round_trips_churn_risk(self):
        raw = {"name": "Bob", "email": "b@b.com", "owner_id": 2,
               "churn_risk": 0.3, "churn_risk_tier": "low"}
        c = Customer.from_dict(raw)
        assert c.churn_risk == 0.3
        assert c.churn_risk_tier == "low"
        assert c.to_dict()["churn_risk"] == 0.3

    def test_from_dict_rejects_churn_risk_out_of_range(self):
        raw = {"name": "Bob", "email": "b@b.com", "owner_id": 2, "churn_risk": 1.5}
        with pytest.raises(ValueError, match="churn_risk must be"):
            Customer.from_dict(raw)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_model.py -v` → `6 passed`（或实际数量，全部 passed）。

---

### Step 4: Add router tests for churn_risk in GET response

操作：
- a) 在 [`tests/unit/test_customers_router.py`](../../tests/unit/test_customers_router.py) 的 `TestGetCustomer` 类中添加：

```python
    def test_get_customer_response_includes_churn_risk_fields(self):
        # Mock a customer with churn_risk set
        mock_customer = MagicMock()
        mock_customer.id = 5
        mock_customer.tenant_id = 1
        mock_customer.name = "Churned Corp"
        mock_customer.email = "churned@example.com"
        mock_customer.phone = None
        mock_customer.company = None
        mock_customer.status = "customer"
        mock_customer.owner_id = 1
        mock_customer.tags = []
        mock_customer.assigned_at = None
        mock_customer.recycle_count = 0
        mock_customer.recycle_history = []
        mock_customer.created_at = datetime.now(UTC)
        mock_customer.updated_at = datetime.now(UTC)
        mock_customer.churn_risk = 0.88
        mock_customer.churn_risk_tier = "high"
        mock_customer.to_dict.return_value = {
            "id": 5, "tenant_id": 1, "name": "Churned Corp",
            "email": "churned@example.com", "phone": None, "company": None,
            "status": "customer", "owner_id": 1, "tags": [],
            "assigned_at": None, "recycle_count": 0, "recycle_history": [],
            "created_at": mock_customer.created_at.isoformat(),
            "updated_at": mock_customer.updated_at.isoformat(),
            "churn_risk": 0.88, "churn_risk_tier": "high",
        }
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=AsyncMock(return_value=mock_customer))
        )
        # ... use TestClient to call GET /api/v1/customers/5 with mock session ...
        response = client.get("/api/v1/customers/5")  # with mocked deps
        assert response.status_code == 200
        data = response.json()["data"]
        assert "churn_risk" in data
        assert "churn_risk_tier" in data
        assert data["churn_risk"] == 0.88
        assert data["churn_risk_tier"] == "high"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customers_router.py -v` → all passed.

---

## 6. 验收

- [ ] `ruff check src/models/customer.py src/db/models/customer.py` → 0 errors
- [ ] `ruff check tests/unit/test_customer_model.py tests/unit/test_customers_router.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_model.py -v` → all passed (no regression on existing fields)
- [ ] `PYTHONPATH=src pytest tests/unit/test_customers_router.py -v` → all passed (no regression on existing endpoints)
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → all passed (no regression on service layer)

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Issue #672 writes churn_risk to a separate table (not `customers` row) — fields always return `None` in this board's lifetime | 低 | 低 | 说明文档已在 §1.3 明确 storage 由 #672 负责；schema 正确性由本 board 保证 |
| Adding fields to `CustomerModel.to_dict()` breaks existing tests that assert exact field count | 低 | 中 | 使用 `getattr(self, "churn_risk", None)` 保证向后兼容；如测试因 field count 失败，扩展 assertion 而非移除新字段 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/models/customer.py src/db/models/customer.py tests/unit/test_customer_model.py tests/unit/test_customers_router.py
git commit -m "feat(customers): add churn_risk and churn_risk_tier fields to Customer schema"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#673): add churn_risk fields to customer response schema" --body "Closes #673"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- Dataclass pattern（已有）：[`src/models/customer.py`](../../src/models/customer.py) L22-L93
- ORM to_dict pattern（已有）：[`src/db/models/customer.py`](../../src/db/models/customer.py) L40-L56
- Unit test for dataclass：[`tests/unit/test_customer_model.py`](../../tests/unit/test_customer_model.py)
- Router test for GET endpoint：[`tests/unit/test_customers_router.py`](../../tests/unit/test_customers_router.py) L168-L176
- Parent issue / subtask：#35（父 issue）
- 依赖 issue：#672（churn risk computation — storage side）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
