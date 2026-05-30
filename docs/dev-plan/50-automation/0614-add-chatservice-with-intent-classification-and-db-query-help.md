# 自动化 · Add ChatService with intent classification and DB query helpers

| 元数据 | 值 |
|---|---|
| Issue | #614 |
| 分类 | [50-automation](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待验证：Issue #613 的文件路径（chat-router + session-history 端点） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 CRM 系统没有统一的聊天/对话服务层。客服、销售等模块各自的查询逻辑分散，无法根据用户自然语言意图路由到对应的数据查询。Issue #614 需要先建立 `ChatService` 作为基础设施，提供基于关键词/正则的意图识别和标准化 DB 查询接口，为后续 #613 的对话路由和会话历史功能奠定基础。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 Service 改动
- **开发者视角**：`ChatService` 可接收用户消息文本，返回结构化意图（`customer_lookup | sales_summary | ticket_query | general`）并附带查询结果；可调用 `query_customers()` / `query_opportunities()` / `query_tickets()` 进行多表查询，所有结果按 `tenant_id` 隔离

### 1.3 不做什么（剔除）

- [ ] 不实现 LLM/外部模型调用，意图识别完全基于本地关键词/正则
- [ ] 不新增 API Router 或 HTTP 端点（Router 在 #613 中处理）
- [ ] 不新增数据库表或 Migration（无新 ORM model）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → `≥ 8 passed`
- `ruff check src/services/chat_service.py` → 0 errors
- `mypy src/services/chat_service.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：无
- 要建：
  - `src/services/chat_service.py` — ChatService（含意图分类 + DB 查询 helpers）
  - `tests/unit/test_chat_service.py` — 单元测试覆盖 4 种意图 + 3 种 helper + 边界错误

### 2.3 缺什么

- [ ] 无 `ChatService` 类，无法对用户消息做意图分类
- [ ] 无统一的 `query_customers()` / `query_opportunities()` / `query_tickets()` 查询入口（各模块分散或缺失）
- [ ] 新 Service 必须符合本仓库 Service 层规范（session 必传、raise AppException、返回 dict 非 ORM）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/chat_service.py` | ChatService — 意图分类（关键词/正则）+ 三个 DB 查询 helper |
| `tests/unit/test_chat_service.py` | 单元测试 — 覆盖所有意图路径 + helper 返回 + 异常场景 |

### 3.2 修改文件

（无修改文件）

### 3.3 新增能力

- **Service class**：`ChatService(session: AsyncSession)` — 构造器签名符合本仓库规范
- **Intent classification**：`classify_intent(text: str) -> Literal["customer_lookup", "sales_summary", "ticket_query", "general"]` — 基于关键词/正则，无外部 LLM
- **DB query helpers**：
  - `query_customers(tenant_id: int, keyword: str | None = None, limit: int = 10) -> list[dict]`
  - `query_opportunities(tenant_id: int, keyword: str | None = None, limit: int = 10) -> list[dict]`
  - `query_tickets(tenant_id: int, keyword: str | None = None, status: str | None = None, limit: int = 10) -> list[dict]`
- **异常**：`NotFoundException` — 当 helper 查询不到结果时；`ValidationException` — 当传入非法参数时
- **返回值约定**：所有 helper 返回 `list[dict]`，每个 dict 为标准化 flat 结构（含 `id`、`tenant_id` 等公共字段）；Service 层不调用 `.to_dict()`（调用方为 ORM 对象时需外部转换）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **意图识别选关键词+正则而不选 LLM**：当前阶段不需要外部模型依赖，关键词/正则方案实现简单、零延迟、测试确定性高，适合作为 MVP 基础设施。后续如需升级可替换 `classify_intent` 实现而无需改动调用方。
- **三个 helper 各自独立而非共用查询模板**：Customer / Opportunity / Ticket 三张表结构不同，字段名不一致（`name` vs `subject` vs `customer_id`），共模会引入不必要的适配逻辑，维护成本高于各自独立实现。

### 4.2 版本约束

（无新依赖引入）

### 4.3 兼容性约束

- 构造器：`ChatService.__init__(self, session: AsyncSession)` — session 必传，**禁止** `session=None` 默认值
- 多租户：所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- 返回值：helper 返回 `list[dict]`，不返回 ORM 对象，不调用 `.to_dict()`
- 异常：使用 `NotFoundException`（查无结果时）和 `ValidationException`（非法参数时），不返回 `ApiResponse.error()` 形式的 dict
- 模块导入：`from services.chat_service import ChatService`（PYTHONPATH=src）

### 4.4 已知坑

1. **关键词重叠导致意图误判** → 规避：正则匹配优先于关键词匹配（先检查正则规则列表，再检查关键词列表），且每类意图的正则/关键词集合互斥、无交集
2. **大 keyword 查询击穿 DB** → 规避：所有 helper 有 `limit` 参数（默认 10），即使 keyword 为空也限制返回条数，防止 SELECT 无 LIMIT 导致内存问题
3. **ILIKE 注入风险（特殊字符 `%\\_`）** → 规避：查询前对 keyword 做转义，`\` → `\\`，`%` → `\%`，`_` → `\_`，与 `CustomerService.search_customers` 保持一致

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 `src/services/chat_service.py` 骨架（类结构 + 构造器）

创建 `src/services/chat_service.py`，定义 `ChatService` 类、构造器、占位 method 签名（`classify_intent` + 三个 helper + `handle_message`）。

```python
"""Chat service — intent classification and DB query helpers."""

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from pkg.errors.app_exceptions import NotFoundException, ValidationException

Intent = Literal["customer_lookup", "sales_summary", "ticket_query", "general"]


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        if session is None:
            raise ValidationException("ChatService requires a session")
        self.session = session

    async def classify_intent(self, text: str) -> Intent:
        ...

    async def query_customers(self, tenant_id: int, keyword: str | None = None, limit: int = 10) -> list[dict]:
        ...

    async def query_opportunities(self, tenant_id: int, keyword: str | None = None, limit: int = 10) -> list[dict]:
        ...

    async def query_tickets(self, tenant_id: int, keyword: str | None = None, status: str | None = None, limit: int = 10) -> list[dict]:
        ...

    async def handle_message(self, text: str, tenant_id: int) -> dict:
        """Main entry: classify intent + dispatch to appropriate helper, return structured result."""
        ...
```

**完成判定**：`ruff check src/services/chat_service.py` → 0 errors

---

### Step 2: 实现 `classify_intent`（关键词 + 正则，无 LLM）

实现意图分类逻辑：

```python
import re

# 正则规则（优先级高，按顺序逐一匹配）
_INTENT_REGEX_PATTERNS: list[tuple[Intent, re.Pattern, str]] = [
    ("customer_lookup", re.compile(r"\b(customer|client|customer id|customer #)\b", re.I), "customer_lookup"),
    ("ticket_query",    re.compile(r"\b(ticket|support|issue|bug|error)\b", re.I), "ticket_query"),
    ("sales_summary",   re.compile(r"\b(deal|opportunity|forecast|revenue|sales|pipeline)\b", re.I), "sales_summary"),
]

# 关键词兜底（正则未匹配时）
_INTENT_KEYWORD_MAP: dict[Intent, list[str]] = {
    "customer_lookup": ["customer lookup", "find customer", "search customer", "客户查询"],
    "sales_summary":   ["sales summary", "deal summary", "pipeline report", "销售摘要"],
    "ticket_query":    ["ticket status", "open tickets", "my tickets", "工单查询"],
    "general":          [],  # 无任何匹配时默认 general
}

async def classify_intent(self, text: str) -> Intent:
    if not text or not text.strip():
        raise ValidationException("text cannot be empty")
    lower = text.lower().strip()
    # 1. 正则优先
    for intent, pattern, _ in _INTENT_REGEX_PATTERNS:
        if pattern.search(lower):
            return intent
    # 2. 关键词兜底（最长匹配优先）
    best: Intent = "general"
    best_len = 0
    for intent, keywords in _INTENT_KEYWORD_MAP.items():
        for kw in keywords:
            if kw in lower and len(kw) > best_len:
                best = intent
                best_len = len(kw)
    return best
```

正则规则顺序：customer_lookup → ticket_query → sales_summary（互斥，匹配即返回）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_chat_service.py -v -k classify` → 全部 passed

---

### Step 3: 实现 `query_customers`（tenant_id + ILIKE + limit）

```python
async def query_customers(self, tenant_id: int, keyword: str | None = None, limit: int = 10) -> list[dict]:
    if limit <= 0 or limit > 200:
        raise ValidationException("limit must be 1-200")
    from sqlalchemy import and_, or_, select
    from db.models.customer import CustomerModel

    conditions = [CustomerModel.tenant_id == tenant_id]
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        kw = f"%{escaped}%"
        conditions.append(
            or_(
                CustomerModel.name.ilike(kw, escape="\\"),
                CustomerModel.email.ilike(kw, escape="\\"),
            )
        )
    result = await self.session.execute(
        select(CustomerModel)
        .where(and_(*conditions))
        .order_by(CustomerModel.created_at.desc())
        .limit(limit)
    )
    return [r.to_dict() for r in result.scalars().all()]
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_chat_service.py -v -k customers` → 全部 passed

---

### Step 4: 实现 `query_opportunities`（tenant_id + ILIKE + limit）

```python
async def query_opportunities(self, tenant_id: int, keyword: str | None = None, limit: int = 10) -> list[dict]:
    if limit <= 0 or limit > 200:
        raise ValidationException("limit must be 1-200")
    from sqlalchemy import and_, or_, select
    from db.models.opportunity import OpportunityModel

    conditions = [OpportunityModel.tenant_id == tenant_id]
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        kw = f"%{escaped}%"
        conditions.append(
            or_(
                OpportunityModel.name.ilike(kw, escape="\\"),
                OpportunityModel.customer_id.is_(None),  # fallback — match all if no keyword
            )
        )
        # If keyword given, match on name OR on a bare integer match against customer_id
        conditions.pop()  # remove bare customer_id.is_(None) stub; use proper OR below
        conditions.append(
            or_(
                OpportunityModel.name.ilike(kw, escape="\\"),
            )
        )
        if keyword.isdigit():
            conditions.append(OpportunityModel.customer_id == int(keyword))

    result = await self.session.execute(
        select(OpportunityModel)
        .where(and_(*conditions))
        .order_by(OpportunityModel.created_at.desc())
        .limit(limit)
    )
    return [r.to_dict() for r in result.scalars().all()]
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_chat_service.py -v -k opportunities` → 全部 passed

---

### Step 5: 实现 `query_tickets`（tenant_id + keyword + status + limit）

```python
async def query_tickets(self, tenant_id: int, keyword: str | None = None, status: str | None = None, limit: int = 10) -> list[dict]:
    if limit <= 0 or limit > 200:
        raise ValidationException("limit must be 1-200")
    from sqlalchemy import and_, or_, select
    from db.models.ticket import TicketModel

    conditions = [TicketModel.tenant_id == tenant_id]
    if status:
        conditions.append(TicketModel.status == status)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        kw = f"%{escaped}%"
        conditions.append(
            or_(
                TicketModel.subject.ilike(kw, escape="\\"),
                TicketModel.description.ilike(kw, escape="\\"),
            )
        )

    result = await self.session.execute(
        select(TicketModel)
        .where(and_(*conditions))
        .order_by(TicketModel.created_at.desc())
        .limit(limit)
    )
    return [r.to_dict() for r in result.scalars().all()]
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_chat_service.py -v -k tickets` → 全部 passed

---

### Step 6: 实现 `handle_message` 并完成最终检查

```python
async def handle_message(self, text: str, tenant_id: int) -> dict:
    """Classify intent and dispatch to appropriate helper.

    Returns:
        {
            "intent": str,
            "query_results": list[dict] | None,
            "error": str | None
        }
    """
    if not text:
        return {"intent": "general", "query_results": None, "error": "empty message"}
    intent = await self.classify_intent(text)
    results: list[dict] | None = None
    error: str | None = None
    try:
        if intent == "customer_lookup":
            results = await self.query_customers(tenant_id, keyword=text, limit=10)
        elif intent == "sales_summary":
            results = await self.query_opportunities(tenant_id, keyword=text, limit=10)
        elif intent == "ticket_query":
            results = await self.query_tickets(tenant_id, keyword=text, limit=10)
        # general: no DB query
    except NotFoundException as e:
        error = str(e.detail)
    except ValidationException as e:
        error = str(e.detail)
    return {"intent": intent, "query_results": results, "error": error}
```

最终 lint + type check：

**完成判定**：`ruff check src/services/chat_service.py && mypy src/services/chat_service.py` → 0 errors / 0 errors

---

## 6. 验收

- [ ] `ruff check src/services/chat_service.py` → 0 errors
- [ ] `mypy src/services/chat_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_chat_service.py -v` → `≥ 8 passed`
- [ ] `PYTHONPATH=src python -c "from services.chat_service import ChatService; print('import ok')"` → `import ok`（无运行时错误）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 意图关键词覆盖不足导致 `general` 误判率过高 | 中 | 中 | `classify_intent` 独立可测试，后续可直接替换为规则权重或 LLM，无需改动 `handle_message` |
| `limit` 参数不传或传 0 导致异常 | 低 | 中 | helper 内有 `ValidationException` 保护，调用方不传 limit 时默认为 10（安全默认值） |
| 多租户隔离疏漏（漏写 `tenant_id` 过滤） | 低 | 高 | 所有 SQL 都经过 `tenant_id` 条件过滤；集成测试覆盖多租户场景 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/chat_service.py tests/unit/test_chat_service.py
git commit -m "feat(chat): add ChatService with intent classification and DB query helpers

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(chat): ChatService with intent classification and DB query helpers" --body "Closes #614

- classify_intent(): keyword + regex, returns customer_lookup | sales_summary | ticket_query | general
- query_customers / query_opportunities / query_tickets: all filter by tenant_id, ILIKE with limit
- handle_message(): orchestrates classification + dispatch

🤖 Generated with [Claude Code](https://claude.com/claude-code)""
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../../src/services/customer_service.py) — Service 层规范（session 必传、raise AppException、ORM 返回）
- 同类参考实现：[`src/services/ticket_service.py`](../../../src/services/ticket_service.py) — `list_tickets` + `get_customer_tickets` 参考，tenant_id 过滤模式相同
- 父 issue / 关联：#43（父）, #613（下游 — 依赖本板块完成）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
