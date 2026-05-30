# AI · Add Chat with AI button and quick questions on Customer Detail

| 元数据 | 值 |
|---|---|
| Issue | #560 |
| 分类 | 10-customers |
| 优先级 | 推荐 |
| 工作量 | 2-3 工作日 |
| 依赖 | [AI Agent Framework #41](../90-frontend/0041-ai-agent-framework.md), [AI Integration Board #559](0559-ai-integration-core.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Users viewing a Customer Detail page today have no AI assistance built in. They must manually synthesize the data shown on the page to form a picture of the customer, and they must independently determine what to do next. This creates friction for sales and support reps who need fast, AI-generated guidance at the point of action. The AI Agent Framework (issue #41) will expose the endpoints needed to generate a customer summary and a suggested next action. This board delivers the frontend surface — a button and a quick-question dropdown — so users can consume those capabilities without leaving the CRM.

### 1.2 做完后

- **用户视角**：On every Customer Detail page a "Chat with AI" button appears. Clicking it opens a small dropdown with at least two options: "Summarize this customer" and "Suggest next action". Selecting an option triggers the AI call and displays the result in a modal or inline panel. The experience is self-contained — no navigation, no new tab.
- **开发者视角**：A new `ai_service_client` module is added to the service layer. It encapsulates all HTTP calls to the AI Agent endpoints (from issue #41). The Customer Detail component imports and uses this client. Error states (endpoint unavailable, slow response) are handled gracefully with user-facing messages.

### 1.3 不做什么（剔除）

- [ ] Any change to the AI Agent Framework itself — endpoints, prompt engineering, model selection are all handled in issue #41.
- [ ] General-purpose chat interface — only the two predefined quick-question flows are implemented.
- [ ] Backend ORM model additions or migrations — this is a frontend-only board.

### 1.4 关键 KPI

- `ruff check src/services/ai_service_client.py src/components/CustomerDetail.tsx` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_ai_service_client.py -v` → all passed
- `PYTHONPATH=src pytest tests/integration/test_customer_detail_ai_integration.py -v` → all passed
- `npm run lint -- --max-warnings 0` (or equivalent frontend lint command) → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/components/CustomerDetail.tsx` L? — 现有 Customer Detail 前端组件，确认文件路径和导出结构
TBD - 待验证：`src/services/` L? — 现有 service 层目录结构，确认模块组织方式
TBD - 待验证：AI Agent 端点路径 — issue #41 尚未完成，端点格式待确认

Issue #41 (AI Agent Framework) is the dependency that will expose two REST endpoints consumed by this board. Until #41 is complete this board cannot be wired to live endpoints.

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/components/CustomerDetail.tsx` — 添加 Chat with AI 按钮和下拉组件
  - TBD - 待验证：`src/app/customers/[id]/page.tsx` — 如果按钮在 page 层而非组件层添加
- 要建：
  - `src/services/ai_service_client.py` — 调用 AI Agent API 的 HTTP 客户端封装
  - `tests/unit/test_ai_service_client.py` — `ai_service_client` 单元测试
  - `tests/integration/test_customer_detail_ai_integration.py` — 端到端集成测试

### 2.3 缺什么

- [ ] "Chat with AI" 按钮 UI 组件
- [ ] 快速问题下拉菜单（"Summarize this customer" / "Suggest next action" 选项）
- [ ] AI 服务客户端模块 (`ai_service_client`)
- [ ] AI 响应展示 Modal/Inline panel
- [ ] 加载状态 UX
- [ ] 错误处理（端点不可用、超时、AI 返回错误）
- [ ] 占位符 / gracefully-degraded 状态（issue #41 未完成时的降级）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/ai_service_client.py` | HTTP 客户端，封装对 AI Agent 端点的调用（`summarize_customer` / `suggest_action`） |
| `tests/unit/test_ai_service_client.py` | `ai_service_client` 单元测试，mock HTTP 层 |
| `tests/integration/test_customer_detail_ai_integration.py` | 端到端集成测试，覆盖按钮 → API → 响应展示全链路 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/components/CustomerDetail.tsx` | 注入 Chat with AI 按钮、下拉菜单 Modal，调用 `ai_service_client` 方法并展示结果 |

### 3.3 新增能力

- **Service**：`ai_service_client.py` — `summarize_customer(customer_id: int, tenant_id: int) -> str` 和 `suggest_action(customer_id: int, tenant_id: int) -> str`
- **API endpoint（consumed, not built）**：`POST /ai/summarize-customer` 和 `POST /ai/suggest-action` — 由 issue #41 提供，本板仅消费
- **UI component**：Chat with AI 按钮 + 快速问题下拉菜单 + 响应展示 Modal
- **Error handling**：超时、HTTP 非 2xx、AI 服务不可用时展示用户友好错误信息

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `httpx.AsyncClient` 不选 `requests`**：后端是 FastAPI async 应用，httpx 与 async/await 原生配合，避免在 async def 中引入阻塞调用。
- **选快速问题预设菜单不选自由文本输入**：Issue 明确要求"quick-question dropdown"；自由文本聊天超出本板范围且对 AI Agent 端点设计有额外要求。
- **选 issue #41 完成后接入不选 mock/stub**：避免因接口设计不匹配导致返工；依赖明确后再接入可减少调试成本。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `httpx` | `>=0.25.0` | 要求 async client，原生支持 `AsyncClient`，与 FastAPI 生态兼容 |

### 4.3 兼容性约束

- 多租户：调用 AI 端点时必须在请求体或 header 中携带 `tenant_id`，由 `ai_service_client` 在封装层统一注入。
- Service 层（`ai_service_client`）返回 Python `str`，不调用 `.to_dict()`；序列化由 router 或直接由 HTTP response body 处理。
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`）；对于 AI 端点返回的非 2xx 或网络错误，封装为 `ValidationException("AI service unavailable")` 或 `ValidationException("AI request timeout")`。
- 前端组件必须兼容现有 Customer Detail 页面路由和权限模型（受 `require_auth` 中间件保护）。

### 4.4 已知坑

1. **Issue #41 端点尚未就绪，前端代码无法联调** → 规避：在 `ai_service_client` 中对所有 HTTP 调用添加 5s 超时，对 `httpx.HTTPStatusError` 捕获并抛出 `ValidationException`，使功能在端点就绪前不崩溃；用 pytest mock 隔离测试。
2. **httpx 默认不超时，可能导致请求挂起** → 规避：`httpx.AsyncClient(timeout=5.0)` 显式设置全局超时，超时抛 `httpx.TimeoutException`，捕获后转 `ValidationException("AI request timeout")`。
3. **AI Agent 端点响应格式不确定（JSON？纯文本？）** → 规避：在 `ai_service_client` 中先断言 `response.headers["content-type"]` 包含 `application/json`，解析为 `dict` 再取值；若格式不符抛 `ValidationException("Unexpected AI response format")`；待 #41 完成后按实际响应结构调整。

---

## 5. 实现步骤（按顺序）

### Step 1: Scaffold `ai_service_client.py` with stubs

Create the service module with two async methods that raise `NotImplementedError` until the endpoint URLs are known. This establishes the interface contract before the AI Agent endpoints exist.

```python
# src/services/ai_service_client.py
import httpx
from typing import Any

AI_AGENT_BASE_URL = "http://localhost:8000"  # overridden via env in tests

async def summarize_customer(
    customer_id: int,
    tenant_id: int,
    base_url: str = AI_AGENT_BASE_URL,
    timeout: float = 5.0,
) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url}/ai/summarize-customer",
            json={"customer_id": customer_id, "tenant_id": tenant_id},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("summary", str(data))
```

**完成判定**：`ruff check src/services/ai_service_client.py` → 0 errors

---

### Step 2: Wire "Chat with AI" button into Customer Detail component

TBD - 待验证：在 `src/components/CustomerDetail.tsx` 第 N 行附近添加按钮组件（根据现有 UI 框架选择 Button 组件）。

- 按钮文案："Chat with AI"
- 点击后展开下拉菜单，选项为：
  - "Summarize this customer" → 调用 `ai_service_client.summarize_customer`
  - "Suggest next action" → 调用 `ai_service_client.suggest_action`
- 选中后显示 Loading spinner，响应到达后展示 Modal

示例 UI 结构（伪 TypeScript）：

```tsx
// Placeholder — actual file path to be verified
const [aiOpen, setAiOpen] = useState(false);
const [aiLoading, setAiLoading] = useState(false);
const [aiResult, setAiResult] = useState<string | null>(null);

return (
  <>
    <Button onClick={() => setAiOpen(true)}>Chat with AI</Button>
    {aiOpen && (
      <AiQuickQuestionModal
        customerId={customer.id}
        tenantId={tenantId}
        onClose={() => { setAiOpen(false); setAiResult(null); }}
        onResult={setAiResult}
      />
    )}
  </>
);
```

**完成判定**：`npm run type-check` (or `tsc --noEmit`) → 0 type errors in `CustomerDetail.tsx`

---

### Step 3: Build `AiQuickQuestionModal` component

Create the Modal/Dropdown component:

- Props: `customerId`, `tenantId`, `onClose`, `onResult`
- Internal state: `selectedQuestion`, `loading`, `error`
- Two question buttons wired to service calls
- Renders AI response text when available
- Error state shows user-friendly message

**完成判定**：TBD - 待验证：组件文件存在且 `npm run lint -- src/components/AiQuickQuestionModal.tsx` → 0 errors

---

### Step 4: Connect `ai_service_client` to modal component

- Import `ai_service_client` in the modal component (backend-for-frontend call via internal HTTP or direct from component if same runtime)
- Wire "Summarize" → `summarize_customer(customerId, tenantId)`
- Wire "Suggest action" → `suggest_action(customerId, tenantId)`
- Display result string in modal body
- Catch `ValidationException` and surface as error state

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ai_service_client.py -v` → all passed

---

### Step 5: Write unit tests for `ai_service_client`

```python
# tests/unit/test_ai_service_client.py
import pytest
from unittest.mock import AsyncMock, patch
from src.services.ai_service_client import summarize_customer, suggest_action

@pytest.mark.asyncio
async def test_summarize_customer_returns_summary():
    with patch("httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = {"summary": "Enterprise customer, 3 open tickets"}
        mock_response.raise_for_status = AsyncMock()
        instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = instance

        result = await summarize_customer(customer_id=1, tenant_id=10)
        assert "Enterprise customer" in result
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_ai_service_client.py -v` → all passed

---

### Step 6: Write integration test for Customer Detail AI flow

```python
# tests/integration/test_customer_detail_ai_integration.py
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.integration
@pytest.mark.asyncio
async def test_ai_quick_question_integration():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Seed customer first
        resp = await client.post("/customers/", json={"name": "Acme Corp", "tenant_id": 1})
        customer_id = resp.json()["data"]["id"]
        # Call AI summarize endpoint (provided by issue #41)
        ai_resp = await client.post(
            "/ai/summarize-customer",
            json={"customer_id": customer_id, "tenant_id": 1},
        )
        assert ai_resp.status_code == 200
        assert "summary" in ai_resp.json()["data"]
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_customer_detail_ai_integration.py -v` → all passed

---

### Step 7: Lint and type-check all changed files

- `ruff check src/services/ai_service_client.py`
- `ruff check src/components/CustomerDetail.tsx` (TBD - 待验证)
- TBD - 待验证：`npm run lint` on frontend files

**完成判定**：All lint commands exit 0, all type-check commands exit 0

---

## 6. 验收

- [ ] `ruff check src/services/ai_service_client.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_ai_service_client.py -v` → all passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_customer_detail_ai_integration.py -v` → all passed
- [ ] TBD - 待验证：`npm run lint -- src/components/AiQuickQuestionModal.tsx` → 0 errors
- [ ] TBD - 待验证：`tsc --noEmit` on affected frontend files → 0 errors
- [ ] Manual verification: navigate to Customer Detail page → "Chat with AI" button visible; click → dropdown appears with both question options

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Issue #41 AI Agent endpoints have different request/response shapes than assumed | 中 | 中 | 在 `ai_service_client` 中添加 schema validation；将不匹配响应捕获为 `ValidationException`，前端显示"AI unavailable"，不阻塞页面加载 |
| Frontend file for Customer Detail not at expected path | 低 | 低 | 运行 `find . -name "CustomerDetail*" -o -name "customer*detail*" -o -name "*customer-detail*"` 确认实际路径后更新 §2.1 和 §5 Step 2 |
| AI API returns slow (>5s) causing timeout | 中 | 低 | 将超时错误展示为用户提示"AI is taking longer than expected — try again"；前端有重试按钮 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/ai_service_client.py tests/unit/test_ai_service_client.py tests/integration/test_customer_detail_ai_integration.py
git commit -m "feat(customers): add Chat with AI button and quick questions on Customer Detail"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(customers): Chat with AI button and quick questions on Customer Detail" --body "Closes #560"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：[`src/services/customer_service.py`](../../src/services/customer_service.py) — 现有 service 层模式参考（session 注入、异常抛出规范）
- 第三方文档：[httpx AsyncClient](https://www.python-httpx.org/async/) — async HTTP 客户端用法
- 父 issue / 关联：#53 (AI Integration epic), #559 (AI Integration core board), #41 (AI Agent Framework)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
