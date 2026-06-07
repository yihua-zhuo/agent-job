# churn_batch_job · 实现每日流失预测批处理

| 元数据 | 值 |
|---|---|
| Issue | #817 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | TBD - 待验证：#816 dev-plan board 路径（issue body 声明 Depends on #816） |
| 启用后赋能 | TBD - 待补充：依赖此 batch job 产出的下游板块（churn dashboard / alert 路由） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The CRM needs an automated mechanism to run churn prediction for all active customers on a daily basis and to fire alerts when a customer's risk score crosses the high-churn threshold. Without a batch job, the `ChurnPredictionService.predict()` calls from #816 would have to be invoked manually per tenant — this is operationally untenable as the customer base grows. This issue is a subtask of the broader churn-analytics epic #575.

### 1.2 做完后

- **用户视角**：Customers whose churn score crosses the 70-point threshold (previously below 70, now at or above 70) receive an automated alert — no operator action required. The batch runs once per day per tenant.
- **开发者视角**：A new `src/jobs/` package exists. Operators can invoke the batch via `python -m jobs.churn_batch_job --tenant-id N` (e.g. from cron or a Kubernetes CronJob). Two reusable async functions — `check_and_alert_threshold` and `run_daily_churn_predictions` — are available for embedding in other orchestrators or test fixtures.

### 1.3 不做什么（剔除）

