# Audience AI · Suggest audience button in Campaign Builder

| 元数据 | 值 |
|---|---|
| Issue | #534 |
| 分类 | 40-campaigns |
| 优先级 | 推荐 |
| 工作量 | 2 工作日 |
| 依赖 | [#533](./0333-xxx.md)（AI agent endpoint）, [50-automation/0041-ai-agent-core](./50-automation/0041-ai-agent-core.md)（AI endpoint wire target） |
| 启用后赋能 | [板块名](相对路径)，... |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The Campaign Builder currently requires manual audience/segment selection with no intelligent suggestion capability. Marketers must already know the segment query DSL or browse through the segment list. Adding an AI-powered "Suggest audience" button reduces time-to-first-segment and surfaces relevant segments that match the campaign's type and description. This is a prerequisite for downstream AI features in the campaigns domain.

### 1.2 做完后

- **用户视角**：Marketers editing or creating a campaign see a "Suggest audience" button on the audience/segment selector. Clicking it calls the AI agent endpoint, and the returned segment query populates the selector. If the AI service is unavailable, a user-friendly message is shown and the selector remains usable without suggestions.
- **开发者视角**：`marketing_service.py` gains `suggest_audience(campaign_type, description)`. The router in `campaigns.py` exposes `POST /campaigns/suggest-audience`. A feature flag `campaigns.ai_audience_suggestions` gates the button in the frontend. Tests cover both the happy path and the graceful-fallback path.

### 1.3 不做什么（剔除）

- [ ] Backend implementation of the AI agent endpoint itself (belongs to #41)
- [ ] Changes to the campaign list view or campaign CRUD beyond the builder
- [ ] Persistence of AI-suggested segments (suggestion is one-shot, user must confirm and save)
- [ ] UI redesign of the entire Campaign Builder — only the audience suggestion area is modified

### 1.4 关键 KPI

- [Feature flag `campaigns.ai_audience_suggestions` toggled on → button visible in Campaign Builder]
- [Button click → AI endpoint called → segment query returned within 5 s (p95)]
- [AI endpoint unavailable → button disabled with tooltip, no JS error thrown]
- [`PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v` → ≥ 4 passed]
- [`ruff check src/services/marketing_service.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/marketing_service.py`](../../src/services/marketing_service.py) L{1}-L{50}

```python
# Partial excerpt — existing service structure
from sqlalchemy.ext.asyncio import AsyncSession

class MarketingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_campaign(self, campaign_id: int, tenant_id: int) -> Campaign:
        ...

    async def list_campaigns(self, tenant_id: int, page: int, page_size: int) -> tuple[list[Campaign], int]:
        ...
```

CampaignBuilder 前端入口（需验证路径）：

TBD - 待验证：`src/ui/pages/marketing/CampaignBuilder.tsx L? — 现有 CampaignBuilder 组件结构，是否已有 audience selector 区域>

### 2.2 涉及文件清单

- 要改：
  - `src/services/marketing_service.py` — 新增 `suggest_audience` 方法
  - `src/api/routers/campaigns.py` — 新增 `POST /campaigns/suggest-audience` 路由
  - `src/config/feature_flags.py` — 新增 `campaigns.ai_audience_suggestions` 布尔标志
  - `src/ui/pages/marketing/CampaignBuilder.tsx` — 添加 "Suggest audience" 按钮
  - `tests/unit/test_marketing_service.py` — 新增 `suggest_audience` 用例
- 要建：
  - `src/services/ai_agent_client.py` — 调用 #41 AI agent endpoint 的 HTTP 客户端
  - `tests/unit/test_marketing_service.py` — 扩展现有文件，新增测试用例

### 2.3 缺什么

- [ ] `suggest_audience` service method that accepts campaign type + description and calls the AI agent endpoint
- [ ] `POST /campaigns/suggest-audience` router endpoint with proper error handling
- [ ] Feature flag `campaigns.ai_audience_suggestions` to gate the UI button
- [ ] Frontend "Suggest audience" button in `CampaignBuilder.tsx` wired to the new endpoint
- [ ] Graceful fallback: if AI service returns 503/timeout, show friendly message and keep selector functional
- [ ] Unit tests for the `suggest_audience` service method and router

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/ai_agent_client.py` | HTTP client calling the AI agent endpoint (#41) with campaign payload |
| `tests/unit/test_marketing_service.py` | 新增测试用例（扩展现有文件，如文件不存在则新建） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/marketing_service.py`](../../src/services/marketing_service.py) | 新增 `suggest_audience(campaign_type, description, tenant_id)` 方法，调用 `ai_agent_client` |
| [`src/api/routers/campaigns.py`](../../src/api/routers/campaigns.py) | 新增 `POST /campaigns/suggest-audience` 路由，读取 feature flag，透传 tenant_id |
| [`src/config/feature_flags.py`](../../src/config/feature_flags.py) | 新增 `campaigns.ai_audience_suggestions: bool = False` |
| `src/ui/pages/marketing/CampaignBuilder.tsx` | 添加 "Suggest audience" 按钮，调用 `POST /campaigns/suggest-audience` |

### 3.3 新增能力

- **Service method**：`MarketingService.suggest_audience(self, campaign_type: str, description: str, tenant_id: int) -> dict`
- **API endpoint**：`POST /campaigns/suggest-audience` body `{campaign_type, description}` → `{"success": true, "data": {"segment_query": "...", "confidence": 0.9}}`
- **Feature flag**：`campaigns.ai_audience_suggestions` (bool, default False)
- **Frontend button**："Suggest audience" in CampaignBuilder audience panel, disabled when flag is off or AI service unavailable

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Feature flag over always-on**：The AI endpoint (#41) may not be deployed in all environments. Gating behind a flag lets us ship the code without requiring the dependency to be live. When the flag is off the button is hidden entirely (no degraded state shown to users).
- **Graceful fallback in frontend**：Instead of a 500-page crash, catching `fetch` errors in the button handler shows an inline toast. This avoids blocking the marketer from using the campaign builder if the AI service is down.
- **No persistence of suggestion**：The AI suggestion is shown but not saved until the user explicitly confirms and submits the campaign. This avoids dirty data from low-confidence AI outputs.

### 4.2 版本约束

<!-- 无新第三方依赖引入，整段保留为空 -->

### 4.3 兼容性约束

- 多租户：AI agent client call must pass `tenant_id` in the request body; the upstream #41 endpoint is responsible for tenant isolation on its side
- Service returns ORM/dataclass/dict objects，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException`），**不**返回 `ApiResponse.error()`
- Async session 不要用 `async with get_db()`，用 `Depends(get_db)`
- PYTHONPATH=src，import 写 `from services.ai_agent_client` 而不是 `from src.services.ai_agent_client`

### 4.4 已知坑

1. **Feature flag import in router** → 规避：`feature_flags.py` 使用 Pydantic `BaseSettings` 或 `functools.cache` 避免每次请求重新加载；flag 值在 startup 时读一次，不在 hot path 查 DB
2. **CampaignBuilder.tsx 类型安全** → 规避：按钮 `onClick` 使用 `try/catch` 包装 `fetch`，error 时 set 局部 `error` state 渲染 inline message；不抛 JS 异常
3. **AI agent timeout** → 规避：`ai_agent_client.py` 使用 `httpx.AsyncClient(timeout=5.0)`；router catches `httpx.TimeoutException` and returns HTTP 503 with `{success: false, message: "AI service temporarily unavailable"}`

---

## 5. 实现步骤（按顺序）

### Step 1: Add feature flag `campaigns.ai_audience_suggestions`

在 `src/config/feature_flags.py` 中新增布尔标志：

```python
# src/config/feature_flags.py
campaigns: CampaignsFlags = CampaignsFlags()

class CampaignsFlags(BaseModel):
    ai_audience_suggestions: bool = False   # NEW
```

**完成判定**：`ruff check src/config/feature_flags.py` → 0 errors

---

### Step 2: Create `ai_agent_client.py` HTTP client

新建 `src/services/ai_agent_client.py`，调用 #41 AI agent endpoint：

```python
# src/services/ai_agent_client.py
import httpx
from typing import Any

class AIAgentClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or "http://localhost:8000"

    async def suggest_audience(
        self,
        campaign_type: str,
        description: str,
        tenant_id: int,
    ) -> dict[str, Any]:
        payload = {
            "task": "suggest_segment",
            "context": {
                "campaign_type": campaign_type,
                "description": description,
                "tenant_id": tenant_id,
            },
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{self.base_url}/ai/suggest-segment",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
```

**完成判定**：`ruff check src/services/ai_agent_client.py` → 0 errors

---

### Step 3: Add `MarketingService.suggest_audience` method

在 `src/services/marketing_service.py` 中新增方法：

```python
# src/services/marketing_service.py
from services.ai_agent_client import AIAgentClient

class MarketingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def suggest_audience(
        self,
        campaign_type: str,
        description: str,
        tenant_id: int,
    ) -> dict[str, Any]:
        client = AIAgentClient()
        result = await client.suggest_audience(campaign_type, description, tenant_id)
        return result
```

**完成判定**：`ruff check src/services/marketing_service.py` → 0 errors

---

### Step 4: Add `POST /campaigns/suggest-audience` router endpoint

在 `src/api/routers/campaigns.py` 中新增路由：

```python
# src/api/routers/campaigns.py
from config.feature_flags import feature_flags

@router.post("/suggest-audience")
async def suggest_campaign_audience(
    body: SuggestAudienceRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    if not feature_flags.campaigns.ai_audience_suggestions:
        raise ForbiddenException("AI audience suggestions are not enabled")
    svc = MarketingService(session)
    result = await svc.suggest_audience(
        campaign_type=body.campaign_type,
        description=body.description,
        tenant_id=ctx.tenant_id,
    )
    return {"success": True, "data": result}
```

在 `src/models/schemas.py` 新增请求 schema：

```python
# src/models/schemas.py
class SuggestAudienceRequest(BaseModel):
    campaign_type: str
    description: str
```

**完成判定**：`ruff check src/api/routers/campaigns.py` → 0 errors

---

### Step 5: Add "Suggest audience" button to `CampaignBuilder.tsx`

在 `src/ui/pages/marketing/CampaignBuilder.tsx` audience selector 区域添加按钮：

```typescript
// CampaignBuilder.tsx — audience selector area
import { featureFlags } from "@/config/featureFlags";  // adjust import path

const [suggesting, setSuggesting] = useState(false);
const [suggestionError, setSuggestionError] = useState<string | null>(null);

const handleSuggestAudience = async () => {
  if (!featureFlags.campaigns.aiAudienceSuggestions) return;
  setSuggesting(true);
  setSuggestionError(null);
  try {
    const res = await fetch("/campaigns/suggest-audience", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        campaign_type: campaign.type,
        description: campaign.description,
      }),
    });
    const json = await res.json();
    if (json.success && json.data?.segment_query) {
      setAudienceQuery(json.data.segment_query);
    } else {
      setSuggestionError(json.message || "Failed to get suggestion");
    }
  } catch {
    setSuggestionError("AI service unavailable. Please try again later.");
  } finally {
    setSuggesting(false);
  }
};

// In JSX, inside the audience panel:
{featureFlags.campaigns.aiAudienceSuggestions && (
  <button
    onClick={handleSuggestAudience}
    disabled={suggesting}
    className="btn-secondary"
  >
    {suggesting ? "Getting suggestion…" : "Suggest audience"}
  </button>
)}
{suggestionError && <p className="text-error">{suggestionError}</p>}
```

**完成判定**：`npx tsc --noEmit src/ui/pages/marketing/CampaignBuilder.tsx` → 0 errors（如有 TSC 配置）；或 ESLint `eslint src/ui/pages/marketing/CampaignBuilder.tsx` → 0 errors

---

### Step 6: Add unit tests for `suggest_audience`

在 `tests/unit/test_marketing_service.py` 新增测试用例：

```python
# tests/unit/test_marketing_service.py
import pytest
from unittest.mock import AsyncMock, patch
from services.marketing_service import MarketingService

@pytest.mark.asyncio
async def test_suggest_audience_happy_path(mock_db_session):
    svc = MarketingService(mock_db_session)
    with patch("services.marketing_service.AIAgentClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.suggest_audience = AsyncMock(
            return_value={"segment_query": "status='active' AND region='EU'", "confidence": 0.87}
        )
        result = await svc.suggest_audience(
            campaign_type="email",
            description="Spring sale to European customers",
            tenant_id=1,
        )
        assert result["segment_query"] == "status='active' AND region='EU'"
        assert result["confidence"] == 0.87
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v -k suggest` → ≥ 1 passed

---

## 6. 验收

- [ ] `ruff check src/services/marketing_service.py src/services/ai_agent_client.py src/api/routers/campaigns.py src/config/feature_flags.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v -k suggest` → ≥ 1 passed
- [ ] `ruff check tests/unit/test_marketing_service.py` → 0 errors
- [ ] 端到端：`POST /campaigns/suggest-audience` with `{"campaign_type": "email", "description": "test"}` + auth header 返回 `{success: true, data: {segment_query: ...}}`（需要 #41 AI endpoint 已就绪，feature flag 打开）
- [ ] 降级路径：feature flag 关闭时调用上述 endpoint 返回 HTTP 403

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #41 AI endpoint 未就绪导致功能不可用 | 中 | 中 | Feature flag 默认关闭；按钮完全不渲染，用户无感知；可独立上线 |
| AI agent 返回格式变更导致 `suggest_audience` 解析报错 | 低 | 中 | `ai_agent_client.py` 用 `result.get("segment_query")` 防御性读取，缺失时返回空字符串；router 层 catch KeyError 返回 502 |
| 前端按钮误触导致意外 segment 覆盖 | 低 | 高 | 建议仅填充输入框，不自动选中；用户必须手动确认；配合 UI copy "Review before saving" |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/marketing_service.py src/services/ai_agent_client.py \
        src/api/routers/campaigns.py src/config/feature_flags.py \
        tests/unit/test_marketing_service.py
git commit -m "feat(campaigns): add AI audience suggestion button to Campaign Builder"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(campaigns): add AI audience suggestion (#534)" --body "Closes #534"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/services/sales_service.py L? — 类似 service 调用外部 HTTP endpoint 的现有模式>
- 父 issue / 关联：#62（父），#533（依赖 — AI agent endpoint），#41（AI endpoint wire target），#49（待验证 — 同批 AI 功能）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
