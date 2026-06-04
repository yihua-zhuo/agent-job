# 营销服务 · 添加单元测试与 Alembic 迁移

| 元数据 | 值 |
|---|---|
| Issue | #760 |
| 分类 | [40-campaigns](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | TBD - 待验证：关联 issue #759 的 ORM 模型定义文档路径 |
| 启用后赋能 | TBD - 待验证：依赖板块 README路径 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

MarketingService 在 #759 中新增了 ORM 模型，但目前没有任何单元测试覆盖其 service 方法。这意味着无法在不启动真实数据库的情况下验证业务逻辑正确性，也不满足项目的测试覆盖率要求。每个新增 service 必须配有 `tests/unit/test_<svc>.py`，使用 MockState + make_mock_session 模式隔离数据库依赖。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层测试与迁移补充。
- **开发者视角**：可运行 `pytest tests/unit/test_marketing_service.py -v` 验证 MarketingService 各方法（增删改查 + 错误路径），并通过 `alembic upgrade head` 将模型变更同步至 alembic_dev 数据库。

### 1.3 不做什么（剔除）

- [ ] 不在真实 PostgreSQL 上运行集成测试（集成测试在单独 issue 中覆盖）
- [ ] 不修改已有的 CustomerService / SalesService 等其他 service 及其测试

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v` → ≥10 passed]
- [指标 2：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0]
- [指标 3：`ruff check src/services/marketing_service.py tests/unit/test_marketing_service.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

MarketingService 及相关 ORM 模型在依赖板块 #759 中定义。当前状态：

- MarketingService 已在 `src/services/marketing_service.py` 中实现（#759）
- 对应 ORM 模型已在 `src/db/models/` 下创建（#759）
- 无单元测试文件 `tests/unit/test_marketing_service.py`
- 无 Alembic 迁移文件 `alembic/versions/<id>_create_marketing_tables.py`

TBD - 待验证：`src/services/marketing_service.py` — 确认 service 方法列表（应包含 create / get / update / delete / list 等方法名及签名）
TBD - 待验证：`src/db/models/marketing*.py` — 确认模型文件名及字段定义

### 2.2 涉及文件清单

- 要改：
  - `src/services/marketing_service.py` — 已有实现，无需改动（测试方编写测试用例覆盖之）
- 要建：
  - `tests/unit/test_marketing_service.py` — MarketingService 单元测试，≥10 个测试用例
  - `alembic/versions/<id>_create_marketing_tables.py` — #759 新模型的 Alembic 迁移（若 #759 已建则跳过，否则需生成）
  - `alembic/env.py` — 确认 Marketing 模型已 import（若缺失则补充）

### 2.3 缺什么

- [ ] 无 `tests/unit/test_marketing_service.py` — 无法在 CI 中验证 MarketingService 行为
- [ ] 无 Alembic 迁移 — 若 #759 新模型未生成迁移，则数据库无法通过 `alembic upgrade head` 同步 schema
- [ ] Migration 可能存在 sa.JSON / DateTime timezone 偏差（alembic autogen 常见问题），需手动修正

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `tests/unit/test_marketing_service.py` | MarketingService 单元测试，≥10 个测试用例（每方法含 happy-path + error-path） |
| `alembic/versions/<id>_create_marketing_tables.py` | 为 #759 新增的 Marketing ORM 模型生成数据库迁移 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `alembic/env.py` | 确认 import 了 #759 新增的 Marketing ORM 模型（若未 import 则补充） |

### 3.3 新增能力

- **Unit test**：10+ 个测试用例覆盖 MarketingService 所有 public 方法
- **Mock session fixture**：`test_marketing_service.py` 内定义 `mock_db_session` fixture，使用 `make_mock_session` + 必要 domain handlers
- **Alembic migration**：生成并修正 `alembic/versions/` 下的迁移文件（JSONB / timezone 修正）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **复用 MockState + make_mock_session，不新建 mock 框架**：遵循项目现有约定，每个 unit test 文件自持 fixture，不引入 pytest-mock 或 unittest.mock，确保测试风格一致且运行速度快（<5s）。
- **在 alembic_dev 而非 test_db 上 autogenerate**：test_db 由 `create_all` 管理，autogenerate 会产生空 diff。严格使用专用 disposable 数据库进行迁移生成。

### 4.2 版本约束

<!-- 无新增外部依赖，整段删除 -->

### 4.3 兼容性约束

- 多租户：所有 mock handler 中的 SQL WHERE 子句必须包含 `tenant_id`
- 测试 fixture 中 Service 构造：`MarketingService(mock_db_session)`，session 参数无默认值
- Service 抛异常（`NotFoundException` 等），测试用 `pytest.raises()` 验证
- import 路径：`from services.marketing_service import MarketingService`（PYTHONPATH=src，不写 `from src.services...`）

### 4.4 已知坑

1. **Alembic autogenerate 将 JSONB 写成 `sa.JSON()`** → 规避：迁移生成后手动将 `sa.JSON()` 改为 `sa.JSONB()`
2. **Alembic autogenerate 将 `TIMESTAMPTZ` 写成 `sa.DateTime()`（丢失 `timezone=True`）** → 规避：检查所有时间戳列，手动补回 `timezone=True`
3. **autogenerate 对新表的第一个 migration 可能为空（当 ORM 模型已被 `Base.metadata.create_all` 覆盖时）** → 规避：始终在干净的 alembic_dev 数据库上运行 autogenerate，完成后验证 `alembic upgrade head` 确实执行了 DDL

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 #759 产物与迁移缺口

确认 #759 已完成的工作内容：Marketing ORM 模型文件名、字段定义，以及是否已生成 Alembic 迁移。

操作：
- a) 读取 `src/services/marketing_service.py` 列出所有 public 方法（`async def` 方法）
- b) 读取 `src/db/models/` 下所有 marketing 相关模型文件，记录字段名和类型
- c) 检查 `alembic/versions/` 是否存在针对这些模型的迁移文件
- d) 读取 `alembic/env.py` 确认相关模型已 import

