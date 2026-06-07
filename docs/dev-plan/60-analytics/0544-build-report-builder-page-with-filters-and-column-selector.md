# 报告构建器页面 · 构建 /analytics/reports 页面含筛选器与列选择器

| 元数据 | 值 |
|---|---|
| Issue | #544 |
| 分类 | 60-analytics |
| 优先级 | 推荐 |
| 工作量 | 2-3 工作日 |
| 依赖 | TBD - 待验证：依赖 #543（Analytics API 基础端点，文件尚未创建或路径待确认） |
| 启用后赋能 | TBD - 待补充：依赖本板块的前端板块（前端展示层） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 CRM 系统缺少结构化的分析报告构建能力。用户无法在界面上选择报表类型、设置日期范围和筛选条件来预览数据，也无法将常用的筛选配置保存为收藏报告。现有的分析数据只能通过手动构造 API 请求获取，门槛高且不可复用。构建报告构建器页面是打通数据分析最后一公里的关键体验功能，也是从 #56 Analytics 模块衍生的明确子任务。

### 1.2 做完后

- **用户视角**：用户访问 `/analytics/reports`，在页面上通过下拉菜单选择报表类型（客户漏斗、销售 pipeline、客服工单等），设置起止日期，勾选团队/成员/地区筛选项，在侧边栏通过复选框选择展示列，点击"预览"后页面内即时展示符合条件的数据摘要。用户可点击"保存为收藏"将当前筛选配置持久化，下次从收藏列表一键加载。
- **开发者视角**：`src/api/routers/analytics_reports.py` 新增 `GET /analytics/reports/preview`（接受 query 参数返回预览数据）和 `POST /analytics/reports/favorites`（保存收藏报告）；`analytics_service.py` 新增 `get_report_preview()` 和 `save_favorite_report()` 方法；前端 `frontend/pages/analytics/reports.tsx` 导出页面组件。

### 1.3 不做什么（剔除）

- [ ] 不实现报表导出功能（导出为 CSV/PDF 由独立 issue 处理）
- [ ] 不实现自定义列排序或列宽拖拽（仅基础复选框选择）
- [ ] 不实现报表调度或邮件推送
- [ ] 不实现行级权限（全部成员筛选项基于现有 tenant_id 隔离）

### 1.4 关键 KPI

