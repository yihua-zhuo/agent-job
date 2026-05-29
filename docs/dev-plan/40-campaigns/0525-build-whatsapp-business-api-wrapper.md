# Channels · WhatsApp Business API wrapper

| 元数据 | 值 |
|---|---|
| Issue | #525 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 推荐 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [0524-build-channel-base-abstraction](./0524-build-channel-base-abstraction.md) |
| 启用后赋能 | [板块名](../README.md) — #71（父 issue）后续各 channel 实现依赖此 wrapper |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM needs to send WhatsApp Business messages (text and media) to customers as part of multi-channel engagement. There is currently no WhatsApp integration at all — channel logic is mixed into business services with no abstraction. This wrapper establishes a clean, testable boundary between the Facebook Graph API and the rest of the CRM.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 channel wrapper。
- **开发者视角**：`from channels.whatsapp import WhatsAppClient` provides `send_message(to, body)` and `send_media(to, media_url, media_type)`. Credentials come from `WA_BUSINESS_TOKEN` and `WA_PHONE_NUMBER_ID` env vars. No DB, no service layer.

### 1.3 不做什么（剔除）

- [ ] **No DB writes** — this is a pure HTTP utility, not a service.
- [ ] **No service-layer integration** — wiring into `NotificationService` or campaign workflows belongs in a separate issue.
- [ ] **No retry / rate-limit backoff** — handled by caller if needed.
- [ ] **No multi-tenant logic** — `WhatsAppClient` is tenant-agnostic; the phone number ID differentiates accounts.

### 1.4 关键 KPI

- `ruff check src/channels/` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_whatsapp.py -v` → all passed (happy path + 4xx error cases)
- `python -c "from channels.whatsapp import WhatsAppClient, WhatsAppError"` → exit 0 (import is valid)

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - `TBD - 待验证：docs/dev-plan/40-campaigns/0524-build-channel-base-abstraction.md — 确认目录结构是否包含 src/channels/`
- 要建：
  - `src/channels/__init__.py` — `WhatsAppClient` + `WhatsAppError` public exports
  - `src/channels/whatsapp.py` — async wrapper, Facebook Graph API calls
  - `tests/unit/test_whatsapp.py` — unit tests with mocked `aiohttp`
  - `.env.example` — document `WA_BUSINESS_TOKEN` and `WA_PHONE_NUMBER_ID`

### 2.3 缺什么

- [ ] `src/channels/` directory and `WhatsAppClient` class do not exist
- [ ] No HTTP client for Facebook Graph API (`/v18.0/{phone_number_id}/messages`)
- [ ] No structured error mapping from Graph API 4xx responses to `WhatsAppError`
- [ ] No unit tests for the wrapper (coverage requirement from issue)

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/channels/__init__.py` | Public exports: `WhatsAppClient`, `WhatsAppError` |
| `src/channels/whatsapp.py` | Async WhatsApp Business Cloud API wrapper |
| `tests/unit/test_whatsapp.py` | Unit tests: happy path + 4xx error handling, mocked aiohttp |
| `.env.example` | Document `WA_BUSINESS_TOKEN` and `WA_PHONE_NUMBER_ID` |

### 3.2 修改文件

（无修改文件 — 纯新建模块）

### 3.3 新增能力

- **Class**：`WhatsAppClient(wa_token: str, phone_number_id: str, session: ClientSession)`
- **Method**：`send_message(to: str, body: str) -> dict`
- **Method**：`send_media(to: str, media_url: str, media_type: str) -> dict`
- **Exception**：`WhatsAppError` — raised on 4xx Graph API responses
- **Env vars**：`WA_BUSINESS_TOKEN`, `WA_PHONE_NUMBER_ID`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `aiohttp` 不选 `httpx`**：`httpx` adds async cancellation and timeout handling complexity not needed here; `aiohttp` is the de-facto standard async HTTP client in FastAPI ecosystems and matches the repo's async patterns.
- **选 `WhatsAppClient` takes `ClientSession` injected 不选 self-created session**：Caller (e.g. `NotificationService`) manages the `aiohttp` session lifecycle. This avoids creating a new TCP connection pool per message and allows proper connection reuse.
- **选自定义 `WhatsAppError` 不选 `httpx.HTTPStatusError`**：`WhatsAppError` is a domain-specific exception that cleanly separates channel-layer errors from HTTP library internals. Callers catch one known type without importing `aiohttp`.

### 4.2 版本约束

（无新增 Python 依赖 — `aiohttp` is already used elsewhere in the project; verify with `grep -r "aiohttp" pyproject.toml requirements.txt` if needed）

