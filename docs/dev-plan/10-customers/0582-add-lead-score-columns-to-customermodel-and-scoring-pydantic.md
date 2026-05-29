# Lead Scoring · Add score/tier/factors columns to CustomerModel and Pydantic schemas

| 元数据 | 值 |
|---|---|
| Issue | #582 |
| 分类 | 10-customers |
| 优先级 | 推荐 |
| 工作量 | 1 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待补充：依赖 #49 父 issue 的后续板块（如 scoring service / router） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 需要在客户层面持久化潜在客户评分（lead score）的计算结果。现有的 `CustomerModel` 没有评分相关字段，下游的 scoring service / router 无法直接读取已存储的分数，每次计算都要重新跑模型。添加这些字段后，评分结果可持久化、可查询、与工作流挂钩。

### 1.2 做完后

- **用户视角**：无直接可见变化 — 纯底层 schema + ORM 扩展。
- **开发者视角**：`CustomerModel` 新增 `score`、`tier`、`score_factors`、`top_factors`、`recommendations` 属性；`ScoreRequest` / `ScoreResponse` Pydantic schema 供 API 层使用； alembic migration 完成数据库侧变更。

### 1.3 不做什么（剔除）

- [ ] scoring / ranking 算法实现 — 纯数据结构添加，不含业务逻辑
- [ ] API router / endpoint — 仅新增 schema 和 ORM model，不暴露 HTTP 端点
- [ ] 迁移历史数据 — 新增列默认 `NULL`，不进行批量回填
- [ ] 修改现有 `CustomerModel` 以外的任何 model

### 1.4 关键 KPI

