# AI驱动的实时推荐 · 将 LLM 接入 RecommendationService

| 元数据 | 值 |
|---|---|
| Issue | #600 |
| 分类 | 50-automation |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 取决于 #46 最终用户可见推荐功能的交付计划 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `RecommendationService.get_recommendations()` 没有接入 AI 能力，只能返回静态或规则匹配结果，无法生成含语义推理 confidence、reasons、similar_deals 的结构化推荐。CRM销售的推荐质量直接决定转化效率，LLM 可根据成交历史上下文主动推断最佳跟进动作，这一能力缺失是产品功能的关键缺口。Issue 要求在 #41（AI Agent Framework 基础层）完成之前**不得开始**本工作，因此本板块的正确启动时机是 #41 merge 后。

### 1.2 做完后

- **用户视角**：`GET /recommendations/{opportunity_id}` 返回 AI 生成的推荐，内含 `next_action`（中文动作建议）、`confidence`（0.0-1.0 置信度）、`reasons`（3-5 条理由数组）、`similar_deals`（参考成交案例数组），直接显示在销售工作台，无需人工解读日志。
- **开发者视角**：`RecommendationService.get_recommendations()` 内部调用 LLM，端到端返回 `RecommendationModel` ORM 对象。新增 `RecommendationRepository` 可独立持久化和查询推荐记录。Service 方法签名兼容原接口（接受 `tenant_id`），对 router透明。

### 1.3 不做什么（剔除）

- [ ] 实现 AI Agent Framework（由 #41 负责，本板块只调用其 endpoint）
- [ ] 设计推荐提示词策略（Prompt tuning 由未来的 #46 子任务负责，本板块只保证调用链路打通）
- [ ] 前端展示 UI（由前端板块负责，本板块仅保证 API response 结构正确）
- [ ] 推荐结果缓存（future work，不在本期 scope）
- [ ] 超时优化 / 并发批量调用（future work，首期只保证单次调用链路）

### 1.4 关键 KPI

- LLM 返回的 JSON 在99% 请求中可被 Pydantic 解析，无 `ValidationError` crash- `pytest tests/unit/test_recommendation_service.py -v` 回归全部 passed
- `pytest tests/integration/test_recommendation_llm_integration.py -v` 全 passed（含 assert LLM mock 被调用 assert result persisted）
- `ruff check src/services/recommendation_service.py src/api/routers/recommendation_router.py` →0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 2. 当前现状（起点）

### 2.1 现有实现

**机会性审计** — 无法确认，以下两处需在 #41 完成后立即用 grep 核实：

- `TBD - 待验证：src/services/recommendation_service.py L? —现有 RecommendationService.get_recommendations() 实现，建议从 `def get_recommendations` 搜索`
- `TBD - 待验证：src/services/ai_agent_service.py L? — #41 新建的 AI Agent Framework service，暴露 `call_llm(endpoint, system, user)` 方法`

若上述文件尚未存在（#41 未完成），则 `§2.1` 返回 `N/A — 新建模块`；一旦 #41 merge 即可启动本板块。

### 2.2 涉及文件清单

- 要改：
  - `TBD - 待验证：src/services/recommendation_service.py — 新增 `get_recommendations()` 对 LLM 的调用逻辑`
  - `TBD - 待验证：src/api/routers/recommendation_router.py — 新增 `GET /recommendations/{opportunity_id}` endpoint`
- 要建：
  - `src/db/models/recommendation_model.py` — ORM model（含 `next_action`, `confidence`, `reasons`, `similar_deals`, `tenant_id`）
  - `alembic/versions/<id>_create_recommendation_table.py` — 创建 `recommendations` 表，含 `tenant_id` 索引
  - `tests/unit/test_recommendation_service.py` — mock LLM client，验证 service逻辑
  - `tests/integration/test_recommendation_llm_integration.py` — mock LLM HTTP server，验证持久化和 API 返回
  - `tests/integration/conftest.py` — 新增 `_seed_opportunity` / `_seed_recommendation` 辅助 fixture

### 2.3 缺什么

