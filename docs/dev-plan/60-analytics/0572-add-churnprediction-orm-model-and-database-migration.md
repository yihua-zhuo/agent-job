# 参考结构（需确认实际文件存在后替换）
class CustomerModel(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### 2.2 涉及文件清单

- 要改：
  - `alembic/env.py` — 新增 `ChurnPrediction` model import，使 autogenerate 可识别
- 要建：
  - `src/db/models/churn_prediction.py` — `ChurnPrediction` ORM model 定义
  - `tests/unit/test_churn_prediction.py` — model 属性单元测试（mock DB）
  - `tests/integration/test_churn_prediction_integration.py` — 真实 DB 表创建和行插入验证
  - `alembic/versions/<id>_create_churn_prediction_table.py` — 表结构迁移脚本

### 2.3 缺什么

- [ ] 无 `ChurnPrediction` ORM model — 无法在 Python 代码中类型化操作 `churn_predictions` 表
- [ ] 无 alembic 迁移脚本 — `churn_predictions` 表未在 DB schema 版本控制中
- [ ] `alembic/env.py` 未导入 `ChurnPrediction` — autogenerate 不会生成该表的 diff
- [ ] 无针对 `ChurnPrediction` model 的单元测试和集成测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/churn_prediction.py` | `ChurnPrediction` ORM model（含 tier Enum、JSONB 列） |
| `alembic/versions/<id>_create_churn_prediction_table.py` | 建表迁移，支持 upgrade / downgrade |
| `tests/unit/test_churn_prediction.py` | model 属性 mock单元测试 |
| `tests/integration/test_churn_prediction_integration.py` | 真实 DB 表创建 + 行插入集成测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `alembic/env.py` | 新增 `from db.models.churn_prediction import ChurnPrediction`；确认 `import_all_models()` 函数中有对应行 |

### 3.3 新增能力

- **ORM model**：`ChurnPrediction` in `src/db/models/churn_prediction.py` — 字段：id、customer_id、tenant_id、score(0-100)、tier(enum)、factors(JSONB)、recommended_actions(JSONB)、model_version、created_at
- **Migration**：`alembic upgrade head` 创建 `churn_predictions` 表（含 `tenant_id` 索引、`customer_id` 索引）
- **Unit test**：验证 model 各字段类型和默认值
- **Integration test**：验证表在真实 Postgres 中可创建、可插入、可查询一行记录

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `sa.JSONB` 不选 `sa.JSON`**：JSONB 在 Postgres 中以二进制存储，支持索引和高效包含查询，适合 `factors` 和 `recommended_actions` 这类需要经常读取的半结构化数据。
- **选 `enum.Enum` Python侧不选 Postgres `ENUM` 类型**：CRM 表中 tier枚举值变化频繁，Postgres ENUM 类型不可逆变更代价高；Python enum 可控性更强，DB侧存 `String`即可。
- **选 `created_at server_default=func.now()` 不选 `default`**：server_default 保证 DB侧时间戳不依赖应用时钟漂移，与项目中其他 model（CustomerModel 等）保持一致。

### 4.2 版本约束

TBD - 待补充：如有新引入的第三方包（如 `alembic~=1.13`以外的版本要求）则填入；否则删除此段或注明「无新依赖」### 4.3 兼容性约束

- 多租户：`churn_predictions` 表必须包含 `tenant_id` 列（非空 +索引），所有 WHERE 查询必须携带 `tenant_id` 过滤（与项目中其他表一致）。
- 表名列名：column name禁止使用 `metadata`（与 `Base.metadata`冲突）— `factors` 和 `recommended_actions` 字段已命名为避免此问题。
- Session注入：任何直接操作 `ChurnPrediction` 的测试使用 `async_session` fixture（非 `async with get_db()`）。
- PYTHONPATH：`PYTHONPATH=src` 生效，import写 `from db.models.churn_prediction import ChurnPrediction` 而非 `from src.db.models.churn_prediction`。

### 4.4 已知坑

1. **Alembic autogenerate 将 `JSONB` 误写为 `JSON`** → 规避：迁移脚本生成后手动检查 `sa.JSON()` 调用处，将 `JSON()`改为 `JSONB()`。
2. **Alembic autogenerate 将 `DateTime(timezone=True)` 误写为 `DateTime(timezone=False)` 或 `DateTime`** → 规避：检查 `created_at` 列的 `DateTime` 调用，确认 `timezone=True` 存在。
3. **`Base.metadata` 与 ORM model 属性名冲突** →规避：`ChurnPrediction` model 的数据列不命名为 `metadata`，使用 `factors` / `recommended_actions` / `event_metadata` 等。
4. **PG table 的 enum 列若写为 `native_enum=True` 后升级不便** → 规避：tier 列在 model侧用 Python `Enum`，DB侧类型设为 `String(50)`，migration阶段不生成 Postgres `CREATE TYPE`。

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 ChurnPrediction ORM model

在 `src/db/models/churn_prediction.py` 中定义 model。

操作：
- a) 创建文件 `src/db/models/churn_prediction.py`
- b) 定义 `tier` Python enum：`High / Medium / Low`
- c) 定义 `ChurnPrediction` 类，继承 `Base`，`__tablename__ = "churn_predictions"`
- d) 列定义：
  - `id: Mapped[int] = mapped_column(Integer, primary_key=True)`
  - `customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)`
  - `tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)`
  - `score: Mapped[int] = mapped_column(Integer, nullable=False, CheckConstraint("score >= 0 AND score <= 100"))`
  - `tier: Mapped[str] = mapped_column(String(50), nullable=False)`
  - `factors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)`
  - `recommended_actions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)`
  - `model_version: Mapped[str] = mapped_column(String(100), nullable=False, default="v1.0")`
  - `created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())`
- e) 确保 `__tablename__` 与迁移目标一致，无复数形式歧义

示例代码：

```python
import enum
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, Enum, String, func, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Dict, List