### 4.3 兼容性约束

- `WhatsAppClient` must be instantiated with a live `aiohttp.ClientSession`; do not create one inside the class `__init__`
- `send_message` / `send_media` are `async def`; callers must `await` them
- `WhatsAppError` message field should include the Graph API `error.message` for debugging
- Do NOT call `session.close()` inside `WhatsAppClient` — lifecycle is caller's responsibility

### 4.4 已知坑

1. **Graph API `400` (Invalid phone number format) vs `403` (phone not in allowed list)** → both are `WhatsAppError` subclasses with distinct `error_code` attributes; test both cases separately
2. **`aiohttp` response.json() raises `ContentTypeError` on non-JSON bodies** → guard with `resp.content_type.startswith('application/json')` before calling `.json()`; on unexpected HTML error pages, raise `WhatsAppError` with raw text in message

---

## 5. 实现步骤（按顺序）

### Step 1: Create `src/channels/` directory and `__init__.py`

Create the channels package and its public exports so the module is importable before writing implementation.

操作：
- a) Create `src/channels/__init__.py` with exports: `from .whatsapp import WhatsAppClient, WhatsAppError`
- b) Create `src/channels/whatsapp.py` with stub class + import block for `aiohttp`

```python
# src/channels/__init__.py
from .whatsapp import WhatsAppClient, WhatsAppError

__all__ = ["WhatsAppClient", "WhatsAppError"]
```

```python
# src/channels/whatsapp.py (stub)
import os
from dataclasses import dataclass
import aiohttp

@dataclass
class WhatsAppError(Exception):
    message: str
    error_code: int | None = None

class WhatsAppClient:
    def __init__(self, wa_token: str, phone_number_id: str, session: aiohttp.ClientSession):
        self.wa_token = wa_token
        self.phone_number_id = phone_number_id
        self.session = session
```

**完成判定**：`python -c "from channels.whatsapp import WhatsAppClient, WhatsAppError; print('import ok')"` → exit 0

### Step 2: Implement `send_message(to, body)`

Call `POST https://graph.facebook.com/v18.0/{phone_number_id}/messages` with the WhatsApp message payload. Raise `WhatsAppError` on non-2xx response.

操作：
- a) Build headers: `Authorization: Bearer {wa_token}`, `Content-Type: application/json`
- b) Build payload dict with `messaging_product: "whatsapp"`, `to`, `type: "text"`, `text: {"body": body}`
- c) `POST` to `f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"`
- d) If `resp.status >= 400`: parse JSON error body, raise `WhatsAppError(message, error_code)`
- e) Return `await resp.json()`

```python
async def send_message(self, to: str, body: str) -> dict:
    url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {self.wa_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with self.session.post(url, headers=headers, json=payload) as resp:
        if resp.status >= 400:
            body_json = await resp.json() if resp.content_type.startswith("application/json") else {}
            err = body_json.get("error", {})
            raise WhatsAppError(err.get("message", resp.text), err.get("code"))
        return await resp.json()
```

**完成判定**：`PYTHONPATH=src ruff check src/channels/whatsapp.py` → 0 errors

### Step 3: Implement `send_media(to, media_url, media_type)`

Similar to `send_message` but with `type: "image"` (or audio/video) and a media payload instead of text. Media type is validated (must be one of `image`, `audio`, `video`, `document`, `sticker`).

操作：
- a) Validate `media_type` against allowed list (`image`, `audio`, `video`, `document`, `sticker`); raise `ValueError` if invalid
- b) Build payload with `type: media_type`, `recipient_type: "individual"`, `to`, and `media: {"link": media_url}`
- c) Same response handling as `send_message`

```python
ALLOWED_MEDIA_TYPES = {"image", "audio", "video", "document", "sticker"}

async def send_media(self, to: str, media_url: str, media_type: str) -> dict:
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise ValueError(f"media_type must be one of {ALLOWED_MEDIA_TYPES}, got {media_type!r}")
    url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {self.wa_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": media_type,
        media_type: {"link": media_url},
    }
    async with self.session.post(url, headers=headers, json=payload) as resp:
        if resp.status >= 400:
            body_json = await resp.json() if resp.content_type.startswith("application/json") else {}
            err = body_json.get("error", {})
            raise WhatsAppError(err.get("message", resp.text), err.get("code"))
        return await resp.json()
```

**完成判定**：`PYTHONPATH=src ruff check src/channels/whatsapp.py` → 0 errors

### Step 4: Write unit tests

