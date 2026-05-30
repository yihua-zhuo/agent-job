# test 层 · 更新 test_customer_service.py 的 mock 层以支持 CustomerRepository

| 元数据 | 值 |
|---|---|
| Issue | #432 |
| 分类 | 99-misc |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`tests/unit/test_customer_service.py` currently uses a `mock_db_session` fixture that is missing a `CustomerRepository`-level mock handler. When `CustomerService` calls downstream `CustomerRepository` methods (e.g., `find_by_id`, `list_by_tenant`), those calls fall through to unhandled SQLexecute calls, causing test failures or incorrect return values. Adding a `make_customer_repository_handler(state)` to `conftest.py` (following the established pattern of `make_customer_handler` and `make_user_handler`) provides consistent, stateful mocking for all repository operations.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯测试基础设施。
- **开发者视角**：`test_customer_service.py` 中的所有现有测试无需改动断言或调用方式，只需在 fixture 中加入新的 handler。所有测试通过（exit 0）。

### 1.3 不做什么（剔除）

- [ ] 不实现真实的 `CustomerRepository` class — 仅扩展 mock layer
- [ ] 不修改 `CustomerService` 业务逻辑或 SQL 查询
- [ ] 不新增 API endpoint 或 ORM model

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed（所有现有 case 不变）
- `ruff check tests/unit/test_customer_service.py tests/unit/conftest.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`tests/unit/test_customer_service.py` — 现有 fixture 中 `make_customer_handler` 等 handlers 已注册，但缺少 repository 级别 handler

TBD - 待验证：`tests/unit/conftest.py` L? — 现有 `make_customer_handler(state)` / `make_user_handler(state)` 签名与实现（用于参考新 handler 格式）

### 2.2 涉及文件清单

- 要改：
  - [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — 新增 `make_customer_repository_handler(state)` 函数
  - [`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — 在 `mock_db_session` fixture 中加入该 handler
- 要建：无

### 2.3 缺什么

- [ ] `tests/unit/conftest.py` 中无 `make_customer_repository_handler` — repository 层调用无法被 mock，导致部分 test case 失败或行为不正确
- [ ] `mock_db_session` fixture 中未注册 repository handler — 即使添加了 handler，fixture 也不包含它

---

## 3. 目标产物（终点）

### 3.1 新文件

（无新建文件）

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) | 新增 `make_customer_repository_handler(state)` — 参照现有 `make_customer_handler` / `make_user_handler` 模式，提供 INSERT / UPDATE / DELETE / SELECT / COUNT handlers，注册至 `make_mock_session` |
| [`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) | 在 `mock_db_session` fixture 的 `handlers` 列表中追加 `make_customer_repository_handler(state)` 调用 |

### 3.3 新增能力

- **Test fixture helper**：`make_customer_repository_handler(state) -> Handler` in `tests/unit/conftest.py`
- **Mock state**：repository 层数据（`CustomerRepository` 查询结果）纳入 `MockState`，支持跨-test 独立隔离

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **复用现有 handler 模式而非新建适配器**：本 repo 的 `conftest.py` 已有 `make_customer_handler`、`make_user_handler`、`make_count_handler` 等。`make_customer_repository_handler` 遵循完全相同的工厂函数签名 `(state) -> Handler`，保持一致性，降低学习成本。
- **stateful 而非 stateless mock**：handler 需要 `MockState` 以支持跨-test 独立（`MockState` 每次 fixture 调用时 fresh 构造），防止测试间数据泄露。

### 4.2 版本约束

（无新依赖）

### 4.3 兼容性约束

- 多租户：mock handler 中的 SELECT 查询必须过滤 `tenant_id`（与生产代码一致）
- `MockState` 由调用方（test fixture）构造并传入，handler 内部不直接引用全局状态
- handler 返回值须匹配 `MockRow` / `MockResult` 格式（`tests/unit/conftest.py` 中定义）

### 4.4 已知坑

1. **repository handler 与 customer handler 可能操作同一张表** → 规避：`make_customer_repository_handler` 聚焦 repository 接口层（如 `find_by_id`、`list_by_tenant`），不直接操作底层 `customers` 表 state slot；或者与 `make_customer_handler` 共用同一 state slot 以保证数据一致
2. **MockResult.scalar_one_or_none 返回 None 而非 MockRow** → 规避：handler 的 SELECT 查询结果须用 `MockRow` 构造，而非直接返回 dict

---

## 5. 实现步骤（按顺序）

### Step 1: 在 conftest.py 添加 make_customer_repository_handler(state)

在 `tests/unit/conftest.py` 中仿照现有 handler 工厂函数格式，新增 `make_customer_repository_handler`。

参考已有模式：

```python
def make_customer_repository_handler(state: MockState) -> Handler:
    def handle(method: str, stmt, params: dict):
        if method == "insert":
            ...
        elif method == "select":
            ...
        ...
    return handle
```

具体 SELECT filters（`tenant_id` 等）须与 `CustomerRepository` 实际查询一致。TBD - 待验证：`CustomerRepository` 各方法的查询条件与返回值格式。

**完成判定**：`ruff check tests/unit/conftest.py` → 0 errors

### Step 2: 在 test_customer_service.py 的 mock_db_session fixture 中注册新 handler

在 `tests/unit/test_customer_service.py` 的 `mock_db_session` fixture 中，将 `make_customer_repository_handler(state)` 追加至 `handlers` 列表：

```python
@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([
        make_customer_handler(state),
        make_count_handler(state),
        make_customer_repository_handler(state),  # ← 新增
    ])
```

**完成判定**：`ruff check tests/unit/test_customer_service.py` → 0 errors

### Step 3: 运行全量 unit test 验证

执行 `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v`，确认所有现有测试 case passed，不修改任何断言或调用。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check tests/unit/test_customer_service.py tests/unit/conftest.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → 无新增 failure

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| repository handler 查询条件与实际 `CustomerRepository` 不一致，导致 mock 返回错误数据 | 低 | 中 | 回退 Step 1-2，仅保留原有 handler；新增 handler 待 `CustomerRepository` 接口确认后再加 |
| 新 handler 注册顺序导致与其他 handler 冲突（如同一 state slot 被双重写入） | 低 | 低 | 调整 handlers 列表顺序，确保 repository handler 与 customer handler 操作不同 state slot 或共用同一 slot 时顺序正确 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_customer_service.py tests/unit/conftest.py
git commit -m "test: add customer_repository handler to mock_db_session fixture"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test: update mocks for CustomerRepository in test_customer_service.py" --body "Closes #432"
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — 现有 `make_customer_handler`、`make_user_handler`、`make_count_handler` 工厂函数
- 父 issue / 关联：#252（父）, #431（依赖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
