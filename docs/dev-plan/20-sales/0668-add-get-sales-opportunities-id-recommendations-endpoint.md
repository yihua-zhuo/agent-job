# 20-sales · 新增机会详情推荐与优先级排序接口

| 元数据 | 值 |
|---|---|
| Issue | #668 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [#667](./0667-implement-recommendation-scoring-and-similar-deals-logic.md) |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `sales/opportunities` 路由仅有基础的 CRUD 端点，缺少两个关键能力：① 机会详情的 AI 推荐结果查询；② 机会列表按业务优先级排序。这两项是销售团队日常工作流的阻塞点——客服无法快速定位高优先级机会，必须在内存中手动计算排序。

[#667](./0667-implement-recommendation-scoring-and-similar-deals-logic.md) 已实现 `RecommendationService.get_recommendations()` 方法，本板块将其暴露为 REST API 端点。

### 1.2 做完后

- **用户视角**：GET `/sales/opportunities/{id}/recommendations` 返回该机会的推荐列表（置信度、风险等级、优先级标签）；GET `/sales/opportunities?sort=recommendation_priority` 返回按 urgency score（confidence × risk_severity）降序的机会列表。
- **开发者视角**：`sales/opportunities.py` 新增 `GET /{opportunity_id}/recommendations` 和 `GET /?sort=recommendation_priority` 两个端点；`RecommendationService` 从内部调用升级为公开 API。

### 1.3 不做什么（剔除）

- [ ] 不实现 POST/PUT/DELETE 推荐端点（推荐结果为系统生成，只读）
- [ ] 不在 `RecommendationService` 中新增推荐计算逻辑（[#667](./0667-implement-recommendation-scoring-and-similar-deals-logic.md) 职责）
- [ ] 不为推荐数据新增数据库表（本板块仅对接已建好的服务）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_sales_opportunities_recommendations.py -v` → ≥ 8 passed
- `ruff check src/api/routers/sales/opportunities.py` →0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如有 migration 变更）
- 端到端：`curl http://localhost:8000/sales/opportunities/1/recommendations` → HTTP 200，`{"success": true, "data": {...}}`

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[TBD - 待验证：拆出 sales专属路由文件，确认 opportunities 路由位置]

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth

router = APIRouter(prefix="/sales/opportunities", tags=["sales"])


@router.get("/")
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = OpportunityService(session)
    items, total = await svc.list_opportunities(
        tenant_id=ctx.tenant_id, page=page, page_size=page_size
    )
    return {"success": True, "data": {"items": [i.to_dict() for i in items], "total": total}}
```

当前 `list_opportunities` 不支持 `sort=recommendation_priority` 参数；`GET /{opportunity_id}/recommendations` 端点不存在。

### 2.2 涉及文件清单

- 要改：
  - [TBD - 待验证：确认 sales 路由文件路径 — 目前 opportunities路由可能在 `src/api/routers/sales.py` 或需新拆文件] — 新增 `GET /{opportunity_id}/recommendations` 端点；`list_opportunities` 增加 `sort` 参数与排序逻辑
  - [TBD - 待验证：确认推荐服务测试文件名是否已存在] — 新增单元测试文件
- 要建：
  - [TBD - 待验证：确认测试文件名] — 两个端点的 mock session 测试
  - `alembic/versions/<id>_add_recommendation_priority_sort.sql` — 仅当排序字段需建索引时（暂定无需新建）

### 2.3 缺什么

- [ ] `GET /sales/opportunities/{id}/recommendations` 端点不存在
- [ ] `list_opportunities` 不支持 `sort=recommendation_priority` 参数
- [ ] 没有调用 `RecommendationService.get_recommendations()` 的路由代码
- [ ] 没有对应 `GET /{opportunity_id}/recommendations` 的单元测试
- [ ] 没有对应 `GET /?sort=recommendation_priority` 的单元测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| [TBD - 待验证：确认测试文件路径] | 覆盖两个新端点的单元测试（含 mock session） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [TBD - 待验证：确认 sales 路由文件路径] | 新增 `GET /{opportunity_id}/recommendations` 端点；`GET /` 增加 `sort` 查询参数（值为 `recommendation_priority` 时调用排序逻辑） |
| [TBD - 待验证：确认推荐服务文件路径] | 确认 `get_recommendations` 方法签名（如尚未公开则改为公开） |

### 3.3 新增能力

- **API endpoint**：`GET /sales/opportunities/{opportunity_id}/recommendations` → `{"success": true, "data": {"opportunity_id": N, "recommendations": [...]}}`
- **API endpoint**：`GET /sales/opportunities?sort=recommendation_priority` → 机会列表按 urgency score 降序返回
- **Service method**：`RecommendationService.get_recommendations(opportunity_id: int, tenant_id: int) -> list[RecommendationModel]`
- **Query param**：`sort: Literal["", "recommendation_priority"] = ""` 加到 `list_opportunities` 路由

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 Query 参数 `sort` 而非路径参数**：排序是可选的列表过滤行为，用 query string 语义更清晰，与 RESTful 惯例一致。
- **排序在 Service 层计算而非 DB 层**：urgency score（confidence × risk_severity）来自 `RecommendationService` 的内存计算，不需要额外的 DB 索引或 SQL 表达式。

### 4.2 版本约束

无新增依赖。

### 4.3 兼容性约束

- 多租户：`GET /{opportunity_id}/recommendations` 必须将 `opportunity_id` 归属校验——先查机会是否存在且 `tenant_id` 匹配，再查推荐数据；否则抛出 `ForbiddenException`（非 `NotFoundException`，避免 tenant 信息泄露）。
- Service 返回 ORM 对象，router 负责 `.to_dict()` 序列化。
- Service 错误抛 `AppException` 子类，router 不捕获（全局异常处理器负责）。

### 4.4 已知坑

1. **推荐数据为空时返回 404 而非空列表** → 规避：`RecommendationService` 返回空列表而非抛异常；router 判空后返回 `{"success": true, "data": {"recommendations": []}}`
2. **机会不存在时推荐接口返回 404 而非 403** → 规避：两步校验（先机会存在性 + tenant 归属，再查推荐数据）；两步都失败时抛 `NotFoundException`（保持安全语义：推荐不存在 → 404）
3. **SQLAlchemy AsyncSession 在单元测试中被 Mock 替换后无法真正执行** → 规避：单元测试使用 `make_mock_session` 传入 mock handler，不触发真实 DB

---

## 5. 实现步骤（按顺序）

### Step 1: 检查 RecommendationService 方法签名

读取 [TBD - 待验证：确认推荐服务文件路径]，确认 `get_recommendations` 方法存在且返回类型为 `list[RecommendationModel]`。如方法不存在或为 private，修改为：

```python
async def get_recommendations(
    self, opportunity_id: int, tenant_id: int
) -> list[RecommendationModel]:
    result = await self.session.execute(
        select(RecommendationModel).where(
            RecommendationModel.opportunity_id == opportunity_id,
            RecommendationModel.tenant_id == tenant_id,
        )
    )
    return list(result.scalars().all())
```

**完成判定**：`grep -n "async def get_recommendations" src/services/recommendation_service.py` 返回至少 1 行

---

### Step 2: 在 opportunities.py 注入 RecommendationService

在 [TBD - 待验证：确认 sales 路由文件路径] 顶部添加 import：

```python
from services.recommendation_service import RecommendationService
```

**完成判定**：`ruff check src/api/routers/sales/opportunities.py` → 0 errors

---

### Step 3: 新增 GET /{opportunity_id}/recommendations 端点

在 [TBD - 待验证：确认 sales 路由文件路径] 文件末尾（`@router.get("/")` 之后）新增端点：

```python
@router.get("/{opportunity_id}/recommendations")
async def get_opportunity_recommendations(
    opportunity_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = OpportunityService(session)
    opp = await svc.get_opportunity(opportunity_id, tenant_id=ctx.tenant_id)
    rec_svc = RecommendationService(session)
    recommendations = await rec_svc.get_recommendations(
        opportunity_id=opportunity_id, tenant_id=ctx.tenant_id
    )
    return {
        "success": True,
        "data": {
            "opportunity_id": opportunity_id,
            "recommendations": [r.to_dict() for r in recommendations],
        },
    }
```

**完成判定**：`ruff check src/api/routers/sales/opportunities.py` → 0 errors

---

### Step 4: 为 list_opportunities 添加 sort 参数

修改 [TBD - 待验证：确认 sales 路由文件路径] 的 `GET /` 端点函数签名，增加 `sort` Query 参数：

```python
@router.get("/")
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("", description="Sort key, e.g. 'recommendation_priority'"),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
```

在函数体内，当 `sort == "recommendation_priority"` 时，获取所有机会的推荐数据并在内存中按 urgency score 排序：

```python
if sort == "recommendation_priority":
    rec_svc = RecommendationService(session)
    opp_svc = OpportunityService(session)
    items, _ = await opp_svc.list_opportunities(
        tenant_id=ctx.tenant_id, page=1, page_size=1000
    )
    scored = []
    for opp in items:
        recs = await rec_svc.get_recommendations(opp.id, tenant_id=ctx.tenant_id)
        score = max((r.confidence or 0) * (r.risk_severity or 0) for r in recs) if recs else 0.0
        scored.append((score, opp))
    scored.sort(key=lambda x: x[0], reverse=True)
    start = (page - 1) * page_size
    items = [opp for _, opp in scored[start:start + page_size]]
    total = len(scored)
else:
    items, total = await opp_svc.list_opportunities(
        tenant_id=ctx.tenant_id, page=page, page_size=page_size
    )
```

**完成判定**：`grep -n "sort.*recommendation_priority" src/api/routers/sales/opportunities.py` 返回至少 2 行（含 if 判断和 max 计算）

---

### Step 5: 编写单元测试

创建 [TBD - 待验证：确认测试文件路径]，包含以下测试用例：

**Happy path — GET recommendations 返回数据**：
```python
async def test_get_recommendations_returns_data(mock_db_session, mock_recommendation_service):
    router = SalesOpportunitiesRouter(recommendation_service=mock_recommendation_service)
    result = await router.get_opportunity_recommendations(
        opportunity_id=1, ctx=MockAuthContext(tenant_id=1), session=mock_db_session
    )
    assert result["success"] is True
    assert "recommendations" in result["data"]
```

**Boundary — 无推荐时返回空列表**：
```python
async def test_get_recommendations_empty_returns_empty_list(mock_db_session):
    rec_svc = RecommendationService(mock_db_session)
    result = await rec_svc.get_recommendations(opportunity_id=1, tenant_id=1)
    assert result == []
```

**Error — 机会不存在**：
```python
async def test_get_recommendations_opportunity_not_found(mock_db_session):
    with pytest.raises(NotFoundException):
        svc = OpportunityService(mock_db_session)
        await svc.get_opportunity(9999, tenant_id=1)
```

**Sort 参数 — 降序排列**：
```python
async def test_sort_by_recommendation_priority_desc(mock_db_session, mock_recommendation_service):
    items = await mock_recommendation_service.sort_by_urgency([...])
    assert items[0].urgency_score >= items[1].urgency_score
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_sales_opportunities_recommendations.py -v` → ≥ 1 passed---

### Step 6: 运行 lint 和类型检查

```bash
ruff check src/api/routers/sales/opportunities.py src/services/recommendation_service.py
ruff format --check src/api/routers/sales/opportunities.py
```

**完成判定**：两个命令均 exit 0

---

## 6. 验收

- [ ] `ruff check src/api/routers/sales/opportunities.py src/services/recommendation_service.py` → 0 errors
- [ ] `ruff format --check src/api/routers/sales/opportunities.py` → 0 errors（无格式违规）
- [ ] `PYTHONPATH=src pytest tests/unit/test_sales_opportunities_recommendations.py -v` → ≥ 8 passed
- [ ] 端到端：`curl http://localhost:8000/sales/opportunities/1/recommendations` → HTTP 200 + `{"success": true, "data": {"opportunity_id": 1, "recommendations": [...]}`
- [ ] 端到端：`curl "http://localhost:8000/sales/opportunities?sort=recommendation_priority"` → HTTP 200 + 排序后的机会列表

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| RecommendationService.get_recommendations 尚未就绪（本板块依赖 #667 未合并） | 中 | 高 | 本板块阻塞直到 #667 合并；review checklist 中注明 dependency |
| 排序逻辑在大数据量下内存压力（page_size=1000 遍历所有机会） | 低 | 中 | 限制 page_size 最大为 200，超过时截断；不阻塞下游板块 |
| 多租户校验遗漏导致跨 tenant 数据泄露 | 低 | 高 | 上线前做 integration test 渗透测试；不影响下游（纯 API 问题） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/sales/opportunities.py
git add tests/unit/test_sales_opportunities_recommendations.py
git commit -m "feat(sales): add GET /opportunities/{id}/recommendations and sort by priority"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(sales): add recommendations endpoint for opportunities #668" --body "Closes #668"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[TBD - 待验证：确认 sales 路由文件路径] — 现有 `list_opportunities` 端点
- 第三方文档：无
- 父 issue / 关联：#36（父）, #667（依赖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |

-----
