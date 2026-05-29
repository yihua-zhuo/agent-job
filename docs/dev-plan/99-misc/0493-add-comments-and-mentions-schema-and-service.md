# Comments & @Mentions Schema and Service · Add Comment ORM model and router endpoint

| 元数据 | 值 |
|---|---|
| Issue | #493 |
| 分类 | `20-sales` |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [Add Activity Timeline Schema and Service · #492](../20-sales/0492-add-activity-timeline-schema-and-service.md) |
| 启用后赋能 | 新建 CommentService 的各 consumer 模块；未来 frontend实时推送 subtask 依赖本板块 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 CRM 系统没有评论能力——用户无法在工单（ticket）、销售机会（opportunity）等工作项下发起讨论、记录备注，也无法通过 `@mentions`唤起特定协作者。产品需求（父 issue #80）将评论列为基础原子能力，所有后续工作项（任务、线索、工单等）都依赖这套统一的评论 schema。与其各自实现，不如一开始就建立统一的 `Comment` 模型和服务层，避免后续拆改。

### 1.2 做完后

- **用户视角**：[工单详情页、机会详情页等] 接口 GET `/resources/{type}/{id}/comments` 返回评论列表；创建评论时输入 `@username` 可自动生成提及通知。纯底层 API——前端 subtask 负责 UI 层渲染。
- **开发者视角**：`CommentService` 提供 `create()`, `list()`, `mention_notifications()`三个方法，可直接组合进各业务 service；`Comment` ORM 模型可在任何需要评论的地方 `relationship` 进来，无需重复建表。

### 1.3 不做什么（剔除）

- [ ] 实时推送（WebSocket / SSE）——那是 frontend subtask 的范围，本板块只提供 API 端点。
- [ ] 评论编辑 / 删除——不在 #80 scope 内，后续单独 issue 处理。
- [ ] 文件附件上传——评论 body 仅支持纯文本，最大长度4000 字符。
- [ ] 通知发送（邮件 / in-app push）——`mention_notifications()` 只返回待发送的通知列表，发送逻辑由 consumer 模块负责。

### 1.4 关键 KPI

- [ ] `PYTHONPATH=src pytest tests/unit/test_comment_service.py -v` → `≥ 6 passed`（create + list + mention_notifications 共6 个 cases）
- [ ] `PYTHONPATH=src pytest tests/integration/test_comment_integration.py -v` → 全 passed
- [ ] `ruff check src/services/comment_service.py src/models/comment.py src/api/routers/comment.py` → 0 errors
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `curl http://localhost:8000/resources/ticket/1/comments` → HTTP 200，`{"success": true, "data": {"items": [], "total": 0}}`

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - `alembic/env.py` — 新增 `Comment` model import，使 autogen 可发现- 要建：
  - `src/db/models/comment.py` — `Comment` ORM model（含 `to_dict()`）
  - `alembic/versions/<id>_create_comment_table.py` — 建表 migration  - `src/services/comment_service.py` — `CommentService`（`create`, `list`, `mention_notifications`）
  - `src/api/routers/comment.py` — `GET /resources/{type}/{id}/comments` 路由
  - `tests/unit/test_comment_service.py` — 单元测试（MocDB）
  - `tests/integration/test_comment_integration.py` — 集成测试（真实 DB）

### 2.3 缺什么

- [ ] `Comment` ORM model——当前无评论模型，工单/机会等资源无关联评论表
- [ ] `CommentService` — 缺少统一的评论创建 /列表 / mentions 通知生成业务逻辑
- [ ] `GET /resources/{type}/{id}/comments` 路由——无评论查询端点
- [ ] 单元测试和集成测试覆盖——防止 schema变更引发回归
- [ ] `__init__.py` export——各模块 `__init__.py` 需 export 新增的 class

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/comment.py` | `Comment` ORM 模型：id, resource_type, resource_id, tenant_id, author_id, body, mentions (JSONB), created_at |
| `alembic/versions/<id>_create_comment_table.py` | 建表 +索引 migration（resource_id + tenant_id 复合索引；tenant_id 独立索引） |
| `src/services/comment_service.py` | `CommentService`（session in, no default）：`create()`, `list()`, `mention_notifications()` |
| `src/api/routers/comment.py` | `GET /resources/{type}/{id}/comments` 路由（分页，tenant 隔离） |
| `tests/unit/test_comment_service.py` | 单元测试：MockDB 覆盖 create / list / mentions |
| `tests/integration/test_comment_integration.py` | 集成测试：Docker Postgres，真实 schema |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `alembic/env.py` | import `Comment` from `db.models.comment`，使 autogen 可见 |
| `src/db/models/__init__.py` | export `Comment` |
| `src/services/__init__.py` | export `CommentService` |
| `src/api/routers/__init__.py` | export comment router 并注册到 `api_router` |

### 3.3 新增能力

- **ORM model**：`Comment` (src/db/models/comment.py)——含 `to_dict()`，与 `Base`兼容，支持多租户过滤
- **Service method**：`CommentService.create(session, tenant_id, author_id, resource_type, resource_id, body, mentions) -> Comment`
- **Service method**：`CommentService.list(session, tenant_id, resource_type, resource_id, page, page_size) -> tuple[list[Comment], int]`
- **Service method**：`CommentService.mention_notifications(session, comment: Comment) -> list[dict]`（返回待发通知列表）
- **API endpoint**：`GET /resources/{type}/{id}/comments` → `{"success": true, "data": {"items": [...], "total": N}}`
- **Migration**：`alembic upgrade head` 创建 `comment` 表（含 JSONB 列 `mentions` 和索引）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **`resource_type` 存字符串而非枚举**：CRM 内评论可附属于多种资源（ticket / opportunity / task / customer），改用枚举表需要频繁新增记录维护，不如存 string，database schema 用 CHECK constraint 限制合法值。
- **`mentions` 存 JSONB 而非关联表**：mentions 语义上是"评论中提到的用户列表"，低频更新，没必要拆成 `comment_mention` 关联表。JSONB 可直接索引 `{user_id}` 进行通知派发。
- **路由路径 `/resources/{type}/{id}/comments` 不抽象**：RESTful 风格，`/resources` 前缀统一表达"附属于任意资源"，避免每个资源单独建路由。

### 4.2 版本约束

无新外部依赖。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`
- 路由注入 session：`session: AsyncSession = Depends(get_db)`，禁止 `async with get_db()`
- Service `__init__`：`def __init__(self, session: AsyncSession)`，无默认值
- Service 返回 ORM 对象，不在 service 层调用 `.to_dict()`，序列化由 router 负责
- Service错误抛 `AppException` 子类，不返回 ApiResponse.error()
- 字段名禁止使用 `metadata`（与 SQLAlchemy `Base.metadata` 冲突）——本板块用 `mentions` 存储提及列表，安全### 4.4 已知坑

1. **Alembic autogen 误写 JSON 为 JSONB** → 规避：检查 migration 文件，手动将 `sa.JSON()` 改为 `sa.JSONB()`，尤其是 `mentions` 列
2. **Alembic autogen 漏写 `timezone=True` on DateTime 列** → 规避：检查 `created_at` 列定义，手动补上 `timezone=True`（PostgreSQL TIMESTAMPTZ）
3. **`mentions` 内容格式** → 要求：`mentions` 为 `[{user_id: int, username: str}]` 结构的 JSONB，调用方在 `create()` 前负责验证 usernames合法，不在 service 层做 name → user_id 的二次查询
4. **`resource_type` 未做 CHECK constraint** → 规避：在 migration 中添加 `CHECK (resource_type IN ('ticket', 'opportunity', 'task', 'customer'))`，防止脏数据

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 Comment ORM model

在 `src/db/models/comment.py` 新建 `Comment` 类，继承 `Base`。参照现有 model（如 `ticket.py`）的结构：

- `__tablename__ = "comment"`
- 字段：`id` (PK, autoincrement), `resource_type` (String(50), NOT NULL), `resource_id` (Integer, NOT NULL), `tenant_id` (Integer, NOT NULL, index=True), `author_id` (Integer, NOT NULL), `body` (Text, max 4000字符), `mentions` (JSONB, 默认空数组), `created_at` (DateTime(timezone=True), server_default now())
- 索引：`(resource_type, resource_id, tenant_id)` 复合索引；`tenant_id` 独立索引
- CHECK constraint：`resource_type IN ('ticket', 'opportunity', 'task', 'customer')`
- `to_dict()` 方法，返回 dict，含 `id, resource_type, resource_id, author_id, body, mentions, created_at`

**完成判定**：`PYTHONPATH=src python -c "from db.models.comment import Comment; print('OK')"` → 输出 `OK`

### Step 2: 注册 model 并生成 Alembic migration

a) 在 `src/db/models/__init__.py` 添加 `from .comment import Comment` 并 export
b) 在 `alembic/env.py` 添加 `from db.models.comment import Comment`
c) 运行 autogen 命令（启动 `alembic_dev` DB 并执行 `alembic revision --autogenerate -m "create comment table"`）生成 `alembic/versions/<id>_create_comment_table.py`
d) 审查 migration 文件，手动修复以下两项：
   - `mentions` 列的 `Type` 从 `JSON` 改为 `JSONB`
   - `created_at` 列加上 `timezone=True`
