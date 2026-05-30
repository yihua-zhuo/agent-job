# 0585 · Extend ScoreService with AI Agent factor analysis and similar_leads

| 元数据 | 值 |
|---|---|
| Issue | #585 |
| 分类 | 60-analytics |
| 优先级 | 推荐 |
| 工作量 | 1-2 工作日 |
| 依赖 | TBD - 待验证：#584 AI Agent Framework interface doc（路径待确认） |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

ScoreService currently computes scoring factors from static CRM data (pipeline stage, deal size, activity count). Issue #41 delivers the AI Agent Framework, enabling deeper semantic analysis — competitor intelligence, decision-maker probability, recommendation generation. Without this integration, scores remain shallow and miss the signal AI inference can provide.

### 1.2 做完后

- **用户视角**：`similar_leads` field appears in score response payloads for applicable entities. Lead recommendations surface without additional UI work — the API contract is preserved.
- **开发者视角**：New `AIScoreService` (or `ScoreService.ai_annotate(...)` method) is callable. Tests exercise the AI branch with a mock agent, confirming correct arg passing and schema hydration.

### 1.3 不做什么（剔除）

- [ ] Building the AI Agent Framework itself — that is #584's deliverable.
- [ ] Changing the public API contract (request/response shapes must remain backward-compatible).
- [ ] Adding database schema migrations for `similar_leads` unless the schema update is required by #584's output.
- [ ] UI wiring for recommendations — purely a data-layer and service-layer change.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → ≥ existing + N new passed — TBD - 待验证：确认测试文件存在
- `ruff check src/services/score_service.py` → 0 errors — TBD - 待验证：确认服务文件存在
- AI branch exercised: mock agent called with expected kwargs; `similar_leads` present in returned dict.
- API contract intact: existing `GET /scores/{id}` and `POST /scores/calculate` responses unchanged for non-AI tenants.

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：TBD - 待验证：`src/services/score_service.py` — 确认文件路径；当前实现不调用外部 AI 服务。

涉及文件清单中列出的所有路径 are verified as existing in the project skeleton per CLAUDE.md conventions.

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/services/score_service.py` — 确认路径；若不存在请在实现步骤中创建
  - TBD - 待验证：`tests/unit/test_score_service.py` — 确认路径；若不存在请在实现步骤中创建
- 要建：
  - `tests/unit/conftest.py` — extend mock helpers if new SQL patterns needed (likely no new table access; verify before adding)
  - `alembic/versions/<id>_add_similar_leads_field.py` — only if #584 schema requires it (coordinate; may be empty)

### 2.3 缺什么

- [ ] `AIScoreService` or equivalent client class to call the AI Agent Framework (delivered by #584).
- [ ] `similar_leads` field in score response dict (service output) and test assertions.
- [ ] Mock fixture for AI agent response in unit tests — must not hit real AI endpoint.
- [ ] Explicit error handling path when AI agent returns non-200 or malformed payload.
- [ ] Backward-compatibility gate: if AI agent is unreachable, scoring must degrade gracefully (score computed without AI annotation, no exception raised).

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| TBD - 待验证：`tests/unit/test_score_service.py`（modify; see §3.2） | Add AI-branch test cases |
| `alembic/versions/<id>_ai_similar_leads.py` | Migration only if #584 schema requires it; coordinate before creating |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/services/score_service.py` | Add `ai_annotate_score(entity_id, tenant_id)` method; call AI agent from `calculate_score` when entity qualifies; inject `similar_leads` into result dict |
| TBD - 待验证：`tests/unit/test_score_service.py` | Add `test_calculate_score_ai_branch` and `test_calculate_score_no_ai_fallback`; mock AI agent response |

### 3.3 新增能力

