# RecommendationService LLM · Wire LLM call into get_recommendations

| 元数据 | 值 |
|---|---|
| Issue | #812 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | #811 (AIAgentService with `call_recommendation_llm` must be merged first) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #600 (LLM-driven sales recommendations) introduced the high-level flow but the concrete `RecommendationService.get_recommendations()` entry point still lacks the LLM integration. Without this wiring, the recommendations router returns nothing actionable, and downstream consumers (UI, analytics) cannot surface AI-generated next-action suggestions. This issue is a hard dependency for the unit/integration test board that covers the full LLM recommendation pipeline.

### 1.2 做完后

- **用户视角**：销售用户在 opportunity 详情页会获得由 LLM 生成的 `next_action`、`confidence`（0-1）、`reasons` 列表和 `similar_deals` 列表，所有内容由租户隔离、按 opportunity 持久化。
- **开发者视角**：`RecommendationService.get_recommendations(opportunity_id, tenant_id)` 返回一个完整的 `RecommendationModel` ORM 对象；调用方可直接 `.to_dict()` 序列化。`LLMRecommendationPayload` 暴露为可复用的 Pydantic schema，其他 LLM 流也可复用。`AIAgentService` 通过构造函数注入，便于在测试中替换。

### 1.3 不做什么（剔除）

- [ ] 不实现 LLM 调用的具体 transport / retry / token-budget 逻辑（属于 #811 范围）
- [ ] 不在 service 层处理 HTTP/JSON 序列化（由 router 负责）
- [ ] 不改动 `opportunities` 或 `deals` 表结构
- [ ] 不引入新的 ORM 字段到 `RecommendationModel` 之外
- [ ] 不实现异步/批量调用；本板块只覆盖同步单次 opportunity 路径

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → ≥ 6 passed
- `ruff check src/services/recommendation_service.py` → 0 errors
- `ruff check src/api/routers/recommendations.py` → 0 errors（如有 router 改动）
- 服务方法在 mock LLM 抛错时必须抛 `ValidationException`，**不**返回 dict
- 服务方法在拿到非法 LLM payload 时必须抛 `ValidationException`，**不**吞掉错误
- `RecommendationModel` 行在 `commit()` 之后必须可被 `refresh()` 拿到自增 ID

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/recommendation_service.py` 是否已存在以及其 `get_recommendations` 当前签名/实现 — grep 关键字：`def get_recommendations`、`LLMRecommendationPayload`、`AIAgentService`

TBD - 待验证：`RecommendationModel` ORM 类是否已存在及其字段（`tenant_id`、`opportunity_id`、`next_action`、`confidence`、`reasons`、`similar_deals`、`created_at`）— grep 路径：`src/db/models/`

TBD - 待验证：`src/api/routers/recommendations.py` 当前是否已注册 `GET /recommendations/opportunities/{opportunity_id}` — grep 关键字：`recommendations` 在 `src/api/routers/` 下

TBD - 待验证：`AIAgentService.call_recommendation_llm` 的精确签名（输入类型是 `str` 还是 `Prompt` dataclass）— 来源：#811 合并后的代码

### 2.2 涉及文件清单

- 要改：
  - [`src/services/recommendation_service.py`](../../../src/services/recommendation_service.py) — 注入 `AIAgentService`、定义 `LLMRecommendationPayload`、改写 `get_recommendations` 加入 prompt + LLM call + 持久化
  - TBD - 待验证：`src/api/routers/recommendations.py`（如已存在） — 确保 router 调用的是新签名
  - TBD - 待验证：`tests/unit/test_recommendation_service.py`（如已存在） — 补充 mock `AIAgentService` 的测试
- 要建：
  - TBD - 待验证：`tests/unit/test_recommendation_service.py`（如不存在则新建）— 覆盖新流程
  - TBD - 待验证：`tests/integration/test_recommendation_service_integration.py`（可选，取决于 #814 范围是否已包含）

### 2.3 缺什么

- [ ] `LLMRecommendationPayload` Pydantic model：定义 `next_action: str`、`confidence: float` (0-1)、`reasons: list[str]`、`similar_deals: list[dict]` 字段与校验
- [ ] `RecommendationService.__init__` 增加 `ai_agent: AIAgentService` 强类型参数（no default）
- [ ] `RecommendationService.get_recommendations` 的真实实现：fetch opportunity → fetch top 5 closed-won deals → `_build_prompt()` → `ai_agent.call_recommendation_llm(prompt)` → Pydantic 校验 → 持久化 `RecommendationModel` → `commit()` → `refresh()` → 返回 ORM 对象
- [ ] `_build_prompt(opportunity, similar_deals) -> str` 私有方法，构造稳定的 prompt 模板
- [ ] Opportunity 不存在时的 `NotFoundException` 处理
- [ ] LLM 返回非法 payload 时的 `ValidationException` 处理
- [ ] 租户隔离：所有 SQL 过滤必须包含 `tenant_id`

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| TBD - 待验证：`tests/unit/test_recommendation_service.py`（如不存在） | 单元测试：mock `AIAgentService` + mock DB session 覆盖 LLM 正常流、校验失败流、opportunity 不存在流 |
| TBD - 待验证：`src/services/recommendation_service.py` 内的 `LLMRecommendationPayload`（同文件内） | Pydantic schema：LLM 响应结构 + 字段约束 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/recommendation_service.py`](../../../src/services/recommendation_service.py) | • 在文件顶部 import `AIAgentService`（来自 `src/services/ai_agent_service.py`，由 #811 提供）<br>• 定义 `LLMRecommendationPayload(BaseModel)`<br>• `__init__(self, session, ai_agent)` 增加 `ai_agent` 必填参数<br>• `get_recommendations(opportunity_id, tenant_id)` 重写：fetch opportunity → fetch top 5 closed-won deals → `_build_prompt()` → `ai_agent.call_recommendation_llm(prompt)` → `LLMRecommendationPayload.model_validate(raw)` → 构造 `RecommendationModel` → `session.add()` + `await session.commit()` + `await session.refresh()` → 返回 ORM 对象<br>• 新增私有方法 `_build_prompt(opportunity, similar_deals) -> str`<br>• 任何错误路径抛 `NotFoundException` / `ValidationException` |
| TBD - 待验证：`src/api/routers/recommendations.py` | 确保 router 接受 `AIAgentService` 依赖并构造 `RecommendationService(session, ai_agent)`；调用 `entity.to_dict()` 序列化后包装为标准 envelope |