e) 删除 drift_check 空 migration（如有）

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

### Step 3: 实现 CommentService

在 `src/services/comment_service.py` 新建 `CommentService` 类：

```python
from sqlalchemy import select, funcfrom sqlalchemy.ext.asyncio import AsyncSession
from db.models.comment import Comment

class CommentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        tenant_id: int,
        author_id: int,
        resource_type: str,
        resource_id: int,
        body: str,
        mentions: list[dict] | None = None,
    ) -> Comment:
        comment = Comment(
            tenant_id=tenant_id,
            author_id=author_id,
            resource_type=resource_type,
            resource_id=resource_id,
            body=body,
            mentions=mentions or [],
        )
        self.session.add(comment)
        await self.session.commit()
        await self.session.refresh(comment)
        return comment

    async def list(
        self,
        tenant_id: int,
        resource_type: str,
        resource_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Comment], int]:
        base_q = select(Comment).where(
            Comment.tenant_id == tenant_id,
            Comment.resource_type == resource_type,
            Comment.resource_id == resource_id,
        )
        count_q = select(func.count()).select_from(base_q.subquery())
        count_result = await self.session.execute(count_q)
        total = count_result.scalar_one()
        offset = (page - 1) * page_size
        data_q = base_q.order_by(Comment.created_at.desc()).offset(offset).limit(page_size)
        result = await self.session.execute(data_q)
        return list(result.scalars().all()), total
```