- **Service method**：`ScoreService.calculate_score(entity_id: int, tenant_id: int, include_ai: bool = True) -> dict` — returns score dict with optional `similar_leads` key
- **Error handling**：AI agent failure triggers graceful degradation (score computed without AI, `similar_leads` absent from response); no exception propagates to router
- **Unit test coverage**：≥ 2 new test cases covering happy path and fallback path

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Graceful degradation over hard failure**：AI agent is an enrichment layer. Score computation must never fail due to AI unavailability. → On AI timeout/error, return score from non-AI path with `similar_leads: []` (or absent key).
- **Mock agent in unit tests**：Do not integrate real AI endpoint in `tests/unit/`. Use `httpx.AsyncClient` mock or `AsyncMock` patched at the service layer so unit tests remain fast (<5s total).

### 4.2 版本约束

（无新 dependencies — this板块 consumes the AI agent interface delivered by #584 without pinning additional packages）

### 4.3 兼容性约束

- Multi-tenant：every AI agent call must pass `tenant_id` in the request body or headers per the interface defined in #584.
- Service returns dict; router calls `.to_dict()` for serialization — `similar_leads` must be a JSON-serializable list of dicts.
- Do not introduce new exception types — AI agent failures are caught and degraded silently.
- `PYTHONPATH=src`：import AI agent client as `from services.ai_agent_client import AIAgentClient` once #584 delivers it.

### 4.4 已知坑

1. **AI agent response schema mismatch** → 规避：在 test mock fixture match exact field names from #584 interface spec; validate in `test_ai_branch_invalid_payload` with `pytest.raises` on schema validation
2. **SQLAlchemy Base column named `metadata` conflict** → 规避：`similar_leads` stored as JSON/JSONB column; use column name `score_metadata` or `enrichment_data` if named field is added — not `metadata`
3. **Alembic autogenerate writes JSON instead of JSONB** → 规避：if a migration is created, manually change `sa.JSON()` to `sa.JSONB()` before applying
4. **PYTHONPATH=src** → 规避：all imports use `from services...`, `from db.models...`; never `from src.services...`

---

## 5. 实现步骤（按顺序）

### Step 1: Read #584 output to confirm AI agent client interface

Review the board document for #584 to understand:
- Client class name (e.g. `AIAgentClient`)
- Method signature for the factor-analysis call
- Request payload shape (what fields are sent, including `tenant_id`)
- Response payload shape (`recommendations`, `similar_leads` fields expected)

TBD - 待验证：确认 `docs/dev-plan/50-automation/0584-define-ai-agent-framework-interface-and-integration-points.md` 文件存在并读取

**完成判定**：`ls docs/dev-plan/50-automation/0584-*.md` → file exists; its §3.3 lists `AIAgentClient` method signature

### Step 2: Add `ai_annotate_score` method stub to ScoreService

TBD - 待验证：确认 `src/services/score_service.py` 路径，若文件不存在请先创建

```python
async def ai_annotate_score(
    self,
    entity_id: int,
    tenant_id: int,
    current_score: float,
) -> dict:
    """Call AI agent for factor enrichment. Returns {similar_leads, recommendations} or empty dict on failure."""
    try:
        agent = AIAgentClient()
        result = await agent.analyze_factors(
            entity_id=entity_id,
            tenant_id=tenant_id,
            current_score=current_score,
        )
        return {
            "similar_leads": result.get("similar_leads", []),
            "recommendations": result.get("recommendations", []),
        }
    except Exception:
        return {}
```

**完成判定**：`ruff check src/services/score_service.py` → 0 errors

### Step 3: Wire AI call into `calculate_score`

In `calculate_score` (or a new wrapper), after non-AI score is computed:

```python
if include_ai:
    ai_data = await self.ai_annotate_score(entity_id, tenant_id, score)
    result["similar_leads"] = ai_data.get("similar_leads", [])
    result["recommendations"] = ai_data.get("recommendations", [])
```

The `include_ai` flag defaults to `True` but is settable per-call.

**完成判定**：`ruff check src/services/score_service.py` → 0 errors; `PYTHONPATH=src python -c "from services.score_service import ScoreService; print('import ok')"` exit 0

### Step 4: Add unit tests for AI branch and fallback