- `ruff check src/db/models/customer.py src/services/customer_service.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed（含新列的序列化/反序列化测试）
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- Pydantic schema `ScoreRequest` 和 `ScoreResponse` 可被 `pydantic validate` 成功校验

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：TBD - 待验证：`src/db/models/customer.py` L? — 现有 `CustomerModel` ORM 定义位置

```{python}:src/db/models/customer.py
# 当前 CustomerModel 预期结构（待验证）
class CustomerModel(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # ... 现有字段 ...
```

新建模块时，§2.1 直接写：N/A — 新建模块 → 本 issue 属于 **扩展现有模块**，文件待验证。

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/customer.py` — 新增 5 个评分列（`score`, `tier`, `score_factors`, `top_factors`, `recommendations`）
  - `src/services/customer_service.py` — 若 `to_dict()` 中有硬编码字段列表需同步扩展
  - `tests/unit/test_customer_service.py` — 新增列的序列化测试用例
- 要建：
  - `src/models/score_schemas.py` — `ScoreRequest` / `ScoreResponse` Pydantic schemas（新建 schema 文件，不放在 customer.py 以避免循环依赖）
  - `alembic/versions/<id>_add_lead_score_columns_to_customers.py` — 迁移文件
  - `tests/unit/test_customer_score_schema.py` — schema 校验测试

### 2.3 缺什么

- [ ] `CustomerModel` 无评分列，无法持久化 lead score
- [ ] 无 `ScoreRequest` / `ScoreResponse` Pydantic schema，下游 scoring service 无法类型化请求/响应
- [ ] 无 alembic migration，无法在 schema 层面创建新列
- [ ] 无 `score_factors` / `top_factors` 的 JSONB 列定义（不能用 `metadata` 列名，与 `Base.metadata` 冲突）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/models/score_schemas.py` | `ScoreRequest` / `ScoreResponse` Pydantic schema 定义 |
| `alembic/versions/<id>_add_lead_score_columns_to_customers.py` | 迁移：新增 score/tier/score_factors/top_factors/recommendations 列 |
| `tests/unit/test_customer_score_schema.py` | schema 校验 unit 测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/customer.py` | 新增 `score`（Integer，nullable）、`tier`（String，nullable）、`score_factors`（JSONB，nullable）、`top_factors`（JSONB，nullable）、`recommendations`（JSONB，nullable）列 |
| `src/services/customer_service.py` | 检查并扩展 `to_dict()` 或相关序列化逻辑（如有） |
| `tests/unit/test_customer_service.py` | 新增字段的序列化/反序列化测试用例 |

### 3.3 新增能力

- **ORM model 扩展**：`CustomerModel` 新增 5 个列，全部 nullable
- **Pydantic schemas**：`ScoreRequest`（输入用）、`ScoreResponse`（输出用），与 issue output shape 对齐
- **Migration**：`alembic upgrade head` 创建 5 个新列，均 nullable，无 default，不阻塞现有数据

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **JSONB 而非 JSON**：`score_factors`、`top_factors`、`recommendations` 均为半结构化数据，JSONB 在 PostgreSQL 中支持索引和高效查询，选 `sa.JSON()` → 手动改为 `sa.JSONB()`。
- **全部 nullable**：评分尚未计算时允许 NULL，避免迁移时强制回填；`score` 用 `Integer` 而非 `SmallInteger`，支持 0-100 范围及扩展。
- **独立 schema 文件**：不在 `customer.py` 内混放 Pydantic schema，避免 service 层循环导入。

### 4.2 版本约束

<!-- 无新增外部依赖，整段删除 -->

### 4.3 兼容性约束

- 多租户：新增列无需 tenant_id（已存在于父表），迁移不加额外 tenant_id 索引
- JSONB 列名不能用 `metadata`（与 `Base.metadata` 冲突）→ 使用 `score_factors`、`top_factors`、`recommendations`
- Service 错误抛 `AppException` 子类，不返回 `ApiResponse.error()`

### 4.4 已知坑

1. **Alembic autogen 把 JSONB 写成 JSON** → 手动改 `sa.JSON()` 为 `sa.JSONB()`，并检查 `server_default=None` 是否正确。
2. **Alembic autogen 遗漏 timezone=True** → DateTime 列已有时区意识，新增列无 DateTime 类型，不受影响。
3. **`metadata` 列名与 Base.metadata 冲突** → 确保 `score_factors`、`top_factors`、`recommendations` 列名均不包含 `metadata`。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 Pydantic schema 文件

在 `src/models/` 下新建 `score_schemas.py`，定义 `ScoreRequest` 和 `ScoreResponse`。

操作：
- a) 创建 `src/models/score_schemas.py`
- b) 定义 `ScoreRequest(BaseModel)`：包含所有输入字段（tenant_id、customer_id 等，由 issue output shape 决定）
- c) 定义 `ScoreResponse(BaseModel)`：包含 `score: int | None`、`tier: str | None`、`score_factors: dict | None`、`top_factors: list | None`、`recommendations: list | None`
- d) 导出供其他模块使用

示例代码（如有）：

```python
# src/models/score_schemas.py
from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    customer_id: int
    # ... 其他输入字段


class ScoreResponse(BaseModel):
    score: int | None = None
    tier: str | None = None
    score_factors: dict | None = None
    top_factors: list | None = None
    recommendations: list | None = None
```

**完成判定**：`ruff check src/models/score_schemas.py` → 0 errors

### Step 2: 修改 CustomerModel ORM

在 `src/db/models/customer.py` 的 `CustomerModel` 类中添加 5 个新列。

操作：
- a) 在 `customer.py` 中导入 `JSON`、`JSONB`（或 `JSON` 供后续修正） from `sqlalchemy`
- b) 在 `CustomerModel` 类末尾添加新列定义
- c) 注意：所有列 `nullable=True`，不使用 `default=`

示例代码（如有）：

```python
# src/db/models/customer.py  — 新增列（暂用 JSON，后续迁移前改 JSONB）
score: Mapped[int | None] = mapped_column(Integer, nullable=True)
tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
score_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
top_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.customer import CustomerModel; print(CustomerModel.__table__.columns.keys())"` 不报错

### Step 3: 生成并修复 alembic migration

使用 alembic autogenerate 生成迁移，手动修正 JSON → JSONB。

