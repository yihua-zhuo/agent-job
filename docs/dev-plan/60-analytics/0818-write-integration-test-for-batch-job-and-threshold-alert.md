# 流失预测批处理集成测试 · 为批处理与阈值告警编写集成测试

| 元数据 | 值 |
|---|---|
| Issue | #818 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | TBD - 待验证：#817 的 dev-plan 板块实际文件路径（issue body 显式声明 Depends on #817） |
| 启用后赋能 | #575（父 epic — Churn Management） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

This issue is a subtask of the Churn Management epic (#575). The implementation of the daily churn prediction batch job (`run_daily_churn_predictions`) and the threshold alert path is being delivered in the dependent board #817. Without an integration test that hits a real PostgreSQL session, regressions in the batch logic (wrong customer count, swallowed errors, missing ChurnPrediction rows) and in the threshold path (alerts never firing, or firing for the wrong customers) can ship undetected — the unit-level coverage in #817's board can verify call counts but cannot prove rows are actually persisted or that the threshold comparison really crosses. This board closes that gap with a real-DB integration test that exercises both the happy path and the threshold-alert path.

### 1.2 做完后

- **User perspective**: No user-visible change. This is a pure testing/infrastructure addition — it does not modify the API surface, the batch schedule, the alert delivery mechanism, or any model schema.
- **Developer perspective**: A new integration test file `tests/integration/test_churn_batch_job_integration.py` is available. It can be executed against the real PostgreSQL test DB (via the existing `db_schema`, `tenant_id`, and `async_session` fixtures) to verify that:
  - `run_daily_churn_predictions(session, tenant_id)` processes every active customer in the tenant and returns `{"processed": N, "errors": 0, "alerts": M}` with N matching the count of active customers and N `ChurnPrediction` rows persisted.
  - The threshold alert path is invoked when a pre-existing prediction already sits at score 55.0, producing `result["alerts"] >= 1` in the batch result dict.

### 1.3 不做什么（剔除）

- [ ] Implementing `run_daily_churn_predictions` or the threshold alert logic itself — owned by #817.
- [ ] Adding unit tests for the batch job — owned by #817's board (or its sibling unit-test board, if one exists).
- [ ] Modifying `Customer` / `ChurnPrediction` ORM models, Alembic migrations, or the batch scheduler.
- [ ] Configuring real downstream alert delivery (email, Slack, webhook) — the threshold path is a stub that only logs; this test asserts the code path ran (`alerts >= 1`) but does not validate delivery.
- [ ] Performance / load / concurrency testing of the batch.

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py -v` → 2 passed (both `test_happy_path_processes_all_active_customers` and `test_threshold_alert_fires_when_existing_score_at_threshold` green).
- Happy-path coverage: `result["processed"] == 2` AND `result["errors"] == 0` AND `SELECT count(*) FROM churn_predictions WHERE tenant_id = :t` returns 2.
- Threshold coverage: `result["alerts"] >= 1` when a pre-existing `ChurnPrediction` row at score 55.0 is present.
- `ruff check tests/integration/test_churn_batch_job_integration.py` → 0 errors.

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口（batch job，源自 #817）：TBD - 待验证：`src/services/<疑似 churn_service 或 batch 子目录>` 中的 `run_daily_churn_predictions` — 现有签名 + 返回 dict 的位置。

从 issue body 推导出的预期契约（具体行号未验证）：

```python
# 来自 #817 的实现；具体文件/行号待 #817 合并后从其板块中确认
async def run_daily_churn_predictions(
    session: AsyncSession,
    tenant_id: int,
) -> dict[str, int]:
    ...
    return {"processed": <int>, "errors": <int>, "alerts": <int>}
```

ORM model（ChurnPrediction，源自 #817）：TBD - 待验证：`src/db/models/<疑似 churn 子目录>` 中的 `ChurnPrediction` — 现有 schema（`customer_id` / `score` / `tenant_id` / 其它字段，以及 `score` 的 SQL 类型是 Float 还是 Numeric）。

### 2.2 涉及文件清单

- 要改：
  - （无 — 本板块只新增一个测试文件，不修改任何 src 或 alembic 文件）
- 要建：
  - TBD - 待验证：待创建 — `tests/integration/test_churn_batch_job_integration.py` — batch job + threshold alert 的集成测试（2 个 test case，使用 `db_schema` / `tenant_id` / `async_session` fixture）

### 2.3 缺什么

- [ ] `tests/integration/test_churn_batch_job_integration.py` 整个文件不存在 — 没有任何针对 `run_daily_churn_predictions` 的真实 DB 端到端测试。
- [ ] Happy-path 端到端验证缺失：CI 中无法证明 batch 处理 N 个 active customer 后会写入 N 行 `ChurnPrediction`。
- [ ] Threshold-alert 端到端验证缺失：CI 中无法证明 score ≥ 阈值时 batch 结果 dict 里的 `alerts` 计数会 ≥ 1。
- [ ] 返回 dict 的 shape 契约测试缺失：`processed` / `errors` / `alerts` 三个 key 是否稳定存在、是否都为 int，没有断言保护。
- [ ] 跨 test 的数据隔离没有保护：若之后有人复用 fixture 写新测试，可能踩到本测试的残留数据（虽然 `db_schema` 已 TRUNCATE，但显式声明「本测试不依赖跨 test 状态」仍是好习惯）。

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| TBD - 待验证：待创建 — `tests/integration/test_churn_batch_job_integration.py` | 集成测试：覆盖 `run_daily_churn_predictions` 的 happy path 与 threshold alert path，使用现有 `db_schema` / `tenant_id` / `async_session` fixture |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| （无） | 本板块不修改任何已有文件 |

### 3.3 新增能力

- **Integration test class**：`TestChurnBatchJob`（在 `tests/integration/test_churn_batch_job_integration.py`），标记 `@pytest.mark.integration`：
  - `test_happy_path_processes_all_active_customers` — seed 2 个 active customer → 调 `run_daily_churn_predictions` → 断言 `result["processed"] == 2`、`result["errors"] == 0`、DB 中存在 2 行 `ChurnPrediction`（`WHERE tenant_id = :t`）。
  - `test_threshold_alert_fires_when_existing_score_at_threshold` — seed 1 个 customer + 1 行预存 `ChurnPrediction(score=55.0)` → 重跑 batch → 断言 `result["alerts"] >= 1`。

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **使用现有 fixtures（`db_schema` / `tenant_id` / `async_session`）而非新建**：理由 — `tests/integration/conftest.py` 已提供这些 fixture（见 CLAUDE.md §Integration Test Fixtures），它们保证 schema 在每个 test function 前被创建/清空、session 在同一 test 内被共享。新建重复 fixture 只会增加维护成本和潜在的 isolation bug。
- **集成测试而非更多 unit test**：理由 — issue 显式要求真实 DB 上的 `ChurnPrediction` 行持久化断言和 threshold 比较。Mock DB 只能验证调用次数，无法证明 row 真的被写入或 threshold 真的被越过。
- **threshold test 用 score = 55.0 作为预存值**：理由 — issue body 显式指定 55.0；不擅自改成其它值。55.0 与 #817 中具体阈值的相对位置由 #817 的实现决定；只要 batch 在该 score 下 `alerts >= 1`，就证明 threshold path 被触发。
- **threshold test 只断言 `alerts >= 1` 而非具体数字**：理由 — issue body 明确说「count being non-zero proves the threshold path ran」。不锁死具体 alert 数量可让 #817 调整阈值/规则时不需要改本测试。
- **不引入 `_seed_churn_customer` 等新 helper**：理由 — CLAUDE.md §Gotchas 5 的「cross-service seeds」模式（`tests/integration/conftest.py` 里的 `_seed_customer` / `_seed_user`）已覆盖 customer seed 需求；新增 churn 专用 helper 超出本板块范围。

### 4.2 版本约束

（无新依赖 — 本板块仅新增一个测试文件，imports 都来自仓库内已存在的 fixture / model / service / SQLAlchemy / pytest）

### 4.3 兼容性约束

- 多租户：所有 SQL 操作必须经过 `tenant_id` 过滤（见 CLAUDE.md §Multi-Tenancy）。`run_daily_churn_predictions` 本身已按 `tenant_id` 过滤；本测试在 seed customer / pre-existing prediction 时也必须带上 `tenant_id`，且 SELECT 断言的 `WHERE tenant_id = :t` 必须存在。
- 集成测试 schema 隔离：`db_schema` fixture 在每个 test function 前 `TRUNCATE` 所有表（见 CLAUDE.md §Gotchas 4）；不要假设跨 test 的数据持久化。
- 测试用 session：`async_session` fixture 在 test 内部共享；可用它同时驱动 service 调用和后续 SELECT 断言。
- 不在测试内 try/except 吞 AppException：service 抛 `NotFoundException` / `ValidationException` 等时直接让 pytest 标记失败（沿用 CLAUDE.md §Error Handling 约定）。
- 严格沿用 `tests/unit/conftest.py` 的 mock 模式**不可**用于本文件：集成测试必须跑真 DB。
- 不新增 alembic migration：本板块不引入新表/新列；任何 churn 相关 migration 由 #817 负责。

### 4.4 已知坑

1. **跨 service seed 顺序**：seed customer → seed ChurnPrediction 时必须保证 customer 已 commit（否则 FK 报错）。沿用 CLAUDE.md §Gotchas 5 的「cross-service seeds」模式：先 `_seed_customer` + `await async_session.commit()`，再 seed ChurnPrediction + 再次 `commit`。
2. **score 字段类型**：`ChurnPrediction.score` 在 #817 中是 `Float` 还是 `Numeric` 未验证。若类型是 `Numeric`，写入 55.0 时 ORM 可能要求 `decimal.Decimal` 而非 `float`；本测试在写入预存 row 时需用与 model 匹配的类型（`TBD - 待验证：ChurnPrediction.score 列的 SQL 类型`）。规避：写预存 row 时先按 `score` 的 Python 类型构造值；若失败再切换 `Decimal("55.0")`。
3. **threshold 的实际数值未公开**：#817 的 threshold 常量值（如 `THRESHOLD = 50.0`）未知。本测试在 #817 合并前可能因为 threshold 与 55.0 的相对位置变化而失败 — 这是正常的，#817 落地后再跑即可。
4. **session 共享 / flush 时机**：`async_session` fixture 在一个 test function 内是同一个 session。在调用 `run_daily_churn_predictions(session, tenant_id)` 之后做 SELECT 断言前，必须 `await async_session.commit()` 或 `await async_session.flush()`，否则未提交的行对后续查询不可见。规避：在 service 调用返回后立即 `await async_session.commit()`，再做 row-count 断言。
5. **多租户 WHERE 漏写**：CLAUDE.md §Multi-Tenancy 强调「every SQL query must filter by tenant_id」。本测试的 count 断言必须 `WHERE tenant_id = :tenant_id`，不能裸 `SELECT count(*)` —— 否则会跨租户污染（虽然单 test 内只有一个 tenant，但显式声明是 contract）。
6. **Alembic autogen 与本板块无关**：本板块不新增 migration；现有 churn 相关迁移（若 #817 引入）请在 #817 的板块里按 CLAUDE.md §Alembic Migrations 规则检查（注意 autogen 倾向把 JSONB 写成 JSON、TIMESTAMPTZ 写成 DateTime），不在本板块范围。

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 #817 的函数签名与 model schema

在写测试前，先确认 #817 已经（或将要）合并的接口与 model 字段。这一步是阅读性操作，不写代码。

操作：
- a) 打开 #817 的 dev-plan 板块，定位 `run_daily_churn_predictions` 的实现文件、路径与行号。
- b) 打开 `src/db/models/<churn 目录>`，定位 `ChurnPrediction` 的列定义（特别是 `score` 字段的 SQL 类型、`tenant_id` 列是否存在索引）。
- c) 确认 `tests/integration/conftest.py` 中的 `db_schema` / `tenant_id` / `async_session` fixture 名字未变（CLAUDE.md §Integration Test Fixtures 列出这三个名字是稳定的，但本步骤仍需以实际仓库代码为准）。
- d) 确认是否有可复用的 `_seed_customer` helper（CLAUDE.md §Gotchas 5 暗示有，但需以实际 conftest 为准）。

**完成判定**：本作者已记录 #817 的 `run_daily_churn_predictions` 完整签名（参数名 / 返回 dict 的 key 集合）以及 `ChurnPrediction` 各列的 Python 类型与 SQL 类型。

### Step 2: 在 `tests/integration/` 下创建空 test 文件框架

创建一个空的 test 文件框架，import 必要的 fixture 与 #817 的 service。

操作：
- a) 新建文件 TBD - 待验证：待创建 — `tests/integration/test_churn_batch_job_integration.py`。
- b) 文件顶部加入 `@pytest.mark.integration` marker 类（沿用 `tests/integration/` 目录其它文件的约定）。
- c) 写入 import 块：`pytest`、`AsyncSession`（类型注解用）、`sqlalchemy.func`、`sqlalchemy.select`、#817 的 `run_daily_churn_predictions` 与 `ChurnPrediction`（具体路径以 #817 落地后为准）、`_seed_customer` helper（若 conftest 暴露）。

示例代码：

```python
# tests/integration/test_churn_batch_job_integration.py
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# 注：以下 import 的具体路径待 #817 落地后从其板块中确认
# from services.<churn_path> import run_daily_churn_predictions
# from db.models.<churn_path> import ChurnPrediction
# from tests.integration.conftest import _seed_customer


@pytest.mark.integration
class TestChurnBatchJob:
    async def test_placeholder(
        self,
        db_schema,
        tenant_id,
        async_session: AsyncSession,
    ) -> None:
        # 占位 — 后续 Step 替换
        assert True
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py -v` → 1 passed（占位测试）。

### Step 3: 实现 test case 1 — happy path

在 `TestChurnBatchJob` 内加入第一个 test case。

操作：
- a) 替换 `test_placeholder` 为 `test_happy_path_processes_all_active_customers`。
- b) seed 2 个 active customer（沿用 CLAUDE.md §Gotchas 5 的 cross-service seed 模式；用 `_seed_customer` helper 或 inline 构造 `Customer`）。
- c) `await async_session.commit()`。
- d) 调用 `result = await run_daily_churn_predictions(async_session, tenant_id=tenant_id)`。
- e) 断言 `result["processed"] == 2`、`result["errors"] == 0`。
- f) `await async_session.commit()`（按 §4.4 坑 4 的规避）。
- g) 断言 DB 中 `ChurnPrediction` 行数 = 2：`select(func.count()).select_from(ChurnPrediction).where(ChurnPrediction.tenant_id == tenant_id)`。

示例代码：

```python
async def test_happy_path_processes_all_active_customers(
    self,
    db_schema,
    tenant_id,
    async_session: AsyncSession,
) -> None:
    await _seed_customer(async_session, tenant_id, name="Cust A", status="active")
    await _seed_customer(async_session, tenant_id, name="Cust B", status="active")
    await async_session.commit()

    result = await run_daily_churn_predictions(async_session, tenant_id=tenant_id)

    assert result["processed"] == 2
    assert result["errors"] == 0

    count_q = (
        select(func.count())
        .select_from(ChurnPrediction)
        .where(ChurnPrediction.tenant_id == tenant_id)
    )
    total = (await async_session.execute(count_q)).scalar_one()
    assert total == 2
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py::TestChurnBatchJob::test_happy_path_processes_all_active_customers -v` → 1 passed。

### Step 4: 实现 test case 2 — threshold alert path

加入第二个 test case。

操作：
- a) 加入 `test_threshold_alert_fires_when_existing_score_at_threshold`。
- b) seed 1 个 active customer，commit。
- c) seed 1 行预存的 `ChurnPrediction`（`score=55.0`、`tenant_id=tenant_id`、`customer_id=<刚 seed 的 customer id>`）；若 `score` 列类型是 `Numeric`，把 `55.0` 改成 `decimal.Decimal("55.0")`。
- d) `await async_session.commit()`。
- e) 调 `result = await run_daily_churn_predictions(async_session, tenant_id=tenant_id)`。
- f) 断言 `result["alerts"] >= 1`（不锁死具体数字，按 issue body 要求）。
- g) `await async_session.commit()`。

示例代码：

```python
async def test_threshold_alert_fires_when_existing_score_at_threshold(
    self,
    db_schema,
    tenant_id,
    async_session: AsyncSession,
) -> None:
    cust_id = await _seed_customer(
        async_session, tenant_id, name="Cust T", status="active"
    )
    await async_session.commit()

    pre = ChurnPrediction(
        customer_id=cust_id,
        tenant_id=tenant_id,
        score=55.0,  # 若 score 列类型为 Numeric, 改为 decimal.Decimal("55.0")
    )
    async_session.add(pre)
    await async_session.commit()

    result = await run_daily_churn_predictions(async_session, tenant_id=tenant_id)

    assert result["alerts"] >= 1
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py::TestChurnBatchJob::test_threshold_alert_fires_when_existing_score_at_threshold -v` → 1 passed。

### Step 5: 全量验证 + lint

跑完整文件 + ruff，确认两个 test case 都过且 ruff 干净。

操作：
- a) `PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py -v`。
- b) `ruff check tests/integration/test_churn_batch_job_integration.py`。
- c) 若有 lint 报错，按 ruff 提示修（典型：import 排序、未使用 import、行长 > 99）。
- d) （可选）连续跑两次 `pytest tests/integration/test_churn_batch_job_integration.py -v`，验证 test 隔离（不应有顺序依赖）。

**完成判定**：步骤 a) → 2 passed（两个 test case 名称与 §1.4 KPI 完全一致）；步骤 b) → exit 0；步骤 d) → 两次均 2 passed。

### Step 6: 在本板块 §Changelog 登记

操作：
- a) 编辑本板块文档的 Changelog 表，新增一行「2026-06-07 · 创建」并把「实施者」填为实际作者。

**完成判定**：Changelog 表新增的行可被 `git diff` 看到；与本板块 §8 完成后必做的 commit 一起提交。

---

## 6. 验收

- [ ] `ruff check tests/integration/test_churn_batch_job_integration.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py -v` → 2 passed（`TestChurnBatchJob::test_happy_path_processes_all_active_customers` 和 `TestChurnBatchJob::test_threshold_alert_fires_when_existing_score_at_threshold` 都过）
- [ ] Happy-path 断言覆盖：`result["processed"] == 2` AND `result["errors"] == 0` AND `SELECT count(*) FROM churn_predictions WHERE tenant_id = :t` 返回 2
- [ ] Threshold-alert 断言覆盖：`result["alerts"] >= 1`（预存 `ChurnPrediction.score == 55.0`）
- [ ] 测试隔离：连续跑两次 `PYTHONPATH=src pytest tests/integration/test_churn_batch_job_integration.py -v` → 每次 2 passed（不依赖 test 间数据残留）
- [ ] 多租户 contract：所有 SELECT 断言显式 `WHERE tenant_id = :tenant_id`（无裸 `SELECT count(*)`）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #817 尚未合并时本测试无法运行（`run_daily_churn_predictions` / `ChurnPrediction` 不存在） | 高 | 高 | 把本板块的 status 保持为 📋 待开始；CI 不要求 #818 的测试在 #817 合并前必过。回退：本板块合并可晚于 #817，本板块的 PR 不阻塞 #575 整体的 release。 |
| `ChurnPrediction.score` 实际类型是 `Numeric` 而非 `Float`，导致写入 55.0 失败 | 中 | 中 | 把 score 改成 `decimal.Decimal("55.0")`；若仍失败，在测试上加 `pytest.mark.xfail(reason="score type mismatch, see #818")` 临时跳过，并在 issue 评论里 follow up。 |
| #817 的实际 threshold 常量与 55.0 的关系在 #817 调整后变化（例如阈值从 50 提到 60） | 中 | 低 | 按 issue body 只断言 `alerts >= 1`，不锁死 threshold 数值；本测试对 #817 的 threshold 微调天然健壮。 |
| `async_session` 在 service 调用后未 flush/commit，导致 SELECT 断言看到旧数据 | 中 | 中 | 在 `run_daily_churn_predictions` 返回后立即 `await async_session.commit()` 再做 count 查询（已在 §4.4 坑 4 标注）。 |
| `_seed_customer` helper 签名与本测试假设不符（缺 `name`/`status` 关键字） | 低 | 低 | 按实际 `_seed_customer` 的签名调用；若必需字段不同，参考 `tests/integration/conftest.py` 的现有用法调整。 |
| 测试在 CI 上 flake（threshold 边界条件非确定性） | 低 | 中 | 若 flake 出现，定位是 #817 的 batch 逻辑本身非确定性（应回 #817 修），还是 test 自身问题（应在本板块加更明确的 seed 步骤）。 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/integration/test_churn_batch_job_integration.py docs/dev-plan/60-analytics/0818-write-integration-test-for-batch-job-and-threshold-alert.md
git commit -m "test(churn): add integration test for batch job and threshold alert (#818)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test(churn): integration test for batch job + threshold alert" --body "Closes #818"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`tests/integration/test_<其它 *_integration.py>` — 现有 `db_schema` / `tenant_id` / `async_session` fixture 的使用样例与 `_seed_customer` helper 的实际签名。
- 父 issue / 关联：
  - #818（当前 issue）
  - #817（依赖 — churn batch job + threshold alert 的实现板块）
  - #575（父 epic — Churn Management）
- 第三方文档：无（本测试仅依赖仓库内已有的 pytest + SQLAlchemy async 文档，已在 CLAUDE.md §Resources 中给出）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-06-07 | 创建 | TBD |