- [ ] Churn prediction model implementation (delivered by #816; this board only consumes `ChurnPredictionService.predict`)
- [ ] Alert delivery channel configuration (email, Slack, webhook — assumed already wired by `send_churn_alert`)
- [ ] Scheduling infrastructure (cron, k8s CronJob, Airflow — handled by ops, not by this code)
- [ ] A generic job-runner framework — this is a single-purpose module under `src/jobs/`
- [ ] Multi-tenant parallel execution — `--tenant-id` processes one tenant at a time; concurrency is the scheduler's job

### 1.4 关键 KPI

- `ruff check src/jobs/churn_batch_job.py` → 0 errors
- `python -m jobs.churn_batch_job --help` → exit 0, output contains `--tenant-id`
- `PYTHONPATH=src pytest tests/unit/test_churn_batch_job.py -v` → ≥ 4 passed
- `run_daily_churn_predictions` catches per-customer exceptions and continues — one bad customer does not abort the batch
- `check_and_alert_threshold` returns the correct count: customers with `previous_score < 70 <= new_score`

---

## 2. 当前现状（起点）

### 2.1 现有实现

N/A — 新建模块。The `src/jobs/` package does not yet exist in the repository (no reference to it in `CLAUDE.md` §Project Structure). This is a greenfield module.

### 2.2 涉及文件清单

- 要建：
  - `src/jobs/__init__.py` — empty package marker, makes `python -m jobs.churn_batch_job` resolvable
  - `src/jobs/churn_batch_job.py` — the batch job: `check_and_alert_threshold`, `run_daily_churn_predictions`, `main()` CLI
  - `tests/unit/test_churn_batch_job.py` — unit tests for the three entry points
- 依赖已有模块（不修改，仅引用 — 路径 TBD 验证）：
  - TBD - 待验证：`db/connection.py` 中 `get_db()` 的 async generator 实现（CLAUDE.md 确认存在，但精确签名待查）
  - TBD - 待验证：`ChurnPredictionService.predict(customer_id, tenant_id)` 的服务模块路径（来自 #816）
  - TBD - 待验证：`send_churn_alert(...)` 的函数路径与签名（来自 #816 或关联 alert 板块）
  - TBD - 待验证：`ChurnPrediction` ORM model 的文件路径与 `score` 字段名（来自 #816）

### 2.3 缺什么

- [ ] No `src/jobs/` package — the directory does not exist
- [ ] No CLI entry point for running churn predictions on demand
- [ ] No threshold-crossing detection logic — alerts would have to be fired manually from query results
- [ ] No batch orchestration that iterates active customers and isolates per-customer failures
- [ ] No unit-test pattern for jobs that use the `get_db()` async generator — need to decide between mocking `get_db()` or testing the inner async functions directly

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/jobs/__init__.py` | Package marker so `python -m jobs.churn_batch_job` resolves |
| `src/jobs/churn_batch_job.py` | Batch job: `check_and_alert_threshold`, `run_daily_churn_predictions`, `main()` CLI with `--tenant-id` |
| `tests/unit/test_churn_batch_job.py` | Unit tests covering threshold logic, per-customer exception isolation, CLI argument parsing |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| （无） | This board does not modify any existing file under `src/`, `tests/`, or `alembic/` |

### 3.3 新增能力

- **Async function**：`check_and_alert_threshold(session: AsyncSession, tenant_id: int) -> int` — returns the number of alerts fired
- **Async function**：`run_daily_churn_predictions(session: AsyncSession, tenant_id: int) -> dict` — returns a summary dict (keys: `processed`, `errors`, `alerts`); inserts new `ChurnPrediction` rows; commits
- **CLI entry**：`python -m jobs.churn_batch_job --tenant-id <N>` — prints `Processed N customers, M errors, K alerts raised` to stdout

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 `async for session in get_db():` 不选 `async with get_db() as session:`**：The issue body explicitly says "uses `get_db()` async generator". The async-generator pattern (`async for`) is the canonical SQLAlchemy 2.x async pattern for scripts; the `async with` shortcut is forbidden in routers per `CLAUDE.md` §Rules-Don't, but is also not the contract requested by this issue. Stick with `async for` and `break` after the first yield.
- **选 per-customer `try/except` 不选 fail-fast**：One misbehaving customer's `predict()` call must not abort 10 000 other customers. Catch `Exception` (or a narrower `AppException` + `SQLAlchemyError`), log with tenant + customer context, increment an error counter, continue.
- **选 threshold formula `previous_score < 70 <= score` 不选 `score >= 70`**：A customer who is already at 80 does not re-alert every day. The crossing-only semantic matches the issue body's wording and avoids alert fatigue.

### 4.2 版本约束

No new dependencies introduced. The module uses only stdlib (`argparse`, `asyncio`, `logging`) and pre-existing project modules (`sqlalchemy`, `ChurnPredictionService`, `send_churn_alert`).

### 4.3 兼容性约束

- Multi-tenant：every query inside `run_daily_churn_predictions` and `check_and_alert_threshold` must filter by `tenant_id`（见 `CLAUDE.md` §Multi-Tenancy）
- Service 返回 ORM 对象：the batch job must use the `ChurnPrediction` ORM model directly (insert via `session.add(...)`), NOT a dict
- Service 错误抛 `AppException` 子类：`run_daily_churn_predictions` catches exceptions per-customer and does NOT re-raise; this is a batch-script exception to the normal "raise in service" rule, explicitly called out in the issue body
- CLI scripts must be run with `PYTHONPATH=src`（见 `CLAUDE.md` §Gotchas）
- `get_db()` is an async generator — must consume with `async for`, not `await get_db()`

### 4.4 已知坑

1. **`get_db()` as async generator is easy to misuse** → 规避：use `async for session in get_db(): ... break` pattern; never `session = await get_db()` and never `async with get_db() as session:` (the latter is the router-forbidden pattern and may also break the generator's cleanup context).
2. **PYTHONPATH must be set for `python -m jobs.churn_batch_job` to resolve** → 规避：document `PYTHONPATH=src python -m jobs.churn_batch_job --tenant-id 1` in §8 and in the `--help` epilog.
3. **Per-customer `except Exception` is broad** → 规避：catch `(AppException, SQLAlchemyError)` explicitly; let `KeyboardInterrupt` / `SystemExit` propagate so Ctrl-C still aborts the batch.
4. **`previous_score` lookup must be the *immediately* preceding prediction, not just any prior row** → 规避：query `SELECT score FROM churn_predictions WHERE customer_id = :cid AND tenant_id = :tid ORDER BY predicted_at DESC LIMIT 1` excluding the row just inserted (or query *before* insert).
5. **No new ORM model or migration in this board** → 规避：`ChurnPrediction` table and `ChurnPredictionService` are owned by #816; this board only writes rows. If #816's schema is missing a `predicted_at` column, this board fails — verify #816 is merged first.

---

## 5. 实现步骤（按顺序）

### Step 1: Create the `src/jobs/` package skeleton

Create the directory and an empty `__init__.py` so `python -m jobs.churn_batch_job` resolves.

操作：
- a) `mkdir -p src/jobs`
- b) Write an empty file at `src/jobs/__init__.py`
- c) Verify: `python -c "import jobs; print(jobs.__file__)"` exits 0 and prints a path under `src/jobs/`

**完成判定**：`src/jobs/__init__.py` exists; `PYTHONPATH=src python -c "import jobs"` exits 0

### Step 2: Implement `check_and_alert_threshold`

Add the threshold-detection function. It queries the two most recent `ChurnPrediction` rows per customer (the just-inserted one and the prior one), compares scores, and fires `send_churn_alert` on crossing.

操作：
- a) In `src/jobs/churn_batch_job.py`, add imports: `from sqlalchemy.ext.asyncio import AsyncSession`, plus `TBD - 待验证：ChurnPrediction model import path` and `TBD - 待验证：send_churn_alert import path`
- b) Define `THRESHOLD = 70` as a module-level constant
- c) Add the function:

```python
async def check_and_alert_threshold(
    session: AsyncSession, tenant_id: int
) -> int:
    # TBD - 待验证：ChurnPrediction 表的实际列名 (score / predicted_at / customer_id)
    stmt = (
        select(ChurnPrediction)
        .where(ChurnPrediction.tenant_id == tenant_id)
        .order_by(ChurnPrediction.customer_id, ChurnPrediction.predicted_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    alerts = 0
    latest_by_customer: dict[int, list[ChurnPrediction]] = {}
    for row in rows:
        latest_by_customer.setdefault(row.customer_id, []).append(row)
    for _cid, history in latest_by_customer.items():
        if len(history) < 2:
            continue
        new_score, prev_score = history[0].score, history[1].score
        if prev_score < THRESHOLD <= new_score:
            await send_churn_alert(session, tenant_id=tenant_id, customer_id=_cid, score=new_score)
            alerts += 1
    return alerts
```

**完成判定**：`ruff check src/jobs/churn_batch_job.py` → 0 errors; function importable via `from jobs.churn_batch_job import check_and_alert_threshold`

### Step 3: Implement `run_daily_churn_predictions`

Add the batch loop. Select active customers for the tenant, call `ChurnPredictionService.predict` per customer, insert the resulting `ChurnPrediction` row, commit, then call `check_and_alert_threshold`.

操作：
- a) In the same file, add `TBD - 待验证：ChurnPredictionService import path` and `TBD - 待验证：active-customer 筛选的 ORM 路径（Customer.is_active 或类似）`
- b) Add the function:

```python
async def run_daily_churn_predictions(
    session: AsyncSession, tenant_id: int
) -> dict:
    customers_stmt = select(Customer.id).where(
        Customer.tenant_id == tenant_id, Customer.is_active.is_(True)
    )
    customer_ids = (await session.execute(customers_stmt)).scalars().all()
    svc = ChurnPredictionService(session)
    processed = errors = 0
    for cid in customer_ids:
        try:
            await svc.predict(customer_id=cid, tenant_id=tenant_id)
            processed += 1
        except Exception as exc:  # noqa: BLE001 — see §4.4 pitfall 3
            errors += 1
            logger.exception("churn predict failed tenant=%s customer=%s", tenant_id, cid)
    await session.commit()
    alerts = await check_and_alert_threshold(session, tenant_id)
    return {"processed": processed, "errors": errors, "alerts": alerts}
```

**完成判定**：`ruff check src/jobs/churn_batch_job.py` → 0 errors; function importable

### Step 4: Implement `main()` CLI with argparse

Add the CLI entry point. Use `argparse` for `--tenant-id`, `asyncio.run` to drive the async session loop, and `async for session in get_db():` per the issue contract.

操作：
- a) Add imports: `import argparse`, `import asyncio`, `import logging`, plus `TBD - 待验证：get_db import path (likely from db.connection)`
- b) Add at module bottom:

```python
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run daily churn predictions and threshold alerts for one tenant."
    )
    parser.add_argument("--tenant-id", type=int, required=True)
    args = parser.parse_args()

    async def _run() -> dict:
        async for session in get_db():
            return await run_daily_churn_predictions(session, args.tenant_id)

    result = asyncio.run(_run())
    print(
        f"Processed {result['processed']} customers, "
        f"{result['errors']} errors, {result['alerts']} alerts raised"
    )

if __name__ == "__main__":
    main()
```

**完成判定**：`PYTHONPATH=src python -m jobs.churn_batch_job --help` exits 0 and lists `--tenant-id` in output

### Step 5: Write unit tests

Create `tests/unit/test_churn_batch_job.py`. Test the two pure async functions with a mocked `AsyncSession` (following the `tests/unit/conftest.py` handler pattern) and test `main()` with `argparse` and `asyncio.run` mocked.

操作：
- a) Build a `mock_db_session` fixture that handles `SELECT customer.id`, `INSERT/UPDATE churn_predictions`, and the threshold-query pattern — reuse `make_mock_session` + a custom handler from `tests/unit/conftest.py`
- b) Test cases (≥ 4):
  - `test_check_and_alert_threshold_fires_on_crossing` — previous=60, new=70 → alert + return 1
  - `test_check_and_alert_threshold_skips_already_high` — previous=80, new=85 → no alert + return 0
  - `test_run_daily_churn_predictions_continues_on_error` — one customer's `predict()` raises; loop continues; summary `errors=1`
  - `test_main_parses_tenant_id` — monkeypatch `asyncio.run` and `get_db`; assert `run_daily_churn_predictions` called with `tenant_id=42`
- c) Run `PYTHONPATH=src pytest tests/unit/test_churn_batch_job.py -v` → all passed

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_churn_batch_job.py -v` → 4+ passed

### Step 6: Run full acceptance pipeline

Re-run every command from §6 to confirm the board's exit criteria.

操作：
- a) `ruff check src/jobs/churn_batch_job.py`
- b) `PYTHONPATH=src python -m jobs.churn_batch_job --help`
- c) `PYTHONPATH=src pytest tests/unit/test_churn_batch_job.py -v`