### 3.3 新增能力

- **Service method**：`RecommendationService.get_recommendations(self, opportunity_id: int, tenant_id: int) -> RecommendationModel`
- **Service constructor**：`RecommendationService(session: AsyncSession, ai_agent: AIAgentService)` — 两个必填位置参数，无默认值
- **Pydantic schema**：`LLMRecommendationPayload` 含 `next_action: str`、`confidence: float` (Field ge=0, le=1)、`reasons: list[str]` (min_length=1)、`similar_deals: list[dict]`
- **Private helper**：`RecommendationService._build_prompt(opportunity, similar_deals) -> str` — 返回稳定的 prompt 字符串
- **API endpoint**：TBD - 待验证：现有 router 路径（预期 `GET /recommendations/opportunities/{opportunity_id}`）返回 `{"success": true, "data": {...}}`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Pydantic 校验在 service 层做，不在 router 层做** — 选 Pydantic 而非手写 dict 校验，因为：(1) LLM 响应结构是契约，跨多个 endpoint 复用；(2) Pydantic 的 `model_validate` 在失败时直接抛 `ValidationError`，可被 service 包成项目标准的 `ValidationException`
- **AIAgentService 通过构造函数注入** — 选 DI 而非全局单例/模块级变量，因为：(1) 单元测试需要 mock 替换；(2) 与本仓库 `Service(session)` 既有模式一致，便于代码审查
- **Top 5 closed-won deals 来源于同租户历史** — 选 SQL 查询而非全表 in-memory 过滤，因为：(1) tenant 数据规模未知，in-memory 不可扩展；(2) 已有 `tenant_id` 索引可直接利用
- **Prompt 构造放在 `_build_prompt` 私有方法** — 选私有方法而非 inline 拼接，因为：(1) 后续可能需要 A/B 不同 prompt 模板；(2) 便于单元测试单独验证 prompt 格式

### 4.2 版本约束