class ChurnTier(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Base(DeclarativeBase):
    pass


class ChurnPrediction(Base):
    __tablename__ = "churn_predictions"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="churn_score_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    factors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    recommended_actions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False, default="v1.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**完成判定**：`PYTHONPATH=src python -c "from db.models.churn_prediction import ChurnPrediction; print('import ok')"` exit 0

---

### Step 2: 编写 ChurnPrediction model单元测试

操作：
- a) 创建 `tests/unit/test_churn_prediction.py`
- b)引入 `MockState`、`make_mock_session`（或等效 mock session）来测试 model 属性
- c) 测试 `ChurnPrediction` 的 `__tablename__` 值- d) 测试各字段存在性（Mapped 属性可通过 `.__mapper__.columns` 检验 key）
- e) 测试 `ChurnTier` enum 值 `HIGH / MEDIUM / LOW` 可用
- f) 测试 `factors` / `recommended_actions` 默认值类型

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_prediction.py -v` → 全部 passed

---

### Step 3: 生成 alembic 迁移脚本操作：
- a) 启动临时 DB：`docker compose -f configs/docker-compose.test.yml up -d test-db`（或确认已有）
- b) `docker exec <container> psql ... -c "DROP DATABASE IF EXISTS alembic_dev; CREATE DATABASE alembic_dev;"`
- c) 设置 `PYTHONPATH=src` 和 `DATABASE_URL` 环境变量
- d) `alembic upgrade head`（如有历史迁移，先升至 head）
- e) `alembic revision --autogenerate -m "create_churn_predictions_table"`
- f) 手动审查生成的 migration 文件：
  - 确认无 `sa.JSON()`（应为 `sa.JSONB()`）
  - 确认 `created_at` 列有 `timezone=True`
  - 确认 `tier` 列用了 `String(50)` 而非 Postgres ENUM 类型
  - 确认 `downgrade()`包含 `op.drop_table("churn_predictions")`
- g) 测试 upgrade / downgrade 可逆：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 三次 exit 0
- h) 二次 autogenerate 验证（应产生空 migration）：`alembic revision --autogenerate -m "drift_check"` — 若新 migration仅有 `pass`，删除；否则补全

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 4: 更新 alembic/env.py

操作：
- a)打开 `alembic/env.py`，找到 `import_all_models()` 函数或 model import区块
- b) 新增 `from db.models.churn_prediction import ChurnPrediction`
- c) 确认 `Base.metadata` 导入链中可见到 `ChurnPrediction`
- d) 从迁移生成文件（如 Step 3 已生成）可知 `alembic/versions/<id>_create_churn_prediction_table.py` 引用正常**完成判定**：`grep -n "churn_prediction" alembic/env.py` 输出包含该 import 行

---

### Step 5: 编写集成测试

操作：
- a) 创建 `tests/integration/test_churn_prediction_integration.py`
- b) 使用 `db_schema` fixture 创建 schema（所有表由 `create_all`产生，包括 `churn_predictions`）
- c) 使用 `tenant_id` fixture 提供租户隔离
- d) 使用 `async_session` fixture 进行 INSERT + SELECT
- e) 验证步骤：
  - INSERT 一条 `ChurnPrediction`（含 factors JSON、recommended_actions JSON、tier）
  - `.commit()`
  - SELECT回来，`assert row.score == 75` 等断言 - `assert row.tier == "high"`
  - `assert row.factors[0]["name"] == "..."`（JSONB 解序列化验证）

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_churn_prediction_integration.py -v` → 全部 passed

