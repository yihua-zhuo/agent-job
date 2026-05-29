# CodeReview ORM 模型与迁移 · 添加 CodeReview ORM 模型和数据库迁移

| 元数据 | 值 |
|---|---|
| Issue | #608 |
| 分类 | 00-foundations |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0609-add-codereview-service](../99-misc/0609-add-codereview-service.md), [0610-add-codereview-router](../99-misc/0610-add-codereview-router.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前系统没有代码评审（CodeReview）持久化能力 ——评审结果仅存在于内存或 Ephemeral 状态，无法在多用户、多租户场景下查询历史记录，也无法与其他模块（如 AI Conversation）组合实现更丰富的评审流程。本模块是 foundation 板块，为后续 Service 层和 API Router 提供持久化锚点。

### 1.2 做完后

- **用户视角**：无用户可见变化 —纯底层 ORM + migration。
- **开发者视角**：获得 `CodeReviewModel` ORM 模型，可通过 `CodeReviewService.list_reviews(tenant_id)` 查询评审历史；迁移文件可 `alembic upgrade head` 应用并 `downgrade` 回滚。

### 1.3 不做什么（剔除）

- [ ] 不实现 Service 层（由后续板块 0609 负责）
- [ ] 不实现 Router / API endpoint（由后续板块 0610 负责）
- [ ] 不实现 review_type 枚举的业务校验逻辑（仅存储字段值）

### 1.4 关键 KPI

- `alembic upgrade head` → exit 0，迁移文件被成功应用- `alembic downgrade -1 && alembic upgrade head` → 两次 exit 0（可逆性）
- `ruff check src/db/models/code_review.py` → 0 errors
- `PYTHONPATH=src python -c "from db.models.code_review import CodeReviewModel; print('ok')"` → 输出 `ok`

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块，`src/db/models/code_review.py` 尚不存在。

以同类实现 [`src/db/models/ai_conversation.py`](../../src/db/models/ai_conversation.py) L{1}-L{60} 作为建模参考：

```{python}
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AIConversationModel(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

### 2.2 涉及文件清单

- 要改：
  - 无（`db.models` 通过 `__init__.py` pkgutil 自动发现新 model 文件，无需手动注册）
- 要建：
  - `src/db/models/code_review.py` — `CodeReviewModel` ORM 模型类
  - `alembic/versions/<id>_add_code_reviews.py` — 数据库迁移文件（以下一个 HEAD revision 为 down_revision，暂用 `c94d682d4b03`）

### 2.3 缺什么

- [ ] `src/db/models/code_review.py` 不存在 — 无 `CodeReviewModel` 实体
- [ ] `alembic/versions/` 中无 `add_code_reviews` 迁移 — PostgreSQL 无 `code_reviews` 表
- [ ] 其他服务无法 import 并使用 `CodeReviewModel`（因为模型文件不存在）
- [ ] 无针对 `CodeReviewModel` 的单元测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/code_review.py` | `CodeReviewModel` ORM 模型，含 id/tenant_id/user_id/language/review_type/code_snippet/score/summary/created_at |
| `alembic/versions/<datetime>.py` | 创建 `code_reviews` 表（含 tenant_id 索引），引用 c94d682d4b03 为 down_revision |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| 无需修改 | pkgutil 动态发现新模型文件，无需改动 `__init__.py` 或 `alembic/env.py` |

### 3.3 新增能力

- **ORM model**：`CodeReviewModel` in `src/db/models/code_review.py`
- **DB table**：`code_reviews` 表（含 tenant_id 单列索引 + tenant_id+user_id 复合索引）
- **Migration**：可 `alembic upgrade head` 应用，`alembic downgrade -1` 回滚

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **单文件多字段 vs 多文件分拆**：选单文件 `code_review.py`，按 issue 要求字段集中建模；与 `ai_conversation.py` 风格一致。
- **字符串字段类型**：language 和 review_type 用 `String(50)`，与同类模型（如 `ticket.py` 的 `status`）保持一致；`code_snippet` 和 `summary` 用 `Text` 以容纳长内容。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：`tenant_id` 列必须存在且 `index=True`（与其他所有 model 一致）
- 时间戳：`created_at` 用 `DateTime(timezone=True)` + `server_default=func.now()`，与其他模型一致
- 不使用 `metadata` 列名（与 `Base.metadata` 冲突）—— 本模型无此字段，无需规避
- Async SQLAlchemy：模型继承自 `db.base.Base`，与现有所有模型一致### 4.4 已知坑

1. **Alembic autogen 生成 String(255) 当作 String 列** →规避：迁移文件中手动指定长度上限（如 `String(50)`）
2. **Alembic autogen 对 JSONB 生成 JSON** → 本模型无 JSONB 字段，不受影响
3. **PYTHONPATH=src 必须设置** → 执行任何涉及 import 的命令前必须 `export PYWORDATAURL`，示例命令中已包含---

## 5. 实现步骤（按顺序）

### Step 1: 创建 CodeReview ORM 模型文件

在 `src/db/models/code_review.py` 新建模型文件，字段严格按照 issue 要求：id、tenant_id、user_id、language、review_type、code_snippet、score、summary、created_at。参考 `ai_conversation.py` 的 import风格和 `to_dict()` 模式。

```python
"""CodeReview ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CodeReviewModel(Base):
    """Code review entity mapped to the ``code_reviews`` table."""

    __tablename__ = "code_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    review_type: Mapped[str] = mapped_column(String(50), nullable=False)
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_code_reviews_tenant_user", "tenant_id", "user_id"),
        {"sqlite_autoincrement": True},
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "language": self.language,
            "review_type": self.review_type,
            "code_snippet": self.code_snippet,
            "score": float(self.score) if self.score is not None else None,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.code_review import CodeReviewModel; print('ok')"` → 输出 `ok`

### Step 2: 确认上一个迁移的 revision ID

读取当前最新迁移文件名（`alembic/versions/c94d682d4b03_add_ai_conversations.py`），确认其 revision ID = `c94d682d4b03`，此 ID 将作为新迁移的 `down_revision`。

```bash
head -20 /Users/yihuazhuo/Desktop/git/github/agent-job/alembic/versions/c94d682d4b03_add_ai_conversations.py | grep "revision:"
# 输出: revision: str = 'c94d682d4b03'
```

**完成判定**：输出包含 `c94d682d4b03`

### Step 3: 生成 Alembic 迁移文件

在干净数据库上运行 `alembic revision --autogenerate`，生成 `code_reviews` 表的迁移文件。如 autogen 输出的列类型/默认值与预期不符，手动修正（如 `String()` → `String(50)`，`server_default` 用 `sa.text('now()')` 而非 `func.now()` 等）。

```bash
export PYTHONPATH=src
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
# 创建干净数据库
docker compose -f configs/docker-compose.test.yml up -d test-db
docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"
docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"
alembic upgrade headalembic revision --autogenerate -m "add_code_reviews"
# 如果迁移文件列类型有误，手动编辑修正后继续cat alembic/versions/<新文件名>.py
```

**完成判定**：`alembic/versions/<新文件名>.py` 存在，且 `upgrade()` 包含 `op.create_table('code_reviews', ...)`，`downgrade()` 包含 `op.drop_table('code_reviews')`

### Step 4: 在干净数据库上验证迁移可双向执行

```bash
export PYTHONPATH=src
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**完成判定**：三次命令均 exit 0，无报错

### Step 5: Drift check —确认第二次 autogen 为空

以当前 HEAD 运行第二次 autogenerate，确认无残余 drift（若有 `pass` 之外的内容说明第一次迁移不完整）。

```bash
export PYTHONPATH=src
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:$PATH"
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic revision --autogenerate -m "drift_check"
grep -A 5 "def upgrade\|def downgrade" alembic/versions/<drift文件>.py
```

**完成判定**：新迁移文件中 `upgrade()` 和 `downgrade()` 体仅含 `pass`，无其他操作### Step 6: Lint + 导入验证

```bash
export PYTHONPATH=src
ruff check src/db/models/code_review.py
python -c "from db.models.code_review import CodeReviewModel; print('import ok')"
```

**完成判定**：`ruff check` exit 0，`python` 输出 `import ok`

---

## 6. 验收

- [ ] `ruff check src/db/models/code_review.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.code_review import CodeReviewModel; print('ok')"` → 输出 `ok`
- [ ] `alembic upgrade head` → exit 0，迁移文件被应用
- [ ] `alembic downgrade -1` → exit 0，`code_reviews` 表被删除- [ ] `alembic upgrade head` → exit 0，迁移可重新应用
- [ ] drift check autogenerate → `upgrade()`/`downgrade()` 体仅含 `pass`（无遗漏改动）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| migration 列类型 autogen 有误（如 String 无长度） | 中 | 高 |手动修正迁移文件中 `sa.Column(...)` 参数后重跑；不影响下游板块（0609 依赖本板块合并后接入即可） |
| 表名与已有表冲突 | 低 | 高 | 降级：`alembic downgrade -1` 删除冲突表；改动 model 的 `__tablename__` 后生成新迁移 |
| pkgutil 未发现新 model（罕见环境问题） | 低 | 低 | 将 `from db.models.code_review import CodeReviewModel` 添加至 `src/db/models/__init__.py` 显式导入作为兜底 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/code_review.py "alembic/versions/<migration_file>.py"
git commit -m "feat(foundations): add CodeReview ORM model and migrationCloses #608"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#608): add CodeReview ORM model and migration" --body "Closes #608"

# 2. 更新本板块文档
# docs/dev-plan/00-foundations/0608-add-codereview-orm-model-and-migration.md §Changelog 表格新增一行
```

---

## 9. 参考

- 同类参考实现：[`src/db/models/ai_conversation.py`](../../src/db/models/ai_conversation.py) — 相同 ORM 建模模式
- 父 issue：#44

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