<!-- 本板块不引入新依赖（使用 Pydantic、AIAgentService 均已存在或由 #811 引入） -->
不引入新依赖。

### 4.3 兼容性约束

- 多租户：opportunity 查询、deals 查询、RecommendationModel INSERT 都必须 `WHERE tenant_id = :tenant_id`
- Service 返回 `RecommendationModel` ORM 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException`），**不**返回 `ApiResponse.error()` 也不返回裸 dict
- `session: AsyncSession` 在 `__init__` 中无默认值；`ai_agent: AIAgentService` 同样无默认值
- router 注入 session 必须用 `session: AsyncSession = Depends(get_db)`，**不**用 `async with get_db() as session:`
- `AIAgentService` 必须从 #811 提供的路径 import（路径待 #811 合并后确认）
- 既有 `RecommendationService` 公开 API（其他方法、属性）保持不变

### 4.4 已知坑

1. **Pydantic `ValidationError` 不会自动转成 `ValidationException`** → 规避：在 service 内 `try/except pydantic.ValidationError`，捕获后 `raise ValidationException(detail=str(e))` from e
2. **`session.commit()` 后 ORM 对象可能已 expire，`refresh()` 前访问属性会触发隐式 IO** → 规避：严格 `await session.refresh(obj)` 后再 `return obj`
3. **LLM 返回 JSON 字符串而非 dict** → 规避：在 `call_recommendation_llm` 的 wrapper 层（#811 范围）解析；本板块假设返回值已是 dict-like；若实际是 str 则 `_build_prompt` 同模块加一层 `json.loads`，并在测试中覆盖 str 输入
4. **`RecommendationModel` 表没有 `tenant_id` 索引** → 规避：TBD - 待验证：现有迁移是否有索引；若无则在本次或后续 migration 中加 `CREATE INDEX ... ON recommendations (tenant_id)`
5. **Mock DB session 不支持 `flush()` / `refresh()` 默认行为** → 规避：单元测试的 mock handler 必须显式实现 `refresh` 语义（参考 `tests/unit/conftest.py` 中既有的 `MockResult` 模式）；TBD - 待验证：现有 mock 是否覆盖 refresh
6. **Alembic autogen 倾向把 `JSONB` 写成 `JSON`，把 `TIMESTAMPTZ` 写成 `DateTime`** → 规避：本板块不新增表（推荐表已在），但若新增字段需 migration，手动确认 autogen 输出的列类型

---

## 5. 实现步骤（按顺序）

### Step 1: 验证依赖与现有代码定位

确认 #811 已合并、`AIAgentService.call_recommendation_llm` 可用，并定位 `RecommendationService` / `RecommendationModel` 现有实现。

操作：
- a) `git log --oneline | head -20` 确认 #811 已在 master
- b) `grep -rn "class AIAgentService" src/` 定位 service 类路径
- c) `grep -rn "call_recommendation_llm" src/` 确认方法签名
- d) `grep -rn "class RecommendationService" src/` 定位 service 文件
- e) `grep -rn "class RecommendationModel" src/db/models/` 定位 ORM 模型
- f) `cat src/services/recommendation_service.py` 读取当前 `get_recommendations` 签名

**完成判定**：上述 grep 均有唯一定位结果；`AIAgentService` import 路径已记录

### Step 2: 定义 `LLMRecommendationPayload` Pydantic model

在 [`src/services/recommendation_service.py`](../../../src/services/recommendation_service.py) 顶部添加 Pydantic schema。

操作：
- a) 在 import 区增加 `from pydantic import BaseModel, Field`
- b) 在 `RecommendationService` class 之前定义：

```python
class LLMRecommendationPayload(BaseModel):
    next_action: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(min_length=1)
    similar_deals: list[dict] = Field(default_factory=list)
