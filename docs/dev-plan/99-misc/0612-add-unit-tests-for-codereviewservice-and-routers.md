# 代码审查服务与路由 · 单元测试覆盖

| 元数据 | 值 |
|---|---|
| Issue | #612 |
| 分类 | 70-platform |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [#611 板块](./../70-platform/0611-add-code-review-service.md), [无（#44 为父 issue，不阻塞本板块直接工作）] |
| 启用后赋能 | [#613集成测试板块]（本板块完成后方可接入真实 LLM） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `CodeReviewService` 和对应 router仅有手写实现，缺少自动化回归保护。LLM 返回的 review 数据结构（issues / score / summary）若因上游 Prompt变更或字段名漂移而损坏，业务层无法感知。CodeReviewService 是平台自动化流水线的核心节点，其行为必须有确定性验证。

### 1.2 做完后

- **用户视角**：无用户可见变化 —纯底层测试扩充。
- **开发者视角**：
  - `pytest tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py -v` 全 passed
  - 调用 `CodeReviewService.review(pr_id, tenant_id)` 能断言返回结构 `{issues: list, score: float, summary: str}`
  - `POST /code-reviews/{id}` 和 `GET /code-reviews/` 路由均被覆盖，存在完整的 envelope验证和分页断言

### 1.3 不做什么（剔除）

- [ ] 不接入真实 LLM（mock固定 blob）
- [ ] 不创建 `tests/integration/` 测试文件（#613 负责集成层）
- [ ] 不修改 `CodeReviewService` 或 router 的业务逻辑（仅加测试）
- [ ] 不创建新的 ORM model 或 migration（本板块假设 #611 已完成 schema）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py -v` → 全部 passed（预计 ≥ 8 cases）
- `ruff check src/services/code_review_service.py src/api/routers/code_review_router.py tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py` → 0 errors
- `ruff format --check tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py` → 0 diff---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/code_review_service.py` L? — #611 正在实现，预期存在 `CodeReviewService.review()` 和 `CodeReviewService.list_reviews()` 方法

TBD - 待验证：`src/api/routers/code_review_router.py` L? — 预期存在 `POST /code-reviews/` 和 `GET /code-reviews/` 两个 endpoint

如果上述路径不存在则 #611 尚未合并，本板块依赖该合并后方可执行。

### 2.2 涉及文件清单

- 要改：
  - [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — 新增 `make_code_review_handler(state)` 工厂函数
- 要建：
  - `tests/unit/test_code_review_service.py` — CodeReviewService 单元测试（mock session + mock LLM blob）
  - `tests/unit/test_code_review_routers.py` — Router envelope + 分页测试（mock service 层）

### 2.3 缺什么

- [ ] 缺少 `tests/unit/test_code_review_service.py` → CodeReviewService 的 `review()` 和 `list_reviews()` 方法无回归测试
- [ ] 缺少 `tests/unit/test_code_review_routers.py` → 两个 router endpoint 无 HTTP 层覆盖- [ ] 缺少 `conftest.py` 中的 `make_code_review_handler` → 无法为 CodeReview 表构建有状态 MockResult
- [ ] 缺少对 LLM 返回结构的断言 → 无法检测 Prompt 漂移导致的字段名/类型错误
- [ ] 缺少分页逻辑测试 → `GET /code-reviews/` 的 `page / page_size` 参数边界无覆盖---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_code_review_service.py` | CodeReviewService 的 `review()` 与 `list_reviews()` 单元测试，mock LLM 返回固定 blob |
| `tests/unit/test_code_review_routers.py` | Router HTTP 层测试：envelope 结构、分页、error抛转 |
| `tests/unit/conftest.py`（改动末尾） | 新增 `make_code_review_handler(state)` 工厂函数，供两个测试文件复用 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) | 在文件末尾添加 `make_code_review_handler(state)` 工厂（与现有 `make_customer_handler` 格式一致） |

### 3.3 新增能力

- **Test cases**：`test_review_saves_and_returns_issues_score_summary`（service 层）
- **Test cases**：`test_review_list_paginates`（service 层）
- **Test cases**：`test_post_code_review_envelope`（router 层）
- **Test cases**：`test_get_code_reviews_pagination_params`（router 层）
- **Mock handler**：`make_code_review_handler(state)` — 返回有状态 MockResult，支持 INSERT / SELECT / COUNT---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **mock LLM 而非 stub**：`CodeReviewService` 需调用 `llm_service.analyze_pr()`（#611 引入），测试层注入 `MockLLMClient`（固定返回 `{"issues": [...], "score": 7.5, "summary": "ok"}`），而非 patch字典路径。这样 LLM 接口 Signature 变化时测试立即失败，提供早期预警。
- **conftest handler 而非 fixture 叠加**：在 `conftest.py`统一 `make_code_review_handler`，保证 state 在 `test_code_review_service.py` 和 `test_code_review_routers.py` 之间共享格式一致。

### 4.2 版本约束

（无新依赖）

### 4.3 兼容性约束

- 多租户：handler模拟的所有 SQL 必须含 `WHERE tenant_id = :tenant_id`（无例外）
- Service 测试不得调用 `.to_dict()`（应直接断言 ORM 对象属性或 mock call 的入参）
- Router 测试使用 `app.dependency_overrides[get_db]` 注入 mock session，不启动真实 ASGI 生命周期
- Mock handler 的 `MockRow` 列名必须与 `CodeReviewModel` 的 `__mapper_args__` 一致，否则 SQLAlchemy Row 模拟会静默返回 None

### 4.4 已知坑

1. **MockResult 缺少非主键列** → 规避：handler 的 SELECT handler 返回的 MockRow 实例必须声明所有被测方法读取的字段（含 `tenant_id`），宁可多不可少
2. **LLM blob schema硬编码导致测试与实现耦合** → 规避：mock 返回值定义在 conftest 模块顶部常量一处，service 测试 import 该常量断言；router 测试仅验证 envelope `data` 字段存在，不展开 LLM blob 结构
3. **router 测试未覆盖401 未授权** → 规避：至少写一条测试注入空的 `AuthContext` 验证 `HTTPException` 或 `AppException`，确保鉴权链路完整

---

## 5. 实现步骤（按顺序）

### Step 1: 在 conftest.py 添加 make_code_review_handler

在 `tests/unit/conftest.py` 末尾（`make_customer_handler` 附近）新增 `make_code_review_handler(state)` 工厂函数，格式与现有其他 handler 一致：支持 `INSERT`、`SELECT by id`、`SELECT list (WHERE tenant_id)`、`COUNT`。

state 中维护 `code_reviews: dict[int, dict]`，id 自增。字段对应 `CodeReviewModel` 的列名（由 #611 定义，如 `id`, `tenant_id`, `pr_url`, `issues`, `score`, `summary`, `created_at`）。

**完成判定**：`ruff check tests/unit/conftest.py` →0 errors

### Step 2: 创建 tests/unit/test_code_review_service.py

文件结构：

```python
from tests.unit.conftest import make_mock_session, make_code_review_handler, MockState

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_code_review_handler(state)])

@pytest.fixture
def code_review_service(mock_db_session):
    from services.code_review_service import CodeReviewService
    return CodeReviewService(mock_db_session)

class TestCodeReviewService:
    async def test_review_saves_and_returns_issues_score_summary(self, code_review_service):
        # mock LLM client via patch.object or MonkeyPatch 在 fixture 里
        result = await code_review_service.review(pr_url="https://github.com/org/repo/pull/1", tenant_id=1)
        assert hasattr(result, "issues")
        score = result.score
        assert 0 <= score <= 10

    async def test_list_reviews_paginates(self, code_review_service):
        items, total = await code_review_service.list_reviews(tenant_id=1, page=1, page_size=10)
        assert isinstance(items, list)
        assert total >= 0
```

Mock LLM 调用：在 fixture 用 `monkeypatch.setattr("services.code_review_service.llm_service", mock_llm_client)` 返回固定 blob。

**完成判定**：`PYTHONPATH=src ruff check tests/unit/test_code_review_service.py` →0 errors

### Step 3: 创建 tests/unit/test_code_review_routers.py

文件结构：

```python
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from main import app
from dependencies import get_db, require_auth
from internal.middleware.fastapi_auth import AuthContext

@pytest.fixture
def mock_session():
    state = MockState()
    return make_mock_session([make_code_review_handler(state)])

@pytest.fixture
def client(mock_session):
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[require_auth] = lambda: AuthContext(tenant_id=1, user_id=1)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

class TestCodeReviewRouters:
    async def test_post_returns_envelope(self, client):
        response = client.post("/code-reviews/", json={"pr_url": "..."})
        assert response.status_code == 200        data = response.json()
        assert data["success"] is True
        assert "data" in data

    async def test_get_list_pagination_params(self, client):
        response = client.get("/code-reviews/?page=2&page_size=5")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "items" in data
        assert "total" in data
```

**完成判定**：`PYTHONPATH=src ruff check tests/unit/test_code_review_routers.py` → 0 errors

### Step 4: 运行全部单元测试套件验证```bash
PYTHONPATH=src pytest tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py -v
```

**完成判定**：输出包含 `test_code_review_service.py::... PASSED` 和 `test_code_review_routers.py::... PASSED`，全部 passed，exit 0### Step 5: Lint 全量相关文件

```bash
ruff check tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py tests/unit/conftest.py
ruff format --check tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py
```

**完成判定**：两条命令均 exit 0

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py tests/unit/conftest.py` → 0 errors
- [ ] `PYTHONPATH=src ruff format --check tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py` → 0 diff
- [ ] `PYTHONPATH=src pytest tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py -v` →全部 passed（预计 ≥ 8 cases）
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` →全部 passed（回归验证，不引入新错误）

---

## 7. 风险与回退

|风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #611尚未合并导致路径/类名未知，测试写到错误位置 | 中 | 中 | 先基于 issue #612 的接口描述和 `conftest.py`已有 handler格式写骨架；#611 合并后用 `ruff check` 报错驱动快速修正 |
| Mock handler字段名与 #611 ORM model 列名不匹配导致测试静默通过 | 中 | 高 | 在 `test_review_saves_and_returns_issues_score_summary` 中对关键字段（issues、score）加显式 assert，而非仅检查非 None |
| conftest handler 修改影响其他已有单元测试 | 低 | 高 | 先只在 `test_code_review_service.py` 自己的 `mock_db_session` fixture 中加 handler，勿直接改顶层已有 fixtures |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_code_review_service.py tests/unit/test_code_review_routers.py tests/unit/conftest.py
git commit -m "test(platform): add unit tests for CodeReviewService and routers (closes #612)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(platform): unit tests for CodeReviewService and routers" --body "Closes #612"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — `make_customer_handler` / `make_user_handler` 模式- 同类参考实现：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — service 层 mock范式
- 同类参考实现：[`tests/unit/`](../../../tests/unit/) — router 测试文件（如有）
- 父 issue /关联：#44（平台基础设施父 issue）、#611（CodeReviewService 实现，#612 直接依赖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