**完成判定**：all three commands exit 0 with the expected output listed in §6

---

## 6. 验收

- [ ] `ruff check src/jobs/churn_batch_job.py` → 0 errors
- [ ] `PYTHONPATH=src python -m jobs.churn_batch_job --help` → exit 0, output contains `usage:`, `--tenant-id`, and `TENANT_ID` (argparse's required-flag marker)
- [ ] `PYTHONPATH=src pytest tests/unit/test_churn_batch_job.py -v` → `4 passed` (or more)
- [ ] `ruff check src/jobs/` → 0 errors (covers both `__init__.py` and the job module)
- [ ] `PYTHONPATH=src python -c "from jobs.churn_batch_job import check_and_alert_threshold, run_daily_churn_predictions; print('ok')"` → prints `ok`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `ChurnPredictionService.predict` not yet implemented (depends on #816) | 中 | 高 — board cannot run end-to-end | Block this board on #816 merge; if #816 is delayed, stub `predict` in a local fixture and merge tests-only |
| `send_churn_alert` signature unknown at implementation time | 中 | 中 — wrong call site will fail at runtime | Define a thin wrapper in this module (`async def _alert(...): return await send_churn_alert(...)`) and patch the wrapper in tests; adjust the call site once #816's signature is confirmed |
| Per-customer `except Exception` swallows real bugs (e.g. DB connection drop) | 低 | 中 — silent partial failure | Log at `logger.exception` level with tenant + customer ID; emit a metric counter `churn_batch.errors{tenant_id=N}` for ops to alert on; CI test asserts the exception is logged |
| `get_db()` generator consumed only once — multi-tenant loop in CLI is single-tenant by design | 低 | 低 | Out of scope; if multi-tenant batch is needed, wrap the call site in another loop upstream (cron / k8s CronJob) — this module stays single-tenant |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/jobs/__init__.py src/jobs/churn_batch_job.py tests/unit/test_churn_batch_job.py
git commit -m "feat(jobs): add churn_batch_job with threshold detection and CLI (closes #817)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(jobs): churn_batch_job with threshold detection and CLI" --body "Closes #817"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行（日期 + 「创建」/「实现」 + 实施者）
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