```

**完成判定**：`python -c "from services.recommendation_service import LLMRecommendationPayload; print(LLMRecommendationPayload.model_fields.keys())"` 退出 0 且打印 4 个字段名

### Step 3: 重写 `RecommendationService.__init__` 与 `get_recommendations`

在 [`src/services/recommendation_service.py`](../../../src/services/recommendation_service.py) 中注入 `AIAgentService` 并实现完整 LLM 流。

操作：
- a) 改 `__init__` 签名为 `def __init__(self, session: AsyncSession, ai_agent: AIAgentService)`，保存到 `self.ai_agent`
- b) 在 `import` 区增加 `from services.ai_agent_service import AIAgentService`（路径以 Step 1 验证结果为准）
- c) 改写 `get_recommendations` 方法：

```python
async def get_recommendations(
    self, opportunity_id: int, tenant_id: int
) -> RecommendationModel:
    opp_result = await self.session.execute(
        select(OpportunityModel).where(
            OpportunityModel.id == opportunity_id,
            OpportunityModel.tenant_id == tenant_id,
        )
    )
    opportunity = opp_result.scalar_one_or_none()
    if opportunity is None:
        raise NotFoundException("Opportunity")

    deals_result = await self.session.execute(
        select(DealModel)
        .where(
            DealModel.tenant_id == tenant_id,
            DealModel.stage == "closed_won",
        )
        .order_by(DealModel.closed_at.desc())
        .limit(5)
    )
    similar_deals = list(deals_result.scalars().all())

    prompt = self._build_prompt(opportunity, similar_deals)
    raw = await self.ai_agent.call_recommendation_llm(prompt)
    try:
        payload = LLMRecommendationPayload.model_validate(raw)
    except PydanticValidationError as exc:
        raise ValidationException(detail=f"Invalid LLM payload: {exc}") from exc

    rec = RecommendationModel(
        tenant_id=tenant_id,
        opportunity_id=opportunity_id,
        next_action=payload.next_action,
        confidence=payload.confidence,
        reasons=payload.reasons,
        similar_deals=payload.similar_deals,
    )
    self.session.add(rec)
    await self.session.commit()
    await self.session.refresh(rec)
    return rec
```

d) 新增私有方法 `_build_prompt`：

```python
def _build_prompt(self, opportunity, similar_deals) -> str:
    deals_text = "\n".join(
        f"- {d.name} (${d.amount}, closed {d.closed_at})" for d in similar_deals
    ) or "(no historical closed-won deals)"
    return (
        f"Opportunity: {opportunity.name}\n"
        f"Stage: {opportunity.stage}\n"
        f"Amount: {opportunity.amount}\n\n"
        f"Top 5 similar closed-won deals:\n{deals_text}\n\n"
        f"Recommend the next action as JSON with keys: "
        f"next_action, confidence (0-1), reasons (list), similar_deals (list)."
    )