---

### Step 6: 全量 lint + 类型检查

操作：
- a) `PYTHONPATH=src ruff check src/db/models/churn_prediction.py` →0 errors
- b) `PYTHONPATH=src ruff check alembic/versions/` →0 errors（如迁移文件有 syntax 问题）
- c) `PYTHONPATH=src ruff format --check src/db/models/churn_prediction.py` → 通过- d) `PYTHONPATH=src mypy src/db/models/churn_prediction.py` → 无新增错误（按项目配置）

**完成判定**：上述命令全部 exit 0（mypy 如项目本身有 warning 可忽略，但本文件不应引入新 error）

---

## 6. 验收

- `PYTHONPATH=src ruff check src/db/models/churn_prediction.py` → 0 errors
- `PYTOKEN=src ruff check alembic/env.py` → 0 errors（确认 env导入正常）
- `PYTHONPATH=src pytest tests/unit/test_churn_prediction.py -v` →全部 passed
- `PYTHONPATH=src pytest tests/integration/test_churn_prediction_integration.py -v` → 全部 passed
- `PYTHONPATH=src alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0
- `grep -n "churn_prediction" alembic/env.py` → 输出包含 `from db.models.churn_prediction import ChurnPrediction`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Alembic autogenerate未能识别 `ChurnPrediction` model（import遗漏）导致表结构未生成 | 低 | 高 — 集成测试 fail | revert `alembic/env.py` 中的 import 移除，确认 `alembic/versions/<id>_create_churn_prediction_table.py` 已存在则手动 `alembic upgrade<rev>` |
| `JSONB` 误写为 `JSON` 后 PostgreSQL 报错（无 JSON 类型 vs JSONB） | 低 | 高 — 迁移 fail | 手动编辑迁移文件：将 `sa.JSON()` 替换为 `sa.JSONB()`，重新 upgrade |
| 本板块迁移与后续 Sales/Analytics 板块的 model 重叠字段产生冲突（如 `customer_id` join歧义） | 低 | 中 | 后续板块在 service 层 JOIN 查询时显式指定 `churn_predictions.customer_id`，不依赖默认顺序 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/churn_prediction.py \
 alembic/env.py \
      alembic/versions/<id>_create_churn_prediction_table.py \
      tests/unit/test_churn_prediction.py \
      tests/integration/test_churn_prediction_integration.py
git commit -m "feat(analytics): add ChurnPrediction ORM model and migration (closes #572)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): add ChurnPrediction ORM model and migration (closes #572)" --body "## Summary\n- Add `ChurnPrediction` SQLAlchemy ORM model in `src/db/models/churn_prediction.py`\n- Add alembic migration `create_churn_predictions_table`\n- Import model in `alembic/env.py` for autogenerate visibility\n- Add unit and integration tests\n\n## Test plan\n- [x] ruff check src/db/models/churn_prediction.py → 0 errors\n- [x] pytest tests/unit/test_churn_prediction.py -v → passed\n- [x] pytest tests/integration/test_churn_prediction_integration.py -v → passed\n- [x] alembic upgrade head && alembic downgrade -1 && alembic upgrade head → exit 0\n\nCloses #572\nCloses #51 (subtask)"
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/db/models/` 下现有 model（如 Customer / Opportunity）文件作为 ORM风格参考- 第三方文档：[SQLAlchemy 2.x Declarative Mapped](https://docs.sqlalchemy.org/en/20/orm/mapped_config.html)，[Alembic Migration Guide](https://alembic.sqlalchemy.org/en/latest/)
- 父 issue / 关联：#51

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