- [ ] `RecommendationService`缺少调用 LLM endpoint 的内部方法，无 `call_llm_for_recommendations()` 实现
- [ ] 缺少 `RecommendationModel` ORM model，推荐结果无法持久化到 DB
- [ ] 缺少 `recommendations` 数据库表（无 migration）
- [ ] 缺少 API endpoint暴露推荐结果给前端- [ ] 缺少 `reasons`（`list[str]`）和 `similar_deals`（`list[dict]`）字段的 Pydantic 响应 schema- [ ] 缺少 LLM 解析失败时的降级逻辑（当前 service 无错误处理覆盖 LLM 非200 响应）
- [ ] 缺少对机会数据（opportunity）和成交上下文（closed-deal context）的 prompt构造逻辑- [ ] 缺少单元测试（mock LLM）和集成测试（mock HTTP LLM server）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/recommendation_model.py` | `RecommendationModel` ORM model，含 next_action / confidence / reasons / similar_deals / tenant_id |
| `alembic/versions/<id>_create_recommendation_table.py` | 创建 `recommendations` 表，含 `tenant_id` 索引和唯一约束 |
| `tests/unit/test_recommendation_service.py` | 单元测试：mock `AIAgentService`，验证 prompt构造 / LLM 调用 / response 解析 |
| `tests/integration/test_recommendation_llm_integration.py` | 集成测试：mock HTTP LLM server，验证 full stack（API → service → LLM → DB → response） |

### 3.2 修改文件

|路径 | 改动要点 |
|------|---------|
| `TBD - 待验证：src/services/recommendation_service.py` | 新增 `get_recommendations()` 调用 LLM 并持久化；注入 `AIAgentService` 依赖 |
| `TBD - 待验证：src/api/routers/recommendation_router.py` | 新增 `GET /recommendations/{opportunity_id}` endpoint，返回 `{"success": true, "data": {...}}` |
| `TBD - 待验证：src/models/response.py`（或 `src/models/schemas.py`） | 新增 `RecommendationResponse` Pydantic schema，与 ORM `to_dict()` 兼容 |
| `TBD - 待验证：alembic/env.py` | 导入新增的 ORM model，确保 autogen 可见 |

### 3.3 新增能力

- **Service method**：`RecommendationService.get_recommendations(opportunity_id: int, tenant_id: int) -> RecommendationModel`
- **Service method**：`AIAgentService.call_recommendation_llm(prompt: str) -> dict`（若 #41尚未暴露此方法则新建简化版）
- **ORM model**：`RecommendationModel` in `src/db/models/recommendation_model.py`
- **Migration**：`alembic upgrade head` 创建 `recommendations` 表（含 `tenant_id` 复合索引）
- **API endpoint**：`GET /recommendations/{opportunity_id}` → `{"success": true, "data": {"id": 1, "next_action": "...", "confidence": 0.87, ...}}`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JSON mode + Pydantic bypass校验**：让 LLM 输出严格 JSON（`response_format: {"type": "json_object"}`），service 层用 Pydantic `validate_json()` 解析。规避正则 hack，置信度高且易于迭代 prompt。
- **不选 few-shot in-prompt 降级**：若 LLM 超时或返回非 JSON，service 直接 raise `ServiceException`（HTTP 400），前端弹"推荐稍后再试"，不让用户看到 raw error。
- **Opportunity 和 closed-deal context 从 DB query 构建 prompt**：确保 tenant隔离，不把其他 tenant 的成交案例混入。

### 4.2 版本约束

<!-- 无新增外部依赖；AIAgentService 由 #41 提供，版本随主项目走。 -->

|依赖 | 版本 | 理由 |
|------|------|------|
| `pydantic` | 项目现有版本 | 用于 response schema 和 LLM output解析，无新版本要求 |

### 4.3 兼容性约束

- 多租户：推荐结果按 `tenant_id` 隔离存储和查询；LLM prompt构造时禁止拼接其他 tenant ID 的数据
- Service `__init__` 严格签名为 `def __init__(self, session: AsyncSession)`，无默认值；AIAgentService注入亦遵守同样规则
- Service 方法**不调用** `.to_dict()`，解析后返回 ORM 对象；序列化由 router `.to_dict()` 完成
- 错误抛 `AppException` 子类，**不**返回 `ApiResponse.error()`
- 所有 LLM 调用超时上限 `timeout=30s`（防 service 层 hang）

### 4.4 已知坑

1. **LLM 返回非结构化 / 截断 JSON** → 规避：`try json.loads(raw) → Pydantic.validate_json()` 两段解析，外层 `except` 抛 `ValidationException("推荐格式错误，请稍后重试")`
2. **SQLAlchemy 列名 `metadata` 与 `Base.metadata` 冲突** →规避：`recommendations` 表列名用 `event_metadata` / `result_payload`，不用 `metadata`
3. **Alembic autogen 把 `JSONB` → `sa.JSON()` /漏 `timezone=True`** → 规避：migration写完后人工检查 `op_id` 列，改 `sa.JSON()` 为 `sa.JSONB().with_variant(db.JSON(), "postgresql")`，补 `timezone=True` on `created_at`
4. **LLM 返回5xx 或网络超时导致 service hang** → 规避：`httpx.AsyncClient(timeout=30.0)` 设置全局 timeout，超时 raise `TimeoutException` 再由 `except`转为 `ServiceException`
5. **mock LLM HTTP server 在集成测试中不respond** → 规避：`respx` 库 mock `httpx`，在 conftest 中 `respx.get("http://llm-agent/recommend").respond(json={...}).mock`替代真实 server---

## 5. 实现步骤（按顺序）

**前提**：以下所有 Step须在 #41（AI Agent Framework）merge之后启动。在此之前仅完成 Step 0（代码审计 + 接口确认）。

### Step 0:审计现有接口（#41 merge 后立即执行）

确认 #41 暴露的 AI Agent 接口：

```bash
# 1. 查找 AI Agent service 文件
grep -rn "call_llm\|chat\|AIAgent" src/services/ --include="*.py"

