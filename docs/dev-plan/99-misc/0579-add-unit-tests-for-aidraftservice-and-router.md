# AI Draft 单元测试 · 为 AiDraftService 和路由编写测试

| 元数据 | 值 |
|---|---|
| Issue | #579 |
| 分类 | 99-misc |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | [0578-add-ai-draft-service](../50-campaigns/0578-add-ai-draft-service-and-router.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

AiDraftService 是 CRM 内容生成能力的核心服务，目前没有任何单元测试覆盖。每次对 `generate_draft` 的修改都是盲操作，无法在本地快速验证正确性。路由层（`ai_draft` router）同样缺少集成测试，API 契约（输入/输出格式）没有被任何测试守护。这导致了两个问题：(a) 开发者不敢改 `generate_draft` 内部逻辑；(b) 重构或添加新 draft type / tone 时极易引入回归。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层测试追加。
- **开发者视角**：获得 `tests/unit/test_ai_draft_service.py` 和 `tests/unit/test_ai_draft_router.py` 两个测试文件，可独立运行（无需数据库）；修改 `generate_draft` 后本地 `pytest` 秒级验证正确性；路由的输入验证和错误响应有 TestClient 覆盖。

### 1.3 不做什么（剔除）

- [ ] 不修改 `AiDraftService` 本身的生产代码（只追加测试）
- [ ] 不修改 `ai_draft` router 的生产代码（只追加测试）
- [ ] 不添加集成测试（integration 层）；不引入真实数据库连接
- [ ] 不测试 AI agent 框架本身（mock 掉，不测第三方 SDK 行为）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_ai_draft_service.py -v` → `≥ 6 passed`（每种 draft type × tone 组合一个用例 + 边界用例）
- `PYTHONPATH=src pytest tests/unit/test_ai_draft_router.py -v` → `≥ 4 passed`（GET/POST 路由、错误响应、参数校验）
- `ruff check src/services/ai_draft_service.py src/api/routers/ai_draft.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/ai_draft_service.py` L? — 需确认 `AiDraftService` 类名、`generate_draft` 方法签名（参数含 `draft_type: str` 和 `tone: str`？）
TBD - 待验证：`src/api/routers/ai_draft.py` L? — 需确认路由路径（如 `/ai/draft`）、HTTP 方法、依赖 `require_auth`

TBD - 待验证：`src/internal/ai/` L? — 需确认 AI agent 框架调用路径（如 `AIAgent` 类），以便在 mock 中 patch 正确路径

### 2.2 涉及文件清单

- 要改：
  - `src/services/ai_draft_service.py` — 如 `generate_draft` 方法签名与本板块测试假设不一致，需先对齐
- 要建：
  - `tests/unit/test_ai_draft_service.py` — AiDraftService 单元测试（mock DB session）
  - `tests/unit/test_ai_draft_router.py` — FastAPI TestClient 路由测试

### 2.3 缺什么

- [ ] `tests/unit/test_ai_draft_service.py` 不存在 — `AiDraftService` 无单元测试
- [ ] `tests/unit/test_ai_draft_router.py` 不存在 — 路由无 TestClient 覆盖
- [ ] `mock_db_session` fixture 未包含 `ai_draft` 相关 handler（如有持久化调用）；如 `generate_draft` 是纯计算（无 DB 写），则无需新 handler
- [ ] `generate_draft` 各 draft type（email/sms）和 tone 组合无覆盖
- [ ] 路由参数校验（缺少必填字段、超出合法 tone 范围）无测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_ai_draft_service.py` | AiDraftService 单元测试：mock_db_session fixture + generate_draft(email/sms × 3 tone 组合 + 边界) |
| `tests/unit/test_ai_draft_router.py` | FastAPI TestClient 测试：端到端路由验证 + 错误响应 + 参数校验 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/services/ai_draft_service.py` | 如 `generate_draft` 需调整可见性（目前可能是 async def，需确认为纯函数供 mock） |
| TBD - 待验证：`src/api/routers/ai_draft.py` | 确认 router 使用 `Depends(require_auth)` 和 `Depends(get_db)`，测试依赖此签名 |

### 3.3 新增能力

- **Service test**：覆盖 `generate_draft(draft_type="email"|"sms", tone="formal"|"friendly"|"urgent", tenant_id)` 全组合（6 用例）
- **Service test**：边界 case — `draft_type` 无效值、`tone` 无效值（各 1 用例）
- **Router test**：`POST /ai/draft` 成功响应格式 `{"success": true, "data": {...}}`
- **Router test**：未认证请求返回 401
- **Router test**：缺少必填字段返回 422
- **Router test**：无效 draft_type/tone 返回 422

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Mock AIAgent 框架而非集成测试**：避免测试依赖外部 AI 服务（延迟、费用、不稳定），遵循单元测试隔离原则。
- **FastAPI TestClient 而非 httpx.AsyncClient**：同步 TestClient 可在标准 pytest 同步测试函数中使用，无需标记 `async def`，与现有 `tests/unit/` 模式一致。
- **MockState + make_mock_session 而非真实 DB**：符合 CLAUDE.md 规定；unit 测试必须无真实数据库。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：`generate_draft` 调用需传入 `tenant_id: int`，所有 SQL 过滤需含 `tenant_id`（测试 fixture 中验证）
- Service 方法签名：`async def generate_draft(self, draft_type: str, tone: str, tenant_id: int) -> dict`
- Service 返回 dict/dataclass，**不**调用 `.to_dict()`
- Service 错误抛 `AppException` 子类（如 `ValidationException`）
- `AiDraftService.__init__` 签名为 `def __init__(self, session: AsyncSession)` — 无默认值

### 4.4 已知坑

1. **pytest-asyncio 事件循环冲突** → 规避：router 测试使用 `TestClient`（同步），不使用 `AsyncClient`；service 测试如需 async，使用 `pytest.mark.asyncio` 并在 conftest 定义 `event_loop` fixture
2. **Mock AIAgent 路径必须精确** → 规避：在测试文件顶部 `with patch("src.services.ai_draft_service.AIAgent")`（具体路径待 §2.1 验证后填入），而非写死错误路径导致 mock 失效
3. **TestClient 传入 app 需要 router 已注册** → 规避：从 `src.main import app` 导入，而非在测试文件内构建 `APIRouter` 实例，确保所有中间件和依赖项被正确加载

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 AiDraftService 和 router 的当前签名

向开发者/lead 确认以下信息（可在 GitHub issue #579 评论区提问）：

- `src/services/ai_draft_service.py` 中 `generate_draft` 方法的完整签名
- `src/api/routers/ai_draft.py` 的路由路径和 HTTP 方法
- AI agent 框架调用路径（如 `from src.internal.ai.agent import AIAgent`）

**完成判定**：上述信息记录于 issue #579 评论区或 Confluence

---

### Step 2: 编写 `tests/unit/test_ai_draft_service.py`（mock_db_session fixture + generate_draft 测试）

在 `tests/unit/test_ai_draft_service.py` 中创建文件：

```python
# tests/unit/test_ai_draft_service.py
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

# 替换为 §5 Step 1 确认后的正确导入路径
from src.services.ai_draft_service import AiDraftService
from tests.unit.conftest import make_mock_session, MockState


@pytest.fixture
def mock_db_session():
    # AiDraftService.generate_draft 是纯计算（无 DB 写），使用空 handler 列表即可
    return make_mock_session([])


@pytest.fixture
def ai_draft_service(mock_db_session: AsyncSession) -> AiDraftService:
    return AiDraftService(mock_db_session)


class TestGenerateDraft:
    DRAFT_TYPES = ["email", "sms"]
    TONES = ["formal", "friendly", "urgent"]

    @pytest.mark.parametrize("draft_type", DRAFT_TYPES)
    @pytest.mark.parametrize("tone", TONES)
    async def test_generate_draft_returns_expected_keys(
        self, ai_draft_service: AiDraftService, draft_type: str, tone: str
    ):
        with patch("src.services.ai_draft_service.AIAgent") as mock_agent:
            mock_agent.return_value.generate = AsyncMock(return_value="mocked content")
            result = await ai_draft_service.generate_draft(
                draft_type=draft_type, tone=tone, tenant_id=1
            )
            assert isinstance(result, dict)
            assert "content" in result

    async def test_generate_draft_invalid_draft_type(self, ai_draft_service: AiDraftService):
        with pytest.raises(ValidationException):
            await ai_draft_service.generate_draft(
                draft_type="invalid_type", tone="formal", tenant_id=1
            )

    async def test_generate_draft_invalid_tone(self, ai_draft_service: AiDraftService):
        with pytest.raises(ValidationException):
            await ai_draft_service.generate_draft(
                draft_type="email", tone="weird_tone", tenant_id=1
            )
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ai_draft_service.py -v` → `10 passed`（6 parametrize + 2 invalid + 2 其他边界）

---

### Step 3: 编写 `tests/unit/test_ai_draft_router.py`（FastAPI TestClient）

在 `tests/unit/test_ai_draft_router.py` 中创建文件：

```python
# tests/unit/test_ai_draft_router.py
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestAiDraftRouter:
    @patch("src.services.ai_draft_service.AIAgent")
    def test_post_ai_draft_success(self, mock_agent, client: TestClient):
        mock_agent.return_value.generate = AsyncMock(return_value="mocked content")
        # 需提供有效的 auth token（mock require_auth 依赖）
        response = client.post(
            "/ai/draft",
            json={"draft_type": "email", "tone": "formal", "content": "hello"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_post_ai_draft_unauthorized(self, client: TestClient):
        response = client.post(
            "/ai/draft",
            json={"draft_type": "email", "tone": "formal", "content": "hello"},
        )
        assert response.status_code == 401

    def test_post_ai_draft_missing_fields(self, client: TestClient):
        response = client.post(
            "/ai/draft",
            json={"draft_type": "email"},  # 缺 tone 和 content
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 422

    def test_post_ai_draft_invalid_tone(self, client: TestClient):
        response = client.post(
            "/ai/draft",
            json={"draft_type": "email", "tone": "invalid", "content": "hi"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 422
```

如 `require_auth` 依赖无法在 TestClient 中通过 `Authorization` header 绕过，需在测试文件 conftest 或 `tests/unit/conftest.py` 中覆盖 `require_auth` fixture：

```python
# 在 tests/unit/conftest.py 中追加（如尚未存在）
@pytest.fixture
def mock_auth():
    from src.internal.middleware.fastapi_auth import AuthContext
    return AuthContext(user_id=1, tenant_id=1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ai_draft_router.py -v` → `4 passed`

---

### Step 4: 运行全量 unit 测试验证无回归

```bash
export PYTHONPATH=src
pytest tests/unit/ -v
```

**完成判定**：全 unit 测试 passed（regression = 0）

---

## 6. 验收

- [ ] `ruff check src/services/ai_draft_service.py src/api/routers/ai_draft.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_ai_draft_service.py -v` → `≥ 10 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/test_ai_draft_router.py -v` → `≥ 4 passed`
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → 全 passed（regression check）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| §5 Step 1 无法快速确认签名（开发者不响应） | 低 | 中 | 先按合理假设编写测试，PR 时 review 修正；不影响生产代码 |
| AI agent mock 路径错误导致所有用例 FAIL | 中 | 低 | 在 conftest 中统一管理 mock 路径常量；单点修改即可修复所有测试 |
| TestClient 路由测试依赖 `require_auth` 覆盖方式不稳定 | 低 | 低 | 已在 conftest 提供 `mock_auth` fixture；后续如 auth 实现变更，只需更新 fixture |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_ai_draft_service.py tests/unit/test_ai_draft_router.py
git commit -m "test: add unit tests for AiDraftService and ai_draft router"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#579): unit tests for AiDraftService and router" --body "Closes #579"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — mock_db_session fixture 模式和 AppException assert 写法
- 同类参考实现：[`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — MockState、make_mock_session、mock_auth fixture
- 父 issue：#50
- 依赖 issue：#578