**完成判定**：`ls src/db/models/marketing*.py` 找到文件 / `ls alembic/versions/*marketing*.py` 找到或不找迁移（确认是否需要生成）

---

### Step 2: 生成 Alembic 迁移（如缺失）

若 #759 未生成迁移，按以下步骤生成：

操作：
- a) 启动 clean alembic_dev 数据库（docker compose -f configs/docker-compose.test.yml up -d test-db；然后 DROP + CREATE DATABASE alembic_dev）
- b) 确认 `alembic/env.py` 已 import 所有新模型
- c) `export PYTHONPATH=src && export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev" && alembic upgrade head`
- d) `alembic revision --autogenerate -m "create marketing tables"`
- e) 读取生成的迁移文件，手动修正 `sa.JSON()` → `sa.JSONB()`，`sa.DateTime()` → `sa.DateTime(timezone=True)`（针对 TIMESTAMPTZ 列）
- f) 验证：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 三次 exit 0

示例（迁移修正片段）：

```python
# alembic/versions/<id>_create_marketing_tables.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "marketing_campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("config", sa.JSONB(), nullable=True),  # 修正：sa.JSON() → sa.JSONB()
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),  # 修正：补 timezone=True
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_marketing_campaigns_tenant_id", "marketing_campaigns", ["tenant_id"])
```

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0

---

### Step 3: 编写单元测试框架（fixture 定义）

在 `tests/unit/test_marketing_service.py` 中定义 `mock_db_session` fixture。

操作：
- a) 创建 `tests/unit/test_marketing_service.py`
- b) 从 `tests/unit/conftest.py` import：`make_mock_session`, `MockState`，以及所需 domain handlers（参考 #759 模型涉及的表，调用对应的 `make_<entity>_handler(state)`）
- c) 若 conftest.py 缺少某个 handler，先在 conftest.py 添加该 handler，再在测试文件中使用
- d) 定义 `mock_db_session` fixture 与 `marketing_service` fixture

示例代码：

```python
# tests/unit/test_marketing_service.py
import pytest
from tests.unit.conftest import (
    make_mock_session,
    MockState,
    make_marketing_handler,  # 若已存在于 conftest.py
)

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_marketing_handler(state)])

@pytest.fixture
def marketing_service(mock_db_session):
    from services.marketing_service import MarketingService
    return MarketingService(mock_db_session)
```

