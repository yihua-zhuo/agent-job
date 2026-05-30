# AI 草稿 · 添加 AiDraft Pydantic schemas 和 AiDraftService

| 元数据 | 值 |
|---|---|
| Issue | #577 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 2-3 工作日 |
| 依赖 | [板块名](../40-ai-agent-framework/0410-add-ai-agent-framework-and-agents.md) |
| 启用后赋能 | [板块名](../50-automation/0578-add-ai-draft-router-endpoints.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 系统中销售/客服人员需要 AI 辅助快速生成邮件/短信草稿。当前系统没有结构化的 AI 草稿生成能力，所有生成逻辑分散或缺失。#41 已建立 AI Agent 框架，本板块在该框架上构建业务层（schema + service），为后续 #578 路由层打好基础。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层服务层和 schema 改动，为 #578 路由提供可调用接口。
- **开发者视角**：`AiDraftService` 可生成邮件/短信草稿并返回建议操作列表；`DraftRequest` / `DraftResponse` Pydantic 模型可直接导入使用；Service 与 AI Agent 框架 (#41) 解耦，通过接口调用生成逻辑。

### 1.3 不做什么（剔除）

- [ ] 不实现 `POST /ai-draft` 等 HTTP 路由（留待 #578）
- [ ] 不实现草稿保存/持久化（留待后续 issue）
- [ ] 不实现 AI Agent 框架本身（由 #41 提供）

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_ai_draft_service.py -v` → ≥ 3 passed]
- [指标 2：`ruff check src/models/ai_draft.py src/services/ai_draft_service.py` → 0 errors]
- [指标 3：`mypy src/models/ai_draft.py src/services/ai_draft_service.py` → 0 errors]
- [指标 4：Service 方法 `AiDraftService.generate_draft` 在 mock 下正确构造 `DraftResponse` 并返回]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/models/` 目录下尚无 `ai_draft.py`；`src/services/` 目录下尚无 `ai_draft_service.py`；需确认 #41 AI Agent 框架暴露的调用接口（`AgentFramework` 类 / `generate` 方法签名）。

### 2.2 涉及文件清单

- 要改：
  - `src/models/` — 新增 `ai_draft.py`（尚不存在，需确认 model 目录组织方式）
  - `src/services/` — 新增 `ai_draft_service.py`（尚不存在）
  - `tests/unit/` — 新增 `test_ai_draft_service.py`
- 要建：
  - `src/models/ai_draft.py` — DraftRequest / DraftContext / DraftResponse Pydantic 模型
  - `src/services/ai_draft_service.py` — AiDraftService，调用 AI Agent 框架
  - `tests/unit/test_ai_draft_service.py` — 单元测试

### 2.3 缺什么

- [ ] `DraftRequest` Pydantic 模型（含 `type: Literal[email,sms]`、`tone`、`context` 等字段）
- [ ] `DraftContext` Pydantic 模型（含 `customer_id`、`opportunity_id`、`template_type` 等）
- [ ] `DraftResponse` Pydantic 模型（含 `body`、`suggested_actions`）
- [ ] `AiDraftService.generate_draft` 方法，接收 `DraftRequest` 并返回 `DraftResponse`
- [ ] 对 #41 AI Agent 框架的调用封装（需确认接口签名）
- [ ] 完整单元测试覆盖（mock AI Agent 框架）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/models/ai_draft.py` | DraftRequest / DraftContext / DraftResponse Pydantic 模型 |
| `src/services/ai_draft_service.py` | AiDraftService，调用 AI Agent 框架生成草稿 |
| `tests/unit/test_ai_draft_service.py` | AiDraftService 单元测试，mock AI Agent 框架 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| 无 | 本板块不修改现有文件 |

### 3.3 新增能力

- **Pydantic models**：`DraftRequest`, `DraftContext`, `DraftResponse` in `src/models/ai_draft.py`
- **Service method**：`AiDraftService(session: AsyncSession).generate_draft(request: DraftRequest, tenant_id: int) -> DraftResponse`
- **AI integration**：调用 #41 AI Agent 框架生成邮件/短信正文并返回建议操作

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Pydantic models 放在 `src/models/` 而非 `src/schemas/`**：与本仓库 `src/models/` 目录存放 Pydantic schemas 的现有约定一致（如有 `src/models/response.py` 的 `ApiResponse`）
- **Service 不做持久化**：草稿仅在内存中返回，保存逻辑由后续 issue 负责；降低本板块 scope
- **Mock AI Agent 框架而非调用真实 API**：单元测试必须快（<5s），不依赖外部 AI 服务

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- `AiDraftService.__init__` 接受 `session: AsyncSession`，无默认值
- Service 抛出 `AppException` 子类，**不**返回错误 dict
- Service 返回 `DraftResponse` ORM/dataclass 对象，**不**调用 `.to_dict()`
- 所有 SQL 查询（含 future 扩展）必须 `WHERE tenant_id = :tenant_id`

### 4.4 已知坑

1. **#41 AI Agent 框架接口尚未确认** → 规避：在 Service 中通过抽象方法/依赖注入调用，避免直接依赖具体类名；单元测试 mock 整个框架调用
2. **Pydantic `Literal` 类型与 `Optional` 嵌套** → 规避：`subject?: str` 只在 `type=email` 时有效，建模时在 `DraftRequest` 层面接受可选字段，由 service 层或后续 validator 约束业务规则

---

## 5. 实现步骤（按顺序）

### Step 1: 定义 Pydantic schemas（DraftRequest / DraftContext / DraftResponse）

在 `src/models/ai_draft.py` 中定义以下模型：

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class DraftContext(BaseModel):
    customer_id: int | None = None
    opportunity_id: int | None = None
    template_type: str | None = None

class DraftRequest(BaseModel):
    type: Literal["email", "sms"]
    tone: Literal["professional", "friendly", "urgent"]
    subject: Optional[str] = None
    context: DraftContext = Field(default_factory=DraftContext)

class SuggestedAction(BaseModel):
    label: str
    description: str

class DraftResponse(BaseModel):
    body: str
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
```

**完成判定**：`ruff check src/models/ai_draft.py` → 0 errors

---

### Step 2: 确认 AI Agent 框架接口并定义抽象调用

TBD - 待验证：在 `src/services/ai_draft_service.py` 中导入 #41 框架暴露的接口；若接口尚未确定，使用 `Any` 类型占位并在 TODO 注释中注明待 #41 合并后填入：

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.ai_draft import DraftRequest, DraftResponse
# TODO: import AgentFramework from #41 once merged
from typing import Any

class AiDraftService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_draft(self, request: DraftRequest, tenant_id: int) -> DraftResponse:
        # TODO: call AgentFramework.generate(request) after #41 merges
        ...
```

**完成判定**：`ruff check src/services/ai_draft_service.py` → 0 errors；`mypy src/services/ai_draft_service.py` → 0 errors

---

### Step 3: 实现 generate_draft 业务逻辑

在 `AiDraftService.generate_draft` 中：

1. 构造 prompt / context payload 传给 AI Agent 框架（#41）
2. 解析 AI 返回的 JSON，取 `body` 和 `suggested_actions`
3. 构建并返回 `DraftResponse`
4. 若 AI 调用失败，抛出 `ValidationException("AI draft generation failed")`

```python
async def generate_draft(self, request: DraftRequest, tenant_id: int) -> DraftResponse:
    payload = {
        "type": request.type,
        "tone": request.tone,
        "subject": request.subject,
        "customer_id": request.context.customer_id,
        "opportunity_id": request.context.opportunity_id,
    }
    # agent = AgentFramework()  # TODO: after #41
    # result = await agent.generate(prompt=payload)
    # response_data = json.loads(result)
    return DraftResponse(
        body=response_data.get("body", ""),
        suggested_actions=[
            SuggestedAction(label=a["label"], description=a["description"])
            for a in response_data.get("suggested_actions", [])
        ]
    )
```

**完成判定**：`ruff check src/services/ai_draft_service.py` → 0 errors；文件存在

---

### Step 4: 编写单元测试

在 `tests/unit/test_ai_draft_service.py` 中：

1. 定义 `mock_db_session` fixture（使用 `make_mock_session`，参考 CLAUDE.md §Unit Test SQL Mocks）
2. 用 `unittest.mock.AsyncMock` mock AI Agent 框架调用
3. 测试场景：
   - 正常生成邮件草稿
   - 正常生成短信草稿
   - AI 调用抛出异常时抛出 `ValidationException`
   - `tenant_id` 正确传递（虽然本板块暂不查 DB，但保持接口一致性）

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.services.ai_draft_service import AiDraftService
from src.models.ai_draft import DraftRequest, DraftContext, DraftResponse, SuggestedAction

@pytest.fixture
def mock_db_session():
    from tests.unit.conftest import make_mock_session
    return make_mock_session([])

@pytest.fixture
def service(mock_db_session):
    return AiDraftService(mock_db_session)

@pytest.mark.asyncio
async def test_generate_email_draft(service):
    mock_response = {
        "body": "Dear customer, following up on your inquiry...",
        "suggested_actions": [{"label": "Send", "description": "Send the email now"}]
    }
    with patch("src.services.ai_draft_service.AgentFramework") as MockAgent:
        MockAgent.return_value.generate = AsyncMock(return_value=json.dumps(mock_response))
        request = DraftRequest(type="email", tone="professional", subject="Follow-up")
        response = await service.generate_draft(request, tenant_id=1)
        assert isinstance(response, DraftResponse)
        assert "Dear customer" in response.body
        assert len(response.suggested_actions) == 1

@pytest.mark.asyncio
async def test_generate_sms_draft(service):
    mock_response = {"body": "Hi! Quick question for you.", "suggested_actions": []}
    with patch("src.services.ai_draft_service.AgentFramework") as MockAgent:
        MockAgent.return_value.generate = AsyncMock(return_value=json.dumps(mock_response))
        request = DraftRequest(type="sms", tone="friendly")
        response = await service.generate_draft(request, tenant_id=1)
        assert response.body == "Hi! Quick question for you."
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ai_draft_service.py -v` → ≥ 3 passed

---

## 6. 验收

- [ ] `ruff check src/models/ai_draft.py src/services/ai_draft_service.py` → 0 errors
- [ ] `PYTHONPATH=src mypy src/models/ai_draft.py src/services/ai_draft_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_ai_draft_service.py -v` → ≥ 3 passed
- [ ] `PYTHONPATH=src ruff format --check src/models/ai_draft.py src/services/ai_draft_service.py` → 0 errors（格式合规）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #41 AI Agent 框架接口与本板块预期差异大，导致 Service 需重构 | 中 | 中 | Service 层通过 adapter 模式隔离 AI 框架调用；只需改 adapter 不影响 schema 和测试 |
| AI Agent 框架尚未合并，本板块依赖的 import 不存在 | 中 | 低 | 用 `Any` + mock 绕过；合并 #41 后填入真实类型 |
| mock 测试覆盖率不足，真实调用时 response parsing 失败 | 低 | 中 | 后续 #578 集成测试覆盖真实调用路径 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/models/ai_draft.py src/services/ai_draft_service.py tests/unit/test_ai_draft_service.py
git commit -m "feat(automation): add AiDraft schemas and AiDraftService (#577)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(automation): add AiDraft Pydantic schemas and AiDraftService (#577)" --body "Closes #577"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/models/` 目录下现有 Pydantic schema 组织方式（参考 `src/models/response.py` 的 `ApiResponse` 定义模式）
- 父 issue / 关联：#50（父），#41（AI Agent 框架依赖）
- 关联后续：#578（Add AiDraft router endpoints — 本板块的下一跳）