# 2. 查看 OpportunityService 是否可用（构造 prompt 需要机会数据）
grep -rn "get_opportunity\|opportunity" src/services/opportunity_service.py --include="*.py" |grep "async def"

# 3. 查看现有 RecommendationService（确认 get_recommendations 签名）
grep -rn "get_recommendations\|recommendation" src/services/ --include="*.py"
```

若 #41 已暴露 `AIAgentService.chat(prompt: str) -> str`，则记录其文件路径和行号，进入 Step 1。若尚未 merge，本板块维持 block 状态。

**完成判定**：`grep -c "AIAgentService\|call_llm" src/services/ai_agent*.py` exit 0 且输出含方法名

---

### Step 1: 新建 ORM Model `RecommendationModel`

在 `src/db/models/recommendation_model.py` 创建 model：

```python
from datetime import datetime
from typing import Optionalfrom sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Indexfrom sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase

class Base(DeclarativeBase):
    passclass RecommendationModel(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opportunity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    next_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False)          # list[str]
    similar_deals: Mapped[list] = mapped_column(JSONB, nullable=False)    # list[dict]
    raw_llm_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        Index("ix_recommendations_tenant_opp", "tenant_id", "opportunity_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "opportunity_id": self.opportunity_id,
            "next_action": self.next_action,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "similar_deals": self.similar_deals,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.recommendation_model import RecommendationModel; print('ok')"` exit 0

---

### Step 2: 生成数据库 Migration

前提：执行 Alembic 环境准备（见 CLAUDE.md §Alembic Migrations）：

```bash
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic revision --autogenerate -m "create recommendations table"
```

审查生成的 migration：将 `sa.JSON()` 改为 `sa.JSONB()`，补 `timezone=True` on `created_at`：

```python
# 在 alembic/versions/<id>_create_recommendations_table.py 中手动修正
opportunity_id=sa.Column(sa.Integer(), nullable=False),          # ✅ autogen 通常正确
reasons=sa.Column(sa.JSONB(), nullable=False),                   # 手动改：JSON → JSONB
similar_deals=sa.Column(sa.JSONB(), nullable=False),             # 手动改
created_at=sa.Column(sa.DateTime(timezone=True), server_default=sa.text('now()')),  # 手动补 timezone=True
```

验证迁移双向正确：

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

若第二次 `autogenerate -m "drift_check"` 产生空 migration（只含 `pass`），删除它。否则补完 drift。

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 三次均 exit 0

---

### Step 3: 更新 `#41 暴露的 AIAgentService`

在 `AIAgentService` 中新增 `call_recommendation_llm(prompt: str) -> dict` 方法：

```python
import httpx

class AIAgentService:
    def __init__(self, session: AsyncSession, llm_base_url: str = "http://llm-agent"):
        self.session = session
        self.llm_base_url = llm_base_url

 async def call_recommendation_llm(self, prompt: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.llm_base_url}/recommend",
                json={"prompt": prompt, "response_format": {"type": "json_object"}},
            )
            resp.raise_for_status()
            return resp.json()
```

同时在 `AIAgentService` 所在文件顶部确认 `from db.models import *` 或等效 import 使 RecommendationModel 可见（若采用跨 service 调用而非 router 直接调 AIAgentService）。

**完成判定**：`ruff check src/services/ai_agent_service.py` exit 0 且 `grep "call_recommendation_llm" src/services/ai_agent_service.py` 有输出

---

### Step 4: 增强 `RecommendationService.get_recommendations()`

修改 `RecommendationService`（或新建 `RecommendationService` 如果原先不存在）：

```python
import json
from pydantic import BaseModel, ValidationError, validate_json
from db.models.recommendation_model import RecommendationModel

class LLMRecommendationPayload(BaseModel):
    next_action: str
    confidence: float
    reasons: list[str]
    similar_deals: list[dict]

class RecommendationService:
    def __init__(self, session: AsyncSession, ai_agent: AIAgentService):
        self.session = session
        self.ai_agent = ai_agent

    async def get_recommendations(
        self, opportunity_id: int, tenant_id: int ) -> RecommendationModel:
        # 1. 构造 prompt（包含 opportunity 数据 + closed-deal 上下文）
        opportunity_result = await self.session.execute(
            text("SELECT * FROM opportunities WHERE id = :id AND tenant_id = :tid"),
            {"id": opportunity_id, "tid": tenant_id},
        )
        opp_row = opportunity_result.mappings().fetchone()
        if opp_row is None:
            raise NotFoundException("Opportunity")

        closed_deals_result = await self.session.execute(
            text("""
                SELECT o.name, o.amount, o.stage, o.closed_at
                FROM opportunities o
                WHERE o.tenant_id = :tid AND o.stage = 'closed_won'
                ORDER BY o.closed_at DESC                LIMIT 5 """),
            {"tid": tenant_id},
        )
        closed_deals = [dict(r) for r in closed_deals_result.mappings().fetchall()]

        prompt = self._build_prompt(dict(opp_row), closed_deals)

        # 2. 调用 LLM
        raw_response: dict = await self.ai_agent.call_recommendation_llm(prompt)

        # 3. 解析 + 校验结构化输出
        try:
            payload = LLMRecommendationPayload.model_validate(raw_response)
        except ValidationError:
            raise ValidationException("推荐格式错误，请稍后重试")

        # 4. 持久化        rec = RecommendationModel(
            tenant_id=tenant_id,
            opportunity_id=opportunity_id,
            next_action=payload.next_action,
            confidence=payload.confidence,
            reasons=payload.reasons,
            similar_deals=payload.similar_deals,
            raw_llm_response=json.dumps(raw_response),
        )
        self.session.add(rec)
        await self.session.commit()
        await self.session.refresh(rec)
        return rec

    def _build_prompt(self, opportunity: dict, closed_deals: list[dict]) -> str:
        return f"""
当前机会：ID={opportunity['id']}, 名称={opportunity['name']}, 阶段={opportunity['stage']}, 金额={opportunity.get('amount')}
近期成交案例：
{json.dumps(closed_deals, ensure_ascii=False)}
请给出下一步推荐动作（next_action）、置信度（confidence，0-1）、理由列表（reasons）和相似成交案例（similar_deals）。
输出 JSON格式。
"""
```

**完成判定**：`ruff check src/services/recommendation_service.py` exit 0

---

### Step 5: 新增 `POST /recommendations/{opportunity_id}` API Endpoint

在 `src/api/routers/` 新建或修改 `recommendation_router.py`：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from dependencies.fastapi_auth import AuthContext, require_auth
from services.recommendation_service import RecommendationService
from services.ai_agent_service import AIAgentService

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.get("/{opportunity_id}")
async def get_recommendation(
    opportunity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    ai_agent = AIAgentService(session)
    svc = RecommendationService(session, ai_agent)
    rec = await svc.get_recommendations(opportunity_id, tenant_id=ctx.tenant_id)
    return {"success": True, "data": rec.to_dict()}
```

在 `src/main.py` 注册 router（若尚未存在）：

```python
from api.routers import recommendation_router
app.include_router(recommendation_router.router)
```

**完成判定**：`ruff check src/api/routers/recommendation_router.py` exit 0 且 `grep "include_router\|recommendation_router" src/main.py` 有输出

---

### Step 6: 编写单元测试

在 `tests/unit/test_recommendation_service.py` 新建 fixture（使用 `make_mock_session` + 领域 handler）：

```python
import pytestfrom unittest.mock import AsyncMock
from tests.unit.conftest import make_mock_session, MockState, MockRow, make_mock_result

class TestRecommendationService:
    @pytest.fixture
    def mock_ai_agent(self):
        agent = AsyncMock(spec=AIAgentService)
        agent.call_recommendation_llm = AsyncMock(return_value={
            "next_action": "跟进报价",
            "confidence": 0.85,
            "reasons": ["金额超过阈值", "竞争者已出局"],
            "similar_deals": [{"name": "XX公司", "amount": 50000}],
        })
        return agent

    @pytest.fixture
    def mock_db_session(self):
        state = MockState()
        return make_mock_session([make_opportunity_handler(state)])

    async def test_get_recommendations_returns_structured_rec(
        self, mock_db_session, mock_ai_agent
    ):
        svc = RecommendationService(mock_db_session, mock_ai_agent)
        rec = await svc.get_recommendations(opportunity_id=1, tenant_id=1)
        assert rec.next_action == "跟进报价"
        assert 0 <= rec.confidence <= 1.0
        assert isinstance(rec.reasons, list)
        mock_ai_agent.call_recommendation_llm.assert_called_once()

    async def test_llm_returns_invalid_json_raises_validation(
        self, mock_db_session, mock_ai_agent
    ):
        mock_ai_agent.call_recommendation_llm = AsyncMock(return_value={"foo": "bar"})
        svc = RecommendationService(mock_db_session, mock_ai_agent)
        with pytest.raises(ValidationException):
            await svc.get_recommendations(opportunity_id=1, tenant_id=1)
```

补充 `make_opportunity_handler` 在 `tests/unit/conftest.py` 中（若尚不存在）。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → 全 passed

---

### Step 7: 编写集成测试

在 `tests/integration/test_recommendation_llm_integration.py`：

```python
import pytest
import respx
import httpx

@pytest.mark.integration
class TestRecommendationLLMIntegration:
    async def test_get_recommendation_calls_llm_and_persists(
        self, db_schema, tenant_id, async_session
    ):
        _seed_opportunity(async_session, tenant_id, opportunity_id=1)

        with respx.mock:
            respx.post("http://llm-agent/recommend").respond(json={
                "next_action": "预约 Demo",
                "confidence": 0.92,
                "reasons": ["高预算客群", "决策人感兴趣"],
                "similar_deals": [{"name": "YY集团", "amount": 80000}],
            })
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://llm-agent/recommend",
                    json={"prompt": "...", "response_format": {"type": "json_object"}},
                )
                assert resp.status_code == 200

        ai_agent = AIAgentService(async_session)
        svc = RecommendationService(async_session, ai_agent)
        rec = await svc.get_recommendations(opportunity_id=1, tenant_id=tenant_id)

        assert rec.next_action == "预约 Demo"
        assert rec.confidence == 0.92
        assert len(rec.reasons) == 2

 # verify persisted        result = await async_session.execute(
            text("SELECT * FROM recommendations WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        rows = result.mappings().fetchall()
        assert len(rows) == 1
        assert rows[0]["next_action"] == "预约 Demo"
```

**完成判定**：`DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db" PYTHONPATH=src pytest tests/integration/test_recommendation_llm_integration.py -v` → 全 passed

---

### Step 8: Lint + 最终验证

全面检查：

```bash
ruff check src/services/recommendation_service.py src/services/ai_agent_service.py src/api/routers/recommendation_router.py src/db/models/recommendation_model.py
ruff format --check src/services/recommendation_service.py src/services/ai_agent_service.py src/api/routers/recommendation_router.py src/db/models/recommendation_model.py
mypy src/services/recommendation_service.py src/services/ai_agent_service.py src/db/models/recommendation_model.py
```

确认无新增问题后，走完整测试：

```bash
PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

**完成判定**：上述所有命令 exit 0，无 ERROR output

---

## 6. 验收

- [ ] `ruff check src/services/recommendation_service.py src/services/ai_agent_service.py src/api/routers/recommendation_router.py src/db/models/recommendation_model.py` → 0 errors
- [ ] `ruff format --check src/services/recommendation_service.py src/services/ai_agent_service.py src/api/routers/recommendation_router.py src/db/models/recommendation_model.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_recommendation_service.py -v` → 全 passed
- [ ] `DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db" PYTHONPATH=src pytest tests/integration/test_recommendation_llm_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] 端到端：`httpx` mock LLM 返回有效 JSON 时，`POST /recommendations/1` 返回结构化的 `next_action` / `confidence` / `reasons` / `similar_deals` 字段

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| LLM endpoint 在生产环境不可达（#41 未 merge，或服务宕机） | 低 | 高 | feature flag `RECOMMENDATION_LLM_ENABLED=false` 跳过 LLM 调用，返回空推荐 list；不阻塞 API |
| #41 merge 后接口签名与本板块假设不符（方法名/参数/返回格式不同） | 低 | 中 | Step 0 代码审计时对齐接口；若发现 diff，重新调整 Step 3/4 中的调用代码 |
| LLM JSON 解析持续失败（Pydantic ValidationError 占比 >1%） | 中 | 中 | 写 fallback prompt（减少结构化约束），重试一次；二次失败才抛 ValidationException 并通知 oncall |
| 推荐结果写入 DB 失败（constraint violation / connection lost） | 低 | 低 | service 层 `finally: await session.rollback()`，即使写入失败 API 仍返回 200 但 data=null，前端提示"推荐稍后重试" |

---

## 8. 完成后必做

```bash
#1. commit + PR
git add src/db/models/recommendation_model.py \
 src/services/recommendation_service.py \
       src/services/ai_agent_service.py \
       src/api/routers/recommendation_router.py \
       src/main.py \
       alembic/versions/<id>_create_recommendation_table.py \
       tests/unit/test_recommendation_service.py \
       tests/integration/test_recommendation_llm_integration.py
git commit -m "feat(recommendation): wire LLM into RecommendationService for structured AI recommendations

- add RecommendationModel ORM with next_action/confidence/reasons/similar_deals
- add LLM call in RecommendationService.get_recommendations()
- add GET /recommendations/{opportunity_id} endpoint
- add unit + integration tests (respx mock LLM)
- add alembic migration for recommendations table

Closes #600"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#600): Wire AI Agent Framework into RecommendationService" --body "Closes #600"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/services/opportunity_service.py` — 现有 service模式参考（`session` DI、ORM 持久化）
- 父 issue /关联：#46（AI 销售推荐系统主 epic）、#599（RecommendationService 基础版）、#41（AI Agent Framework 基础设施，待 merge 后解除本板块 block）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