**完成判定**：`ruff check tests/unit/test_marketing_service.py` → 0 errors

---

### Step 4: 编写 Happy-path 测试用例

为 MarketingService 每个 public 方法编写成功路径测试（每方法 1-2 个用例）。

操作：
- a) 编写 `test_create_campaign`、`test_get_campaign`、`test_update_campaign`、`test_delete_campaign`、`test_list_campaigns` 等
- b) 使用 `MockState` 预设测试数据
- c) 调用 `marketing_service` 方法，assert 返回值符合预期（ORM 对象属性验证）

示例代码：

```python
@pytest.mark.asyncio
async def test_create_campaign_success(marketing_service, mock_db_session):
    from tests.unit.conftest import MockRow
    result = await marketing_service.create_campaign(
        tenant_id=1,
        name="Spring Campaign",
        config={"channel": "email"},
    )
    assert result.name == "Spring Campaign"
    assert result.tenant_id == 1
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v -k "success or get or list"` → 对应用例 passed

---

### Step 5: 编写 Error-path 测试用例

为每个方法编写错误路径测试（NotFoundException、ValidationException 等）。

操作：
- a) 编写 `test_get_campaign_not_found`、`test_update_campaign_not_found`、`test_delete_campaign_not_found` 等
- b) 使用 `pytest.raises(NotFoundException)` 验证异常抛出
- c) 编写 `test_create_campaign_validation_error` 等，验证参数校验异常

示例代码：

```python
@pytest.mark.asyncio
async def test_get_campaign_not_found(marketing_service):
    from pkg.errors.app_exceptions import NotFoundException
    with pytest.raises(NotFoundException):
        await marketing_service.get_campaign(campaign_id=9999, tenant_id=1)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v -k "not_found or validation"` → 对应用例 passed

---

### Step 6: 验收测试覆盖与迁移完整性

运行完整测试套件并验证 Alembic 迁移。

操作：
- a) `PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v` — 确认 ≥10 passed
- b) `ruff check src/services/marketing_service.py tests/unit/test_marketing_service.py` — 0 errors
- c) `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` — 三次 exit 0

**完成判定**：上述三条命令全部通过

---

## 6. 验收

- [ ] `ruff check src/services/marketing_service.py tests/unit/test_marketing_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_marketing_service.py -v` → ≥10 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如迁移文件已生成）
- [ ] `PYTHONPATH=src mypy src/services/marketing_service.py` → 0 errors（如 mypy 配置存在）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| conftest.py 缺少必要 domain handler | 中 | 中 | 在 conftest.py 中新增 handler（参考现有 `make_customer_handler` 模式），不阻塞其他板块 |
| autogenerate 产生空迁移（因模型已在 Base.metadata） | 低 | 高 | 改用手动编写迁移而非 autogenerate；使用 `op.create_table()` 显式声明所有列 |
| 迁移修正后遗漏某列导致真实 DB schema 不全 | 低 | 高 | 在 alembic_dev 上验证 `alembic upgrade head` 输出含所有 CREATE TABLE / ADD COLUMN 语句 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_marketing_service.py alembic/versions/ alembic/env.py
git commit -m "test(marketing): add unit tests for MarketingService + Alembic migration"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(#760): unit tests + Alembic migration for MarketingService" --body "Closes #760"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — MockState + make_mock_session 模式范本
- 同类参考实现：[`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — domain handler 定义规范
- 父 issue / 关联：#457（父 issue），#759（依赖 — MarketingService ORM 模型定义）
- Alembic 规范：[`alembic/env.py`](../../../alembic/env.py) — 确认模型 import 规范
- 已知坑参考：CLAUDE.md §Alembic Migrations

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |

---

**Changes made:**

- **Line 9** (`./75x-add-orm-models-for-marketing-entity.md`): No file matching `075x-*.md` exists in `40-campaigns/`, and no other marketing ORM doc path is derivable from context. Replaced with `TBD - 待验证：关联 issue #759 的 ORM 模型定义文档路径`.
- **Line 10** (`../30-sales/README.md`): No `30-sales/` directory exists under `docs/dev-plan/` (only `00-foundations`, `10-customers`, `20-sales`, `30-tickets`, etc.). Replaced with `TBD - 待验证：依赖板块 README路径`.