```

**完成判定**：`PYTHONPATH=src python -c "from services.recommendation_service import RecommendationService; import inspect; print(inspect.signature(RecommendationService.__init__))"` 输出 `(self, session: AsyncSession, ai_agent: AIAgentService)`

### Step 4: 单元测试 mock 接线

新建或扩展 [`tests/unit/test_recommendation_service.py`](../../../tests/unit/test_recommendation_service.py)，覆盖 LLM 正常流、payload 非法流、opportunity 不存在流。

操作：
- a) 定义 `mock_db_session` fixture：组合 `make_opportunity_handler`、`make_recommendation_handler`（或 `make_count_handler`）和 mock `refresh` 行为
- b) 定义 `mock_ai_agent`：一个 stub 类，方法 `async def call_recommendation_llm(self, prompt) -> dict` 返回固定 payload
- c) 编写以下测试用例：
  - `test_get_recommendations_happy_path` — mock LLM 返回合法 payload，断言返回 `RecommendationModel` 且 `next_action` 正确
  - `test_get_recommendations_opportunity_not_found` — mock opportunity 查询返回 `None`，断言抛 `NotFoundException`
  - `test_get_recommendations_invalid_payload` — mock LLM 返回 `{"next_action": ""}` 触发 Pydantic 校验失败，断言抛 `ValidationException`
  - `test_get_recommendations_tenant_isolation` — 传入 `tenant_id=1` 时 mock 验证 SQL 含 `WHERE tenant_id = 1`
  - `test_get_recommendations_does_not_call_to_dict` — spy 验证 service 内没有调用 `.to_dict()`
  - `test_build_prompt_includes_opportunity_and_deals` — 直接调用 `_build_prompt` 验证字符串包含 opportunity name 和 deal 信息

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → 6 passed

### Step 5: Lint 与类型检查

确保新增代码符合 ruff 规范。

操作：
- a) `ruff check src/services/recommendation_service.py` 退出 0
- b) `ruff check tests/unit/test_recommendation_service.py` 退出 0
- c) `ruff format --check src/services/recommendation_service.py` 退出 0
- d) `mypy src/services/recommendation_service.py` 退出 0（如启用）

**完成判定**：`ruff check src/services/recommendation_service.py tests/unit/test_recommendation_service.py && ruff format --check src/services/recommendation_service.py tests/unit/test_recommendation_service.py` → 全部 exit 0

### Step 6: Router 端到端确认

TBD - 待验证：router 是否已存在。如已存在，确认其构造 `RecommendationService` 时传入 `AIAgentService` 依赖。

操作：
- a) `grep -n "RecommendationService(" src/api/routers/recommendations.py` 找到构造点
- b) 如 router 还未注入 `AIAgentService`，添加 `ai_agent: AIAgentService = Depends(get_ai_agent)` 并传入 service
- c) 启动 dev server：`PYTHONPATH=src uvicorn main:app --reload --port 8000`
- d) `curl -X GET "http://localhost:8000/recommendations/opportunities/1" -H "Authorization: Bearer $TOKEN"` 验证返回结构

**完成判定**：curl 返回 `{"success": true, "data": {"id": ..., "next_action": ..., "confidence": ...}}`

---

## 6. 验收

- [ ] `ruff check src/services/recommendation_service.py` → 0 errors
- [ ] `ruff check tests/unit/test_recommendation_service.py` → 0 errors
- [ ] `ruff format --check src/services/recommendation_service.py tests/unit/test_recommendation_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → 6 passed
- [ ] `python -c "from services.recommendation_service import LLMRecommendationPayload, RecommendationService; import inspect; assert 'ai_agent' in inspect.signature(RecommendationService.__init__).parameters"` → exit 0
- [ ] `grep -n "tenant_id" src/services/recommendation_service.py` → 至少 3 行匹配（opportunity 查询、deals 查询、INSERT）
- [ ] `grep -n "\.to_dict()" src/services/recommendation_service.py` → 0 匹配（service 内禁止调用）
- [ ] TBD - 待验证：如涉及 migration，`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] TBD - 待验证：端到端 `curl -X GET http://localhost:8000/recommendations/opportunities/{id} -H "Authorization: Bearer $TOKEN"` → `{"success": true, "data": {...}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #811 未合并或 `AIAgentService.call_recommendation_llm` 签名不匹配 | 中 | 高 | 本板块阻塞；在 board 顶部标注「等待 #811」并打回；不合并此 PR 直到 #811 在 master |
| LLM 返回的 JSON 结构漂移（缺字段 / 多字段 / 类型变化） | 中 | 中 | `LLMRecommendationPayload` 的 `extra="ignore"` 策略 + 严格必填字段；失败抛 `ValidationException` 让 router 返回 422，便于监控告警 |
| `RecommendationModel` 表缺 `tenant_id` 索引导致同租户查询慢 | 低 | 中 | 在 service 查询前临时加 `CREATE INDEX CONCURRENTLY`，后续跟进 migration 板块 |
| Mock `session.refresh()` 在测试中行为不一致 | 中 | 低 | 显式在 mock handler 中设置 `obj.id = state.next_id` 后 `state.next_id += 1`；参考 `MockState` 既有的 `customers` 模式 |
| `PydanticValidationError` 未被全局异常处理器识别 | 低 | 中 | 显式 `try/except` 包装为 `ValidationException`（项目标准异常），全局 handler 已知处理 |
| Prompt 注入 / LLM 越权 | 低 | 高 | Prompt 模板中所有用户字段做转义（`str.replace` 移除控制字符）；后续板块引入 output 侧 `tools` 白名单 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/recommendation_service.py tests/unit/test_recommendation_service.py
git commit -m "feat(sales): wire LLM call into RecommendationService.get_recommendations"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "Wire LLM call into RecommendationService.get_recommendations" --body "Closes #812"

# 2. 更新进度
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
# - 如本板块引入了新依赖或新 migration，单独通知 #600 owner 复核整体 LLM 流程状态