Test happy path (200 OK) and 4xx error handling (400, 403) with mocked `aiohttp` responses using `pytest-asyncio` and `aiohttp.test_utils`.

操作：
- a) `tests/unit/test_whatsapp.py` — fixture `mock_aiohttp_session(responses: list)` using `aiohttp.test_utils.AioHTTPTestCase` or a manual `MockSession` approach (matching repo's unit test mock patterns)
- b) Test `send_message` → 200 response, return value matches expected keys
- c) Test `send_message` → 400 Graph API error, raises `WhatsAppError` with correct message + error_code
- d) Test `send_message` → 403 unauthorized, raises `WhatsAppError`
- e) Test `send_media` → happy path
- f) Test `send_media` → invalid `media_type` raises `ValueError`
- g) Test `send_media` → 400 error raises `WhatsAppError`

```python
# tests/unit/test_whatsapp.py (skeleton — full implementation in test file)
import pytest
from unittest.mock import AsyncMock, MagicMock
import aiohttp

# from channels.whatsapp import WhatsAppClient, WhatsAppError, ALLOWED_MEDIA_TYPES

@pytest.fixture
def mock_session():
    session = MagicMock(spec=aiohttp.ClientSession)
    return session

@pytest.fixture
def client(mock_session):
    return WhatsAppClient("test-token", "123456789", mock_session)

@pytest.mark.asyncio
async def test_send_message_happy_path(client, mock_session):
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"messages": [{"id": "wamid.xxx"}]})
    mock_response.content_type = "application/json"
    mock_session.post.return_value.__aenter__.return_value = mock_response

    result = await client.send_message("+15550000000", "Hello!")
    assert result["messages"][0]["id"].startswith("wamid.")

@pytest.mark.asyncio
async def test_send_message_graph_error(client, mock_session):
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.json = AsyncMock(return_value={"error": {"message": "Invalid phone number", "code": 131026}})
    mock_response.content_type = "application/json"
    mock_session.post.return_value.__aenter__.return_value = mock_response

    with pytest.raises(WhatsAppError) as exc:
        await client.send_message("+1invalid", "Hi")
    assert "Invalid phone number" in str(exc.value.message)

@pytest.mark.asyncio
async def test_send_media_invalid_type(client):
    with pytest.raises(ValueError) as exc:
        await client.send_media("+15550000000", "https://example.com/file.exe", "executable")
    assert "media_type must be one of" in str(exc.value)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_whatsapp.py -v` → all passed

### Step 5: Document env vars in `.env.example`

操作：
- a) Append to `.env.example`:

```
# WhatsApp Business API
WA_BUSINESS_TOKEN=your_whatsapp_business_access_token
WA_PHONE_NUMBER_ID=your_phone_number_id
```

**完成判定**：`grep "WA_BUSINESS_TOKEN\|WA_PHONE_NUMBER_ID" .env.example` → 2 lines found

---

## 6. 验收

- [ ] `ruff check src/channels/` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_whatsapp.py -v` → all passed (happy path + 3 error cases minimum)
- [ ] `python -c "from channels.whatsapp import WhatsAppClient, WhatsAppError; print('ok')"` → exit 0
- [ ] `grep "WA_BUSINESS_TOKEN\|WA_PHONE_NUMBER_ID" .env.example` → 2 lines

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Graph API version `v18.0` is deprecated by Meta before merge | 低 | 中 | Bump URL to `v21.0` in `send_message` / `send_media`; this is a one-line change with no downstream impact |
| `aiohttp` is not in `pyproject.toml` / `requirements.txt` | 低 | 高 | Add `aiohttp>=3.9.0` to `[project.dependencies]`; confirm with `pip show aiohttp` first |
| Tests use wrong mock approach and fail on CI | 中 | 中 | Match the repo's unit test mock pattern: `MagicMock` + `AsyncMock` for `aiohttp.ClientSession`, no `pytest-aiohttp` fixtures needed |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/channels/ tests/unit/test_whatsapp.py .env.example
git commit -m "feat(channels): add WhatsApp Business API wrapper

Implements send_message and send_media using Facebook Graph API.
Credentials via WA_BUSINESS_TOKEN and WA_PHONE_NUMBER_ID env vars.
Unit tests cover happy path and 4xx error handling.
Closes #525"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(channels): WhatsApp Business API wrapper" --body "Closes #525"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 父 issue / 关联：#71
- 依赖板块：#524
- 第三方文档：[WhatsApp Business Platform — Send Messages API](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages)
- 第三方文档：[Meta Graph API Error Codes](https://developers.facebook.com/docs/graph-api/error-reference/)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