操作：
- a) 启动 test-db：`docker compose -f configs/docker-compose.test.yml up -d test-db`
- b) 创建 alembic_dev DB（见 CLAUDE.md）
- c) 运行 `alembic revision --autogenerate -m "add lead score columns to customers"`
- d) 打开生成的迁移文件，将 `sa.JSON()` 改为 `sa.JSONB()`
- e) 检查 `server_default=None` 是否存在，不存在需添加 `nullable=True`
- f) 验证：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

**完成判定**：`alembic upgrade head` → exit 0；生成的迁移文件含 `create_table` / `add_column` 语句

### Step 4: 更新 CustomerService 序列化逻辑

若 `customer_service.py` 中有硬编码字段列表（如 `to_dict()` 或 `__mapper__` 相关），检查并同步扩展。

操作：
- a) 读取 `src/services/customer_service.py`
- b) 搜索 `to_dict` 方法或字段序列化逻辑
- c) 如有字段白名单，新增 5 个列名
- d) `ruff check src/services/customer_service.py` → 0 errors

**完成判定**：`ruff check src/services/customer_service.py` → 0 errors

### Step 5: 编写 schema 校验测试

在 `tests/unit/test_customer_score_schema.py` 中测试 `ScoreRequest` 和 `ScoreResponse` 的校验行为。

操作：
- a) 创建 `tests/unit/test_customer_score_schema.py`
- b) 测试 `ScoreResponse` 所有字段可序列化/反序列化
- c) 测试 `score` 范围（0-100 可接受，负数或 >100 可拒绝）
- d) 测试 `score_factors` 接受 dict，`top_factors` 接受 list

示例代码（如有）：

```python
# tests/unit/test_customer_score_schema.py
import pytest
from pydantic import ValidationError
from models.score_schemas import ScoreRequest, ScoreResponse


def test_score_response_all_nullable():
    resp = ScoreResponse()
    assert resp.score is None
    assert resp.tier is None


def test_score_response_valid_data():
    resp = ScoreResponse(
        score=85,
        tier="A",
        score_factors={"engagement": 0.8},
        top_factors=["engagement", "intent"],
        recommendations=["send promo"],
    )
    assert resp.score == 85
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_score_schema.py -v` → 全 passed

### Step 6: 更新 CustomerService unit tests

在 `tests/unit/test_customer_service.py` 中添加新列的序列化测试用例（如果该文件已有 `to_dict` 相关测试）。

操作：
- a) 读取 `tests/unit/test_customer_service.py`
- b) 在现有 customer 相关测试中补充新列断言
- c) 运行 `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/db/models/customer.py src/models/score_schemas.py src/services/customer_service.py` → 0 errors
- [ ] `PYTHONPATH=src python -c "from db.models.customer import CustomerModel; from models.score_schemas import ScoreRequest, ScoreResponse; print('OK')"` → OK
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_score_schema.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/unit/test_customer_service.py -v` → 全 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| JSON vs JSONB 迁移后查询性能差 | 低 | 低 | 手动编辑迁移文件将 `JSON` 改为 `JSONB`，重新 `alembic upgrade head` |
| 新增列与现有 service 字段名冲突 | 低 | 中 | 重命名列（不常见，字段名已避开 `metadata`） |
| alembic autogen 产生空迁移（因目标 DB 已对标 model） | 中 | 中 | 使用 `alembic_env` 检查 Base.metadata 是否正确注册了 `CustomerModel`；必要时用 stamp 标记 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/customer.py src/models/score_schemas.py src/services/customer_service.py
git add alembic/versions/*.py
git add tests/unit/test_customer_score_schema.py tests/unit/test_customer_service.py
git commit -m "feat(customers): add lead_score columns to CustomerModel and Pydantic schemas

Closes #582"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#582): add lead score columns to CustomerModel" --body "Closes #582"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/models/customer.py` — 现有 CustomerModel 结构；`src/models/` 下已有 Pydantic schemas 示例（如有）
- 父 issue / 关联：#49（父 issue lead scoring 项目）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