`mention_notifications()` 返回通知列表（邮件/in-app push 发送逻辑由 consumer 负责，不在本板块）：

```python
    async def mention_notifications(self, comment: Comment) -> list[dict]:
        if not comment.mentions:
            return []
        return [
            {"user_id": m["user_id"], "username": m["username"], "comment_id": comment.id}
            for m in comment.mentions
        ]
```

**完成判定**：`ruff check src/services/comment_service.py` →0 errors

### Step 4: 实现 GET /resources/{type}/{id}/comments 路由

在 `src/api/routers/comment.py` 新建 router：

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from dependencies.fastapi_auth import AuthContext, require_auth
from services.comment_service import CommentService

router = APIRouter(prefix="/resources", tags=["Comments"])

@router.get("/{resource_type}/{resource_id}/comments")
async def list_comments(
    resource_type: str,
    resource_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = CommentService(session)
    items, total = await svc.list(
        tenant_id=ctx.tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        page=page,
        page_size=page_size,
    )
    return {
        "success": True,
        "data": {
            "items": [c.to_dict() for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }
```

将 router 注册到 `src/api/routers/__init__.py` 的 `api_router`。

**完成判定**：`ruff check src/api/routers/comment.py` →0 errors；`curl http://localhost:8000/resources/ticket/1/comments` → 200### Step 5: 编写单元测试

在 `tests/unit/test_comment_service.py` 编写 6 个测试 cases：

- `test_create_comment_success` — MockDB 验证 CommentService.create 返回 ORM 对象，数据正确持久化
- `test_create_comment_with_mentions` — mentions 为 `[{user_id:42, username: "alice"}]` 时，comment.mentions 正确存储
- `test_list_comments_empty` —资源无评论时返回 `([], 0)`
- `test_list_comments_paginated` — 分页参数 page/page_size正确生效
- `test_list_comments_tenant_isolation` — 跨 tenant 查询隔离- `test_mention_notifications_returns_list` — 调用 `mention_notifications()` 返回正确格式的 dict列表

每个测试使用 `make_mock_session` 配合自定义 handler，不依赖全局 autouse patch。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_comment_service.py -v` → `6 passed`

### Step 6: 编写集成测试

在 `tests/integration/test_comment_integration.py` 新建：

```python
@pytest.mark.integration
class TestCommentService:
    async def test_create_and_list(self, db_schema, tenant_id, async_session):
        svc = CommentService(async_session)
        c = await svc.create(tenant_id=tenant_id, author_id=1, resource_type="ticket",
                             resource_id=100, body="Test comment")
        assert c.id is not None
        items, total = await svc.list(tenant_id, "ticket", 100)
        assert total == 1
        assert items[0].body == "Test comment"

    async def test_tenant_isolation(self, db_schema, tenant_id, async_session):
        # 用另一个 tenant_id 验证隔离        svc = CommentService(async_session)
        await svc.create(tenant_id=tenant_id, author_id=1, resource_type="ticket",
                         resource_id=1, body="A")
        await svc.create(tenant_id=tenant_id + 9999, author_id=1, resource_type="ticket",
                         resource_id=1, body="B")
        items, total = await svc.list(tenant_id, "ticket", 1)
        assert total == 1
```

**完成判定**：`DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db" PYTHONPATH=src pytest tests/integration/test_comment_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/models/comment.py src/services/comment_service.py src/api/routers/comment.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.comment import Comment; from services.comment_service import CommentService; print('import OK')"` → 输出 `import OK`
- [ ] `PYTHONPATH=src pytest tests/unit/test_comment_service.py -v` → `6 passed`
- [ ] `PYTHONPATH=src pytest tests/integration/test_comment_integration.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] 启服务后 `curl -s http://localhost:8000/resources/ticket/1/comments` → `{"success": true, "data": {"items": [], "total": 0, "page": 1, "page_size": 20}}`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| migration 改动 `mentions` JSONB错误导致 PostgreSQL 拒绝建表 | 低 | 高 | 删除 migration，手动写正确的 `CREATE TABLE` 语句 |
| `resource_type` CHECK constraint 过严，未来需要新资源类型 | 中 | 中 | 通过 ALTER TABLE ADD CONSTRAINT 新增合法值，不阻塞下游 |
| CommentService.list 被错误调用导致跨 tenant 数据泄露 | 低 | 高 | 单元测试覆盖 tenant隔离 case；integration test 用两个 tenant_id 验证 |
| 依赖 #492 尚未合并，导致 import错误 | 中 | 中 | 本板块可独立开发，通过 mock import绕过；等 #492 merge 后更新 import |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/comment.py src/services/comment_service.py src/api/routers/comment.py \
       alembic/versions/*.py tests/unit/test_comment_service.py tests/integration/test_comment_integration.py \
       src/db/models/__init__.py src/services/__init__.py src/api/routers/__init__.py alembic/env.py
git commit -m "feat(comments): add Comment ORM, CommentService, and GET /resources/{type}/{id}/comments endpoint

Closes #493"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#493): add Comment schema, service, and router" --body "Closes #493"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/db/models/ticket.py` — 现有 ticket 模型的字段结构、索引策略、to_dict() 实现方式
- 同类参考实现：`src/services/ticket_service.py` — Service模式（`__init__` session注入，`async def` 方法）
- 同类参考实现：`src/api/routers/tickets.py` — Router注入 `Depends(require_auth)`、`Depends(get_db)` 并返回 pagination envelope 的写法
- 父 issue /关联：#80（产品需求父 issue），#492（schema 层依赖，CommentService 需等 ORM model 就绪后方可 integration test）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
