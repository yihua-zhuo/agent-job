# 测试引擎 · 补全 test_engine.py 单元测试覆盖

| 元数据 | 值 |
|---|---|
| Issue | #739 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | TBD - 待验证：对应 #738 的 workflow engine 核心实现文档路径 |
| 启用后赋能 | TBD - 待验证：对应 DAG evaluation router 文档路径，无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `workflow_engine` 模块缺少单元测试覆盖。graph topological sort 是核心业务逻辑，一旦排序错误（如 diamond DAG 顺序错误、循环未检测）会直接导致工作流执行顺序错误，影响所有下游功能。当前无测试保护，无法在重构或新增图节点时及时发现回归。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层测试补充
- **开发者视角**：`tests/unit/test_engine.py` 覆盖 linear/diamond/cycle/empty 四种图结构，提供 ≥ 4 个可独立运行的 pytest case；CI 流水线对 engine 改动有回归保护

### 1.3 不做什么（剔除）

- [ ] 不修改 `src/services/workflow_engine.py` 源码（仅写测试）
- [ ] 不使用真实数据库（全部使用 MockSession inline mock）
- [ ] 不覆盖 router 层端到端（如 `POST /workflows/execute`）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_engine.py -v` → ≥ 4 passed
- `ruff check src/services/workflow_engine.py tests/unit/test_engine.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/workflow_engine.py` L? — 需确认 engine 模块路径及 `WorkflowEngine` 类签名（含 `execute_topological_sort` / `detect_cycle` 等方法）

```python
# 预期结构（待 #738 落地后确认）
class WorkflowEngine:
    async def execute_topological_sort(
        self, session: AsyncSession, workflow_id: int, tenant_id: int
    ) -> list[WorkflowStepModel]: ...
```

### 2.2 涉及文件清单

- 要改：
  - `tests/unit/test_engine.py` — 新增测试文件（4 个 case）
- 要建：
  - `tests/unit/test_engine.py` — 覆盖 linear/diamond/cycle/empty 四种场景

### 2.3 缺什么

- [ ] `tests/unit/test_engine.py` 文件不存在，无任何 engine 相关测试
- [ ] `WorkflowEngine.execute_topological_sort` 方法缺少对 edge case（cycle/empty）的回归测试
- [ ] diamond DAG 拓扑排序结果不唯一，缺少对"任意有效顺序"的断言覆盖

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_engine.py` | workflow_engine 单元测试，4 个 case 覆盖 linear/diamond/cycle/empty |

### 3.2 修改文件

（无现有文件修改）

### 3.3 新增能力

- **Test case**：`test_linear_dag_order` — 线性链 A→B→C 产出 [A, B, C]
- **Test case**：`test_diamond_dag_order` — 菱形 A→{B,C}→D 产出任意有效拓扑序
- **Test case**：`test_cycle_raises_validation_exception` — 循环图 A→B→C→A 抛出 `ValidationException` 且 message 含 'cycle'
- **Test case**：`test_empty_workflow_returns_empty_list` — 空工作流返回 []

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 inline MockSession 而非 fixture**：`WorkflowEngine` 依赖 `session` 参数，inline mock 避免 fixture 隐式共享状态，让每个 case 完全独立
- **用 `ValidationException` 而非 `ValueError`**：engine 属于 service 层，错误必须抛 `AppException` 子类以匹配全局异常处理器

### 4.2 版本约束

（无新增依赖）

### 4.3 兼容性约束

- `WorkflowEngine.__init__(session: AsyncSession)` — session 不可为 None，mock 须真实返回 AsyncSession 实例
- 测试中不调用 `.to_dict()` — engine 返回 ORM 对象，router 负责序列化
- cycle 检测异常 message 必须含 'cycle' substring（case 断言匹配）

### 4.4 已知坑

1. **diamond DAG 拓扑序不唯一** → 规避：断言用 `set(sorted(result)) == set(expected_nodes)` 而非逐位相等
2. **MockSession handler 的 async iterator 返回** → 规避：使用 `AsyncIterator` mock（`async def generator()` yield），不要用普通 `list` 冒充

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 tests/unit/test_engine.py，定义 mock session 和 fixture

在 `tests/unit/test_engine.py` 顶部完成：
- import `pytest`, `AsyncSession`, `ValidationException`
- import `WorkflowEngine` 从 `src.services.workflow_engine`
- 定义 `MockState`（step auto-increment id）和 mock handler 集合
- 定义 `make_mock_session(handlers)` 构建 AsyncSession mock
- 4 个 fixture：分别返回 linear/diamond/cycle/empty 场景的 mock session

