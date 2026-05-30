# 审计 ActivityService 中的 tenant_id 过滤

| 元数据 | 值 |
|---|---|
| Issue | #488 |
| 分类 | [10-cross-cutting](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | TBD - 待验证：0487 文档所在路径（`docs/dev-plan/0487-audit-app-exceptions-hierarchy.md` 不存在） |
| 启用后赋能 | 无 — 本板块修复内部安全漏洞，无下游依赖 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

多租户 CRM 中，每个 SQL 查询和 Service 方法必须携带 `tenant_id` 过滤条件，漏写任何一处都会导致租户 A 读取到租户 B 的数据（跨租户数据泄露）。Issue #452 将安全审计设为季度必做项，本板块是其在 `ActivityService` + `activities` 路由层的落地。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层安全修复。
- **开发者视角**：`ActivityService` 所有公开方法和 `activities` 路由处理器均已确认包含 `tenant_id` 过滤，代码审查报告可作为合规模档。

### 1.3 不做什么（剔除）

- [ ] 不重写任何 Service 方法的业务逻辑，只补漏 `tenant_id` 过滤。
- [ ] 不修改 Service 返回类型或 Router 签名（API 兼容性约束）。
- [ ] 不新增测试用例；仅验证现有测试断言覆盖了多租户场景。

### 1.4 关键 KPI

- [`ruff check src/services/activity_service.py src/api/routers/activities.py` → 0 errors](#验收)
- [`PYTHONPATH=src pytest tests/unit/ -k activity -v` → 全部 passed](#验收)
- 所有 8 个方法（见 §2.3）均含 `tenant_id` 过滤，无遗漏

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：`src/services/activity_service.py`

**TBD — 待验证**：`src/services/activity_service.py` L?-L? — 需确认以下 8 个方法是否存在、签名为何、是否已含 tenant_id 过滤：
`create_activity`、`_fetch`、`delete_activity`、`list_activities`、`get_customer_activities`、`get_opportunity_activities`、`search_activities`、`get_activity_summary`

Router：`src/api/routers/activities.py`

**TBD — 待验证**：`src/api/routers/activities.py` L?-L? — 需确认每个路由处理器是否通过 `ctx.tenant_id` 传参给 Service 层。

### 2.2 涉及文件清单

- 要改：
  - `src/services/activity_service.py` — 补漏缺失的 `tenant_id` WHERE 条件
  - `src/api/routers/activities.py` — 确认 Service 方法调用均传递 `tenant_id`
- 要建：
  - N/A — 本次不发新文件

### 2.3 缺什么

- [ ] `create_activity`：需确认 `tenant_id` 被写入新建行的对应字段（非 NULL）
- [ ] `_fetch`（内部查询方法）：需确认 WHERE 子句含 `tenant_id = :tenant_id`
- [ ] `delete_activity`：需确认 WHERE 含 `tenant_id`
- [ ] `list_activities`：需确认首条 WHERE 即 `tenant_id` 过滤
- [ ] `get_customer_activities`：需确认 JOIN/WHERE 含 `tenant_id`
- [ ] `get_opportunity_activities`：需确认 JOIN/WHERE 含 `tenant_id`
- [ ] `search_activities`：需确认全文/模糊查询路径含 `tenant_id`
- [ ] `get_activity_summary`：需确认聚合查询含 `tenant_id` GROUP BY

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|-------|
| N/A | 无新建文件 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/activity_service.py`](../../../src/services/activity_service.py) | 8 个方法中缺失 tenant_id 过滤的补上；不改签名 |
| [`src/api/routers/activities.py`](../../../src/api/routers/activities.py) | 确认每个 handler 传 `tenant_id=ctx.tenant_id` |

### 3.3 新增能力

- **Security fix**：`ActivityService` 全部 SQL 查询含 `WHERE tenant_id = :tenant_id`，消除跨租户泄露路径

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **直接补漏而非重构**：仅在缺失处插入 `tenant_id = :tenant_id` 到 WHERE/VALUES，避免改动范围蔓延至正常代码路径。

### 4.2 版本约束

N/A — 无新依赖引入。

### 4.3 兼容性约束

- Service `__init__` 仍接收 `session: AsyncSession`（无默认值），签名不变。
- Service 方法返回类型不变；`.to_dict()` 仍由 Router 调用。
- `AppException` 子类（`NotFoundException` 等）抛出行为不变。
- API endpoint 路由路径和 HTTP 方法不变。

### 4.4 已知坑

1. **SQLAlchemy `Mapped` 参数顺序写反导致列类型错误** → 规避：确认 `mapped_column` 参数顺序为 `Mapped[int] = mapped_column(Integer, ...)`，不要写成 `mapped_column(Mapped[int], ...)`。
2. **Router 用 `async with get_db() as session:` 导致连接泄露** → 规避：所有路由改用 `session: AsyncSession = Depends(get_db)`，不使用上下文管理器。

---

## 5. 实现步骤（按顺序）

### Step 1: 读取并逐方法审查 activity_service.py

打开 `src/services/activity_service.py` 和 `src/api/routers/activities.py`，对每个方法逐一确认过滤情况：

操作：
- a) 用 grep 搜索文件中所有含 `tenant_id` 的行，记下在哪些方法内。
- b) 对照 §2.3 清单，标注缺失的方法名称。
- c) 若 `_fetch` 是共享基方法，确认其 WHERE 已含 `tenant_id`，则所有调用方均安全。

**完成判定**：已输出缺失清单（0-8 项），无遗漏。

---

### Step 2: 补漏缺失的 tenant_id 过滤（按需执行）

若 Step 1 发现缺失，对每个方法执行以下修改（示例展示通用的补漏模式；实际行号以 Step 1 结果为准）：

操作：
- a) **create_activity**：在 INSERT VALUES 中补 `tenant_id=tenant_id`。
- b) **_fetch / list_activities**：在 SELECT WHERE 首行加 `activity.tenant_id = :tenant_id`。
- c) **delete_activity**：在 DELETE WHERE 加 `tenant_id = :tenant_id`。
- d) **get_customer_activities / get_opportunity_activities**：在 JOIN 后 WHERE 加 `activity.tenant_id = :tenant_id`。
- e) **search_activities**：全文/模糊查询的 WHERE 加 `tenant_id = :tenant_id`。
- f) **get_activity_summary**：聚合查询的 WHERE 加 `tenant_id = :tenant_id`。

示例代码（通用模式）：

```python
# src/services/activity_service.py
# BEFORE（缺失 tenant_id）
result = await session.execute(
    select(Activity).where(Activity.id == activity_id)
)

# AFTER（已补漏）
result = await session.execute(
    select(Activity).where(
        Activity.id == activity_id,
        Activity.tenant_id == tenant_id  # 已补
    )
)
```

**完成判定**：`ruff check src/services/activity_service.py` exit 0；所有 8 个方法已含 `tenant_id` 过滤。

---

### Step 3: 确认 router 层传参完整

检查 `src/api/routers/activities.py`，每个 handler 调用 Service 方法时确认传了 `tenant_id=ctx.tenant_id`：

操作：
- a) grep `ctx.tenant_id`，确认每条 Service 调用线均有此参数。
- b) 若缺失，补上 `tenant_id=ctx.tenant_id` 参数。

**完成判定**：`ruff check src/api/routers/activities.py` exit 0。

---

### Step 4: 运行测试验证无回归

操作：
- a) `PYTHONPATH=src pytest tests/unit/ -k activity -v` — 全部 passed。
- b) 若有 integration 测试：`PYTHONPATH=src pytest tests/integration/ -k activity -v` — 全部 passed。

**完成判定**：测试输出无 FAILED，全 passed。

---

## 6. 验收

- [ ] `ruff check src/services/activity_service.py src/api/routers/activities.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/ -k activity -v` → 全部 passed
- [ ] `PYTHONPATH=src pytest tests/integration/ -k activity -v` → 全部 passed（如有 integration 测试）
- [ ] 人工复核：8 个方法（§2.3 清单）均在对应 SQL WHERE/INSERT 中含 `tenant_id = :tenant_id`
- [ ] `ruff check src/` → 0 errors（全局无新增 lint 问题）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 误改正常业务逻辑（如 WHERE 条件写错比较符） | 低 | 中 | `git diff` 回退，改动文件不超过 2 个，逐方法验证 |
| Service 方法签名被意外改写（添加了 default 参数等） | 低 | 高 | 检查 `__init__` 和各方法签名不变，ruff 类型报错会提前拦截 |
| router 漏传 tenant_id 但测试未覆盖到（测试覆盖盲区） | 中 | 高 | 手动读 router 代码确认每条调用线；后续 issue #452 扩测覆盖 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/activity_service.py src/api/routers/activities.py
git commit -m "fix(security): add missing tenant_id filters in ActivityService

Closes #488"

git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "fix(security): audit and fix tenant_id filtering in ActivityService" --body "## Summary
- Audited all 8 methods in ActivityService for tenant_id coverage
- Added missing tenant_id WHERE conditions
- Confirmed router handlers pass tenant_id to service layer

## Test plan
- pytest tests/unit/ -k activity -v
- ruff check src/services/activity_service.py src/api/routers/activities.py

Closes #488
Subtask of #452"
```

---

## 9. 参考

- 同类参考实现：TBD — 待验证：`src/services/customer_service.py` L?-L? — 已有正确 tenant_id 过滤的 Service 模板
- 第三方文档：[SQLAlchemy 2.0 async documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- 父 issue / 关联：#452（季度安全审计父任务）、TBD - 待验证：#487 依赖的前置审计文档路径（`0487-audit-app-exceptions-hierarchy.md` 不存在）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
