# RecommendationModel · 创建 ORM 与迁移

| 元数据 | 值 |
|---|---|
| Issue | #810 |
| 分类 | [20-sales](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | [0811-call-recommendation-llm](../20-sales/0811-add-call-recommendation-llm-method-to-aiagentservice.md), [0812-wire-llm-call](../20-sales/0812-wire-llm-call-into-recommendationservice-get-recommendations.md), [0813-get-recommendations-endpoint](../20-sales/0813-add-get-recommendations-opportunity-id-endpoint.md), [0814-tests-for-llm-recommendation](../20-sales/0814-write-unit-and-integration-tests-for-llm-recommendation-flow.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The recommendation feature (epic #600) needs a persistence layer for LLM-generated call recommendations tied to sales opportunities. Without an ORM model and the corresponding database table, the downstream service (`RecommendationService.get_recommendations`) and the API endpoint (boards #0811-#0813) have nowhere to store or query recommendation data. This board is the foundational data-layer step that the rest of the epic depends on — it introduces the schema, the migration, and the importable model class.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 改动。终端用户将在下游板块 (#0813) 暴露 API 端点后才看到功能。
- **开发者视角**：可 `from db.models.recommendation_model import RecommendationModel`；`RecommendationService` 可通过 `AsyncSession` 对 `recommendations` 表执行 CRUD；`alembic upgrade` / `downgrade` 可管理该表的 schema 演进。

### 1.3 不做什么（剔除）

- [ ] 不实现 LLM 调用逻辑（板 #0811，`AIAgentService` 上的方法）
- [ ] 不实现 `RecommendationService.get_recommendations` 业务方法（板 #0812）
- [ ] 不添加 HTTP API endpoint（板 #0813）
- [ ] 不写单元 / 集成测试的断言逻辑（板 #0814）
- [ ] 不修改任何现有 model / service / router

### 1.4 关键 KPI

- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `PYTHONPATH=src python -c "from db.models.recommendation_model import RecommendationModel"` → exit 0
- `ruff check src/db/models/recommendation_model.py alembic/versions/<id>_add_recommendation_model.py` → 0 errors
- Migration 中 `reasons` / `similar_deals` 列类型为 `sa.JSONB()`（非 `sa.JSON()`），`created_at` 类型为 `sa.DateTime(timezone=True)`

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块

### 2.2 涉及文件清单

- 要改：
  - [`alembic/env.py`](../../../alembic/env.py) — 导入 `RecommendationModel` 以让 `--autogenerate` 能检测到该模型
- 要建：
  - `src/db/models/recommendation_model.py` — 定义 `RecommendationModel` ORM 类（含 JSONB 列、复合索引、`timezone=True` 的 `created_at`）
  - `alembic/versions/<id>_add_recommendation_model.py` — 建表迁移（revision id 由 `alembic revision --autogenerate` 生成）

### 2.3 缺什么

- [ ] `recommendations` 表（id, tenant_id, opportunity_id, next_action, confidence, reasons JSONB, similar_deals JSONB, raw_llm_response, created_at TIMESTAMPTZ）
- [ ] `(tenant_id, opportunity_id)` 复合索引
- [ ] `tenant_id` 单列索引（autogen 默认生成）
- [ ] alembic 对该模型的可管理性（迁移可逆、autogen 能检测到后续 schema 变更）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/recommendation_model.py` | 定义 `RecommendationModel` 映射 `recommendations` 表 |
| `alembic/versions/<id>_add_recommendation_model.py` | 创建 `recommendations` 表 + 复合索引的可逆迁移 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`alembic/env.py`](../../../alembic/env.py) | 在模型导入区块添加 `from db.models.recommendation_model import RecommendationModel`（行号 TBD，见 Step 2） |

### 3.3 新增能力

- **ORM model**：`RecommendationModel` in `src/db/models/recommendation_model.py`，映射 `recommendations` 表；PK = `id`；含 `tenant_id` 单列索引 + `ix_recommendations_tenant_opportunity` 复合索引
- **Migration**：`alembic upgrade head` 创建 `recommendations` 表（列定义见 §1.4 KPI），`alembic downgrade -1` 删除该表

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JSONB over JSON**：`reasons`（dict）与 `similar_deals`（list）需支持嵌套结构与未来可能的 GIN 索引查询。Postgres `JSONB` 以二进制存储并支持索引，查询效率优于纯文本 `JSON`。ORM 端用 `from sqlalchemy.dialects.postgresql import JSONB`，alembic 端用 `sa.JSONB()`。
- **`timezone=True` on `created_at`**：多时区部署要求时间列携带时区信息，避免裸 `DateTime` 被存为 `timestamp without time zone` 导致跨时区比对出错。
- **Composite index `(tenant_id, opportunity_id)`**：`tenant_id` 始终是等值过滤前缀，放在复合索引左侧可让绝大多数查询走 index-only scan；`opportunity_id` 在右侧用于精确匹配。`tenant_id` 单独也保留单列索引（autogen 默认生成），两者不冲突且各自服务不同查询模式。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：`tenant_id` 列必须存在；下游所有 SQL 查询须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- `Base.metadata` 冲突：本表未使用 `metadata` 作为列名（用 `raw_llm_response` 代替），规避 `Base.metadata` 命名碰撞
- Migration 必须可逆：`downgrade()` 必须显式 `op.drop_table("recommendations")`，不可留空
- 不修改任何现有 model / service / router

### 4.4 已知坑

1. **Alembic autogen 把 `JSONB` 写成 `JSON`** → 规避：autogen 后在 `alembic/versions/<id>_add_recommendation_model.py` 中搜 `sa.Column("reasons"` 与 `sa.Column("similar_deals"`，手动将 `sa.JSON()` 改为 `sa.JSONB()`。
2. **Alembic autogen 丢失 `timezone=True`** → 规避：autogen 后检查 `sa.Column("created_at"` 行，确认类型为 `sa.DateTime(timezone=True)`；若缺失手动补上。
3. **模型未在 `alembic/env.py` 导入导致 autogen 漏检** → 规避：所有新模型必须在 `alembic/env.py` 的模型导入区显式 import，否则 `--autogenerate` 看不到差异，会生成仅含 `pass` 的空 migration。
4. **Migration `downgrade()` 留空** → 规避：autogen 通常会填好 `op.drop_table(...)`，但务必人工 review；如空白则手动补全。
5. **autogen 后残余 drift** → 规避：迁移应用并 roundtrip 后再次运行 `alembic revision --autogenerate -m "drift_check"`；若新文件 up/down 都是 `pass`，删除之；否则说明第一次迁移不完整。
6. **PYTHONPATH 缺失导致 import 失败** → 规避：所有 alembic 与 pytest 命令须在 `export PYTHONPATH=src` 后执行（见 CLAUDE.md §Gotchas）。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 ORM 模型文件

新建 `src/db/models/recommendation_model.py`，定义 `RecommendationModel` 映射 `recommendations` 表。

操作：
- a) 在 `src/db/models/` 目录下创建文件 `recommendation_model.py`
- b) 写入以下模型定义：

```python
from datetime import datetime
from sqlalchemy import Integer, String, Float, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class RecommendationModel(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opportunity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    next_action: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    similar_deals: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    raw_llm_response: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_recommendations_tenant_opportunity", "tenant_id", "opportunity_id"),
    )
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.recommendation_model import RecommendationModel"` exit 0

### Step 2: 在 alembic/env.py 中注册模型

让 alembic `--autogenerate` 能感知 `RecommendationModel` 的存在。

操作：
- a) 打开 [`alembic/env.py`](../../../alembic/env.py)
- b) TBD - 待验证：`alembic/env.py` 中模型导入区块的行号 — grep `from db.models` 定位现有 import 列表
- c) 在该 import 列表中添加 `from db.models.recommendation_model import RecommendationModel`（与其他 `from db.models...` import 保持同一 import 风格）

**完成判定**：`grep -n "recommendation_model" alembic/env.py` 命中 ≥ 1 行

### Step 3: 用 autogen 生成迁移

在干净的 `alembic_dev` 数据库上运行 `--autogenerate` 生成迁移文件。

操作：
- a) `export PYTHONPATH=src`
- b) `export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"`
- c) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "DROP DATABASE IF EXISTS alembic_dev;"`（确保干净）
- d) `docker exec configs-test-db-1 psql -U test_user -d postgres -c "CREATE DATABASE alembic_dev;"`
- e) `alembic upgrade head` — 确认 DB 处于当前 head
- f) `alembic revision --autogenerate -m "add_recommendation_model"`
- g) 记录生成的文件名（含 revision id）：`alembic/versions/<id>_add_recommendation_model.py`

**完成判定**：`ls alembic/versions/*add_recommendation_model.py` 命中 1 个文件

### Step 4: 手动修正迁移文件

autogen 不会把 JSONB 与 timezone 处理对，需人工修正。

操作：
- a) 打开 `alembic/versions/<id>_add_recommendation_model.py`
- b) 搜索 `sa.Column("reasons"` → 将 `sa.JSON()` 改为 `sa.JSONB()`
- c) 搜索 `sa.Column("similar_deals"` → 将 `sa.JSON()` 改为 `sa.JSONB()`
- d) 搜索 `sa.Column("created_at"` → 确认类型为 `sa.DateTime(timezone=True)`，若缺失手动补上 `timezone=True`
- e) 确认 `upgrade()` 中包含 `op.create_index("ix_recommendations_tenant_opportunity", "recommendations", ["tenant_id", "opportunity_id"])`；若 autogen 漏掉，手动追加
- f) 确认 `downgrade()` 包含 `op.drop_table("recommendations")`（autogen 通常会填）

**完成判定**：`grep -E "sa.JSONB\(\)" alembic/versions/<id>_add_recommendation_model.py | wc -l` → `2`；`grep "timezone=True" alembic/versions/<id>_add_recommendation_model.py | wc -l` → `>= 1`；`grep "ix_recommendations_tenant_opportunity" alembic/versions/<id>_add_recommendation_model.py | wc -l` → `>= 1`

### Step 5: 验证迁移可逆

在 `alembic_dev` 上跑三段往返 + drift 检查。

操作：
- a) `alembic upgrade head` — exit 0
- b) `alembic downgrade -1` — exit 0
- c) `alembic upgrade head` — exit 0
- d) `alembic revision --autogenerate -m "drift_check"` — 若新文件 up/down 都是 `pass`，删除之；否则说明 Step 4 迁移不完整，需回到 Step 4 补全

**完成判定**：上述四个命令全部 exit 0；drift_check 文件被删除或为空

### Step 6: Lint 检查

确保新文件符合项目 ruff 规范。

操作：
- a) `ruff check src/db/models/recommendation_model.py`
- b) `ruff check alembic/versions/<id>_add_recommendation_model.py`

**完成判定**：两次 `ruff check` 均为 0 errors

---

## 6. 验收

- [ ] `PYTHONPATH=src python -c "from db.models.recommendation_model import RecommendationModel"` → exit 0
- [ ] `grep -n "recommendation_model" alembic/env.py` → ≥ 1 行命中
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- [ ] `alembic revision --autogenerate -m "drift_check"` → 生成的文件 up/down 均为 `pass`（无残余 drift），生成后删除
- [ ] `ruff check src/db/models/recommendation_model.py alembic/versions/<id>_add_recommendation_model.py` → 0 errors
- [ ] `grep -E "sa.JSONB\(\)" alembic/versions/<id>_add_recommendation_model.py | wc -l` → `2`
- [ ] `grep "timezone=True" alembic/versions/<id>_add_recommendation_model.py | wc -l` → `>= 1`
- [ ] `grep "ix_recommendations_tenant_opportunity" alembic/versions/<id>_add_recommendation_model.py | wc -l` → `>= 2`（upgrade + downgrade 各 1）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| autogen 生成空 migration（`RecommendationModel` 未在 `alembic/env.py` 导入） | 低 | 高 | 回退 Step 2 确认 import 已添加；本板块本身不执行 INSERT，不阻塞下游开发（下游可使用 `Base.metadata.create_all` 临时建表） |
| autogen 漏掉复合索引 `ix_recommendations_tenant_opportunity` | 中 | 中 | 在 `upgrade()` 中手动追加 `op.create_index(...)`；下游查询效率退化但功能不阻塞 |
| Migration `downgrade()` 留空导致无法回滚 | 低 | 中 | 手动补 `op.drop_table("recommendations")`；若回退失败，直接 `psql ... -c "DROP TABLE recommendations CASCADE"` 手动清理 |
| `tenant_id` / `opportunity_id` 列类型与现有 `opportunities` 表不一致（如一个用 `Integer`、一个用 `BigInteger`） | 低 | 中 | 模型层固定用 `Integer`（与 `customers.id` / `opportunities.id` 保持一致）；若发现不一致，调整 `RecommendationModel` 列类型并重新生成 migration |
| 漂移检查发现模型与迁移不一致 | 低 | 高 | 删除漂移 migration，回到 Step 3 重新 autogen 并 review Step 4 的手动修正 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/recommendation_model.py alembic/env.py alembic/versions/<id>_add_recommendation_model.py
git commit -m "feat(sales): add RecommendationModel ORM and alembic migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "Add RecommendationModel ORM and migration" --body "Closes #810"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