**完成判定**：`ls tests/unit/test_engine.py` 文件存在 / `ruff check tests/unit/test_engine.py` exit 0

---

### Step 2: 实现 test_linear_dag_order — 线性链 A→B→C

setup：mock session 返回 steps 列表 `[{id:1, name:'A', next_step_ids:[2]}, {id:2, name:'B', next_step_ids:[3]}, {id:3, name:'C', next_step_ids:[]}]`

```python
async def test_linear_dag_order(mock_linear_session):
    engine = WorkflowEngine(mock_linear_session)
    result = await engine.execute_topological_sort(workflow_id=1, tenant_id=1)
    names = [s.name for s in result]
    assert names == ["A", "B", "C"], f"expected [A,B,C] got {names}"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_engine.py::test_linear_dag_order -v` → 1 passed

---

### Step 3: 实现 test_diamond_dag_order — 菱形 A→{B,C}→D

setup：mock session 返回 steps `[{id:1, name:'A', next:[2,3]}, {id:2, name:'B', next:[4]}, {id:3, name:'C', next:[4]}, {id:4, name:'D', next:[]}]`

```python
async def test_diamond_dag_order(mock_diamond_session):
    engine = WorkflowEngine(mock_diamond_session)
    result = await engine.execute_topological_sort(workflow_id=1, tenant_id=1)
    names = {s.name for s in result}
    assert names == {"A", "B", "C", "D"}, f"expected {{A,B,C,D}} got {names}"
    # A must come before both B and C
    name_map = {s.name: s for s in result}
    a_idx = result.index(name_map["A"])
    b_idx = result.index(name_map["B"])
    c_idx = result.index(name_map["C"])
    assert a_idx < b_idx and a_idx < c_idx, "A must precede B and C"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_engine.py::test_diamond_dag_order -v` → 1 passed

---

### Step 4: 实现 test_cycle_raises_validation_exception — 循环图检测

setup：mock session 返回 cycle steps `[{id:1, name:'A', next:[2]}, {id:2, name:'B', next:[3]}, {id:3, name:'C', next:[1]}]`

```python
async def test_cycle_raises_validation_exception(mock_cycle_session):
    engine = WorkflowEngine(mock_cycle_session)
    with pytest.raises(ValidationException) as exc_info:
        await engine.execute_topological_sort(workflow_id=1, tenant_id=1)
    assert "cycle" in str(exc_info.value).lower(), f"expected 'cycle' in message, got: {exc_info.value}"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_engine.py::test_cycle_raises_validation_exception -v` → 1 passed

---

### Step 5: 实现 test_empty_workflow_returns_empty_list — 空工作流

setup：mock session 返回空 steps list

```python
async def test_empty_workflow_returns_empty_list(mock_empty_session):
    engine = WorkflowEngine(mock_empty_session)
    result = await engine.execute_topological_sort(workflow_id=1, tenant_id=1)
    assert result == [], f"expected [] got {result}"
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_engine.py::test_empty_workflow_returns_empty_list -v` → 1 passed

---

### Step 6: 运行全量测试 + lint

```bash
PYTHONPATH=src pytest tests/unit/test_engine.py -v
ruff check tests/unit/test_engine.py
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_engine.py -v` → `4 passed` 且 `ruff check tests/unit/test_engine.py` exit 0

---

## 6. 验收

- [ ] `ruff check tests/unit/test_engine.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_engine.py::test_linear_dag_order -v` → 1 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_engine.py::test_diamond_dag_order -v` → 1 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_engine.py::test_cycle_raises_validation_exception -v` → 1 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_engine.py::test_empty_workflow_returns_empty_list -v` → 1 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_engine.py -v` → `4 passed`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `WorkflowEngine` 方法签名与假设不符（无 `execute_topological_sort` 方法） | 低 | 高 | 调整测试方法名与签名，依赖 #738 落地后确认接口 |
| mock session handler 语法错误导致 `AttributeError` | 低 | 中 | 复用 `tests/unit/conftest.py` 中 `make_mock_session` 工具函数 |
| diamond 测试随机序导致索引判断不稳定 | 低 | 中 | 改用 set 成员断言 + 仅验证 A 先于 B/C（已反映在 Step 3） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_engine.py
git commit -m "test(engine): add test_engine.py unit tests — linear/diamond/cycle/empty"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(engine): add test_engine.py unit tests" --body "Closes #739

## Test plan
- `PYTHONPATH=src pytest tests/unit/test_engine.py -v` → 4 passed
- `ruff check tests/unit/test_engine.py` → 0 errors"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — MockState / make_mock_session 工具函数
- 父 issue：#517
- 依赖 issue：#738

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-30 | 创建 | TBD |