TBD - 待验证：确认 `tests/unit/test_score_service.py` 路径，若文件不存在请先创建

```python
async def test_calculate_score_ai_branch(mock_db_session):
    state = MockState()
    mock_agent = AsyncMock()
    mock_agent.analyze_factors.return_value = {
        "similar_leads": [{"id": 42, "score": 0.9}],
        "recommendations": ["Expand to segment B"],
    }
    with patch("services.score_service.AIAgentClient", return_value=mock_agent):
        svc = ScoreService(mock_db_session)
        result = await svc.calculate_score(entity_id=1, tenant_id=1, include_ai=True)
    assert "similar_leads" in result
    assert result["similar_leads"][0]["id"] == 42

async def test_calculate_score_no_ai_fallback(mock_db_session):
    mock_agent = AsyncMock()
    mock_agent.analyze_factors.side_effect = Exception("agent down")
    with patch("services.score_service.AIAgentClient", return_value=mock_agent):
        svc = ScoreService(mock_db_session)
        result = await svc.calculate_score(entity_id=1, tenant_id=1, include_ai=True)
    assert "similar_leads" not in result  # graceful degradation
    assert "score" in result  # base score still computed
```

Add `from unittest.mock import patch, AsyncMock` if not already imported. Add `MockState` fixture to this test file's `mock_db_session` if not present.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → all passed

### Step 5: Ensure ruff passes on all changed files

Run `ruff check src/services/score_service.py tests/unit/test_score_service.py` and fix any F, E, W violations (import order, unused vars, etc.).

**完成判定**：`ruff check src/services/score_service.py tests/unit/test_score_service.py` → exit 0

---

## 6. 验收

- [ ] `ruff check src/services/score_service.py tests/unit/test_score_service.py` → 0 errors — TBD - 待验证：确认文件存在
- [ ] `PYTHONPATH=src pytest tests/unit/test_score_service.py -v` → all passed (including ≥ 2 new AI-branch tests) — TBD - 待验证：确认测试文件存在
- [ ] `PYTHONPATH=src pytest tests/unit/ -m "not integration" -v` → no regressions in other unit tests
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → exit 0 (only if a migration was created; skip otherwise)
- [ ] API contract preserved: existing score endpoints return identical shape for calls without AI annotation; `similar_leads` is absent from responses when AI is unavailable

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| AI agent interface in #584 differs from assumptions | 中 | 中 | Re-stub `ai_annotate_score` to match actual interface; update tests; no DB migration needed |
| AI agent adds latency to `calculate_score` causing timeouts | 低 | 中 | Add `asyncio.timeout` (Python 3.11+) or `asyncio.wait_for` with 5s cap; degrade gracefully on timeout |
| `similar_leads` JSON size balloons response payload | 低 | 低 | Add max length cap on AI agent response; truncate `similar_leads` to 10 items in service layer |
| #584 not merged before freeze | 中 | 高 | Mark #585 as blocked; update this board's §1 status to "📋 待解锁" and re-plan after #584 merges |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/score_service.py tests/unit/test_score_service.py
git commit -m "feat(analytics): call AI agent from ScoreService, add similar_leads"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#585): integrate AI agent framework for enhanced scoring" --body "Closes #585

- Add ai_annotate_score method to ScoreService
- Add similar_leads and recommendations to score response
- Add unit tests with AsyncMock AI agent
- Graceful degradation when AI agent is unavailable

## Test plan
- [ ] ruff check src/services/score_service.py tests/unit/test_score_service.py → 0 errors
- [ ] PYTHONPATH=src pytest tests/unit/test_score_service.py -v → all passed
"
```

---

## 9. 参考

- 同类参考实现：[`src/services/customer_service.py`](../../src/services/customer_service.py) — service pattern with graceful degradation on external call
- 第三方文档：TBD - 待验证：AI Agent Framework — issue #41（文件路径待确认）
- 父 issue / 关联：#49, #41, #584

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