- [指标 1：`ruff check src/api/routers/analytics_reports.py src/services/analytics_service.py` → 0 errors]
- [指标 2：`PYTHONPATH=src pytest tests/unit/test_analytics_reports.py -v` → 全 passed（如已有测试）或文件存在]
- [指标 3：`PYTHONPATH=src pytest tests/integration/test_analytics_reports_integration.py -v` → 全 passed（如涉及 DB）]
- [指标 4：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如果新增 migration）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/` 目录下是否有 `analytics_reports.py` 文件（可能由 #543 新建）；`src/services/` 下是否有 `analytics_service.py`；`frontend/pages/analytics/` 目录结构

### 2.2 涉及文件清单

- 要改：
  - `src/services/analytics_service.py` — 新增 `get_report_preview()` 和 `save_favorite_report()` 方法
  - `frontend/pages/analytics/reports.tsx` — 新建报告构建器页面组件（注意：前端文件路径需项目内确认）
- 要建：
  - `src/api/routers/analytics_reports.py` — 报告预览 GET 端点和收藏报告 POST 端点
  - `src/db/models/analytics_report_favorite.py` — 收藏报告 ORM model（如 favorites 需独立表存储）
  - `alembic/versions/<id>_create_analytics_report_favorite.sql` — 创建收藏报告表 migration（如需独立表）
  - `tests/unit/test_analytics_reports.py` — 单元测试
  - `tests/integration/test_analytics_reports_integration.py` — 集成测试（如涉及 DB）

### 2.3 缺什么

- [ ] 无 `/analytics/reports` 前端页面 — 用户无法通过 UI 构建报告
- [ ] 无 `analytics_reports.py` router — 缺少报告预览和收藏报告的后端 API 端点
- [ ] 无收藏报告存储机制 — 需要确定是新建 `analytics_report_favorite` 表还是扩展现有表
- [ ] 无报告预览 service 方法 — `analytics_service` 缺少接收筛选参数并返回预览数据的逻辑
- [ ] 无列选择器与字段映射 — 前端复选框与后端字段名之间无对应关系定义

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `src/api/routers/analytics_reports.py` | 报告预览 GET 端点 + 收藏报告 POST 端点 |
| `src/db/models/analytics_report_favorite.py` | 收藏报告 ORM model（含 tenant_id 索引） |
| `alembic/versions/<id>_create_analytics_report_favorite.py` | 创建收藏报告表的 migration |
| `tests/unit/test_analytics_reports.py` | analytics_reports router/service 单元测试 |
| `tests/integration/test_analytics_reports_integration.py` | 收藏报告 CRUD 集成测试 |
| `frontend/pages/analytics/reports.tsx` | 报告构建器页面（含筛选器 + 列选择器 + 预览面板） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/analytics_service.py` | 新增 `get_report_preview(report_type, filters, tenant_id)` 和 `save_favorite_report(name, config, tenant_id)` 方法 |
| `src/main.py` | 将 `analytics_reports` router 注册到应用（如尚未注册） |

### 3.3 新增能力

- **Service method**：`AnalyticsService.get_report_preview(self, report_type: str, filters: dict, tenant_id: int) -> dict`
- **Service method**：`AnalyticsService.save_favorite_report(self, name: str, config: dict, tenant_id: int) -> FavoriteReportModel`
- **API endpoint**：`GET /analytics/reports/preview?report_type=...&date_from=...&date_to=...&team=...&member=...&region=...` → `{"success": true, "data": {...}}`
- **API endpoint**：`POST /analytics/reports/favorites` body: `{"name": "...", "config": {...}}` → `{"success": true, "data": {"id": N}}`
- **API endpoint**：`GET /analytics/reports/favorites` → `{"success": true, "data": [...]}`
- **ORM model**：`FavoriteReportModel` in `src/db/models/analytics_report_favorite.py`
- **Migration**：`alembic upgrade head` 创建 `analytics_report_favorites` 表（含 `tenant_id` 索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **收藏报告存储在独立表而非 JSONB 列**：`analytics_report_favorites` 独立表使查询和复用更清晰，且支持未来扩展（分享、版本历史），避免单行 JSONB 列内模糊查询的局限。
- **列选择器通过前端配置而非后端硬编码**：将可选列列表定义在前端配置中，后端 `get_report_preview` 接收 `columns: list[str]` 参数按需投影字段，支持零后端改动扩展新列。
- **预览数据返回分页结果**：预览面板每次最多返回 100 条，避免大范围查询拖慢页面；完整导出另作处理。

### 4.2 版本约束

<!-- 无新依赖引入，整段删去 -->

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException`），**不**返回 `ApiResponse.error()`
- Router inject session via `session: AsyncSession = Depends(get_db)`，NEVER use `async with get_db() as session:`
- 列名不能使用 `metadata`（与 `Base.metadata` 冲突）→ 使用 `report_config` / `filter_config` 等替代名称

### 4.4 已知坑

1. **Alembic autogenerate 会将 JSONB 列写成 `sa.JSON()`** → 规避：生成的 migration 中手动将 `Column(JSON())` 改为 `Column(JSONB())`
2. **Alembic autogenerate 可能将带时区的 `DateTime(timezone=True)` 列写成 `DateTime`** → 规避：检查 migration 中的 DateTime 列，必要时手动加上 `timezone=True`
3. **PYTHONPATH=src 必须在所有命令前设置** → import 语句写 `from db.models...` 而不是 `from src.db.models...`
4. **收藏报告表列名不能用 `metadata`** → 使用 `filter_config`（JSONB，存筛选条件）和 `column_config`（JSONB，存选中列）

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 ORM model 和 Migration

在 `src/db/models/` 下新建 `analytics_report_favorite.py`，定义收藏报告表结构：

```python
from datetime import datetime
from sqlalchemy import Integer, String, JSONB, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class FavoriteReportModel(Base):
    __tablename__ = "analytics_report_favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    filter_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    column_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
```

在 `alembic/env.py` 中 import 此 model 后，执行 autogenerate 生成 migration 文件（注意检查 JSONB 和 timezone 参数）。

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 2: 在 AnalyticsService 中添加业务方法

在 `src/services/analytics_service.py` 中添加两个方法：

```python
async def get_report_preview(
    self,
    report_type: str,
    filters: dict,
    columns: list[str],
    tenant_id: int,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    # 根据 report_type 调用对应聚合查询，返回 { "items": [...], "total": N }
    # 投影列由 columns 参数控制，防止注入
    ...

async def save_favorite_report(
    self,
    name: str,
    report_type: str,
    filter_config: dict,
    column_config: list[str],
    tenant_id: int,
    created_by: int,
) -> FavoriteReportModel:
    # INSERT 新记录到 analytics_report_favorites 表
    ...
    return favorite_report
```

**完成判定**：`ruff check src/services/analytics_service.py` → 0 errors

---

### Step 3: 创建 analytics_reports router

在 `src/api/routers/` 下新建 `analytics_reports.py`：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth
from services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics/reports", tags=["Analytics Reports"])


class FavoriteReportCreate(BaseModel):
    name: str
    report_type: str
    filter_config: dict
    column_config: list[str]


@router.get("/preview")
async def get_report_preview(
    report_type: str,
    date_from: str | None = None,
    date_to: str | None = None,
    team: str | None = None,
    member: str | None = None,
    region: str | None = None,
    columns: str | None = None,  # comma-separated
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    filters = {"date_from": date_from, "date_to": date_to, "team": team, "member": member, "region": region}
    col_list = columns.split(",") if columns else []
    result = await svc.get_report_preview(report_type, filters, col_list, tenant_id=ctx.tenant_id)
    return {"success": True, "data": result}


@router.post("/favorites")
async def save_favorite_report(
    body: FavoriteReportCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    fav = await svc.save_favorite_report(
        name=body.name,
        report_type=body.report_type,
        filter_config=body.filter_config,
        column_config=body.column_config,
        tenant_id=ctx.tenant_id,
        created_by=ctx.user_id,
    )
    return {"success": True, "data": fav.to_dict()}


@router.get("/favorites")
async def list_favorite_reports(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(session)
    favs = await svc.list_favorite_reports(tenant_id=ctx.tenant_id)
    return {"success": True, "data": [f.to_dict() for f in favs]}
```

在 `src/main.py` 中注册 router：`app.include_router(analytics_reports.router)`。

**完成判定**：`ruff check src/api/routers/analytics_reports.py` → 0 errors；`curl -X GET http://localhost:8000/analytics/reports/preview?report_type=pipeline` 返回 `{"success": true, ...}`

---

### Step 4: 编写单元测试

在 `tests/unit/test_analytics_reports.py` 中使用 `make_mock_session` 模式测试 router 和 service 方法：

- `test_get_report_preview_returns_filtered_data`
- `test_save_favorite_report_creates_record`
- `test_list_favorite_reports_returns_user_records`

在 `tests/unit/conftest.py` 中按需添加 `make_favorite_report_handler(state)` handler。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_reports.py -v` → 全 passed

---

### Step 5: 编写集成测试

在 `tests/integration/test_analytics_reports_integration.py` 中使用 `db_schema`、`tenant_id`、`async_session` fixtures：

```python
@pytest.mark.integration
class TestAnalyticsReports:
    async def test_save_and_load_favorite_report(self, db_schema, tenant_id, async_session):
        svc = AnalyticsService(async_session)
        fav = await svc.save_favorite_report(
            name="Q1 Pipeline Report",
            report_type="pipeline",
            filter_config={"date_from": "2026-01-01", "date_to": "2026-03-31"},
            column_config=["deal_name", "amount", "stage"],
            tenant_id=tenant_id,
            created_by=1,
        )
        assert fav.id is not None
        favs = await svc.list_favorite_reports(tenant_id=tenant_id)
        assert len(favs) >= 1
```

**完成判定**：`DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_analytics_reports_integration.py -v` → 全 passed

---

### Step 6: 创建前端报告构建器页面

在 `frontend/pages/analytics/reports.tsx`（或项目对应的前端路径）创建页面，包含：

- 报表类型下拉菜单（`report_type`）
- 日期范围选择器（`date_from` / `date_to`）
- 团队/成员/地区筛选复选框或下拉
- 列选择器复选框列表（动态渲染可选列）
- "预览"按钮 → 调用 `GET /analytics/reports/preview` 并渲染结果
- "保存为收藏"按钮 → 调用 `POST /analytics/reports/favorites`
- 收藏报告列表侧边栏 → 调用 `GET /analytics/reports/favorites` 并支持一键加载

**完成判定**：页面文件存在，`ruff check` 对相关后端文件无新增 error

---

## 6. 验收

- [ ] `ruff check src/api/routers/analytics_reports.py src/services/analytics_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics_reports.py -v` → 全 passed
- [ ] `DATABASE_URL="postgresql+asyncpg://..." PYTHONPATH=src pytest tests/integration/test_analytics_reports_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] 端到端：`curl -X GET "http://localhost:8000/analytics/reports/preview?report_type=pipeline&date_from=2026-01-01&date_to=2026-05-31"` 返回 `{"success": true, "data": {"items": [...], "total": N}}`
- [ ] 端到端：`curl -X POST http://localhost:8000/analytics/reports/favorites -H "Content-Type: application/json" -d '{"name":"test","report_type":"pipeline","filter_config":{},"column_config":["amount"]}'` 返回 `{"success": true, "data": {"id": N}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 前端页面路径与模板预期不符（`frontend/pages/analytics/reports.tsx` 不存在） | 中 | 低 | 确认项目前端目录结构，在正确路径下创建文件；后端 API 独立可用 |
| 收藏报告表与其他 analytics 表合并导致 migration 冲突 | 低 | 中 | 如已有类似表，先在 service 层复用；migration 由 #543 的 migration 状态决定顺序 |
| 预览查询在tenant数据量大时超时 | 中 | 中 | 在 service 层添加 `LIMIT page_size` 并设置 `page_size` 上限为 500；前端分页展示 |
| Alembic autogenerate 误将 JSONB 生成 JSON，导致查询失败 | 高 | 高 | 手动修改 migration 中的 `JSON()` 为 `JSONB()`（见 §4.4 已知坑） |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/analytics_reports.py src/services/analytics_service.py src/db/models/analytics_report_favorite.py tests/unit/test_analytics_reports.py tests/integration/test_analytics_reports_integration.py alembic/versions/
git commit -m "feat(analytics): add report builder API and favorites persistence"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): report builder page + favorites API (closes #544)" --body "Closes #544"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 父 issue：#56（Analytics 模块总览）
- 依赖 issue：#543（Analytics API 基础端点）
- 同类参考实现：TBD - 待验证：`src/api/routers/customers.py` — 含筛选参数的 GET 端点参考；`src/services/customer_service.py` — 含 `tenant_id` 的 service 方法参考
- 第三方文档：[FastAPI Query Parameters](https://fastapi.tiangolo.com/tutorial/query-params/)（如需了解 query string 处理）；[React FastAPI Integration Pattern](https://fastapi.tiangolo.com/advanced/using-alternative-fastapi/)（前端对接参考）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
