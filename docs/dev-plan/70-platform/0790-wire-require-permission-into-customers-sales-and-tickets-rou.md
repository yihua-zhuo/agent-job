# RBAC wiring · Wire require_permission into 3 routers

| 元数据 | 值 |
|---|---|
| Issue | #790 |
| 分类 | [70-platform](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | require_permission implementation (TBD - 待验证：父 issue #643 对应 dev-plan 板块文件路径) — 父 issue #643 |
| 启用后赋能 | [rbac integration tests](0793-create-test-permission-denied-py-and-run-full-verification.md) — 依赖本板块完成 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

The RBAC decorator `require_permission` already exists in `src/dependencies/rbac.py` (per the parent issue #643), but three major router files — customers, sales, and tickets — have not yet been wired to enforce per-endpoint permissions. Currently these endpoints rely solely on `require_auth`, which validates the session but does not check whether the caller has the specific resource-action permission for the operation being attempted. This means any authenticated user in a tenant can hit any endpoint regardless of role, violating the principle of least privilege and leaving the RBAC system toothless.

### 1.2 做完后

- **用户视角**：No direct user-visible change for legitimate users with correct permissions. Unauthorized users will receive a 403 Forbidden response when hitting endpoints they lack permission for, instead of silently succeeding.
- **Developer视角**：Every endpoint in `customers.py`, `sales.py`, and `tickets.py` enforces a `resource:action` permission check via `Depends(require_permission(...))`. The permission map is standardized per the dev-plan §3.3. Downstream code can rely on RBAC being enforced at the router boundary and does not need to re-check permissions in service code.

### 1.3 不做什么（剔除）

- [ ] Implementing `require_permission` itself (handled by #643)
- [ ] Adding new permission strings beyond those specified in the dev-plan §3.3
- [ ] Refactoring existing role-based checks on `/leads` and `/leads/recycle` — keep them, just add `customer:read` on top
- [ ] Touching service-layer permission logic — enforcement is at the router level only
- [ ] Adding unit/integration tests for the new permission checks (out of scope for this subtask; covered by a sibling board)

### 1.4 关键 KPI

- `ruff check src/api/routers/customers.py src/api/routers/sales.py src/api/routers/tickets.py` → 0 errors
- All 37 endpoints (13 + 12 + 12) have a `Depends(require_permission("..."))` parameter
- `PYTHONPATH=src pytest tests/unit/ -v` → all pre-existing tests still pass
- Import of `require_permission` from `src/dependencies/rbac.py` present in all three router files

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/api/routers/customers.py`](../../../src/api/routers/customers.py) L? — TBD - 待验证：13 个 endpoint 列表及每个 endpoint 的现有 dependency 签名

```{?}:?:src/api/routers/customers.py
# TBD - 待验证：现有 customers.py endpoint 签名样例（含 require_auth 但无 require_permission 的典型模式）
```

主入口：[`src/api/routers/sales.py`](../../../src/api/routers/sales.py) L? — TBD - 待验证：12 个 endpoint 列表

主入口：[`src/api/routers/tickets.py`](../../../src/api/routers/tickets.py) L? — TBD - 待验证：12 个 endpoint 列表

`require_permission` 定义：[`src/dependencies/rbac.py`](../../../src/dependencies/rbac.py) L? — TBD - 待验证：装饰器签名及 expected permission string format (`resource:action`)

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/customers.py`](../../../src/api/routers/customers.py) — Add `Depends(require_permission("customer:create"))` / `read` / `update` / `delete` to 13 endpoints; on `/leads` and `/leads/recycle` add `customer:read` on top of existing admin/manager role checks
  - [`src/api/routers/sales.py`](../../../src/api/routers/sales.py) — Add `Depends(require_permission("opportunity:create"))` / `opportunity:read` / etc. and `pipeline:create` / `pipeline:read` etc. to 12 endpoints
  - [`src/api/routers/tickets.py`](../../../src/api/routers/tickets.py) — Add `Depends(require_permission("ticket:create"))` / `ticket:read` / `ticket:update` to 12 endpoints
- 要建：
  - 无

### 2.3 缺什么

- [ ] `customers.py` 13 endpoints lack `require_permission` — all currently pass `require_auth` only
- [ ] `sales.py` 12 endpoints lack `require_permission` — no enforcement of `opportunity:*` or `pipeline:*` permissions
- [ ] `tickets.py` 12 endpoints lack `require_permission` — no enforcement of `ticket:*` permissions
- [ ] Import of `require_permission` from `src/dependencies/rbac.py` missing in all three files
- [ ] No standardized permission string mapping per endpoint — each endpoint must be assigned a `resource:action` per dev-plan §3.3
- [ ] `/leads` and `/leads/recycle` already have inline role checks but no `customer:read` on top — gap in layered enforcement

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| 无 | — 本板块不创建新文件 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/customers.py`](../../../src/api/routers/customers.py) | Add `from src.dependencies.rbac import require_permission` (or relative import per repo convention). Add `_: None = Depends(require_permission("customer:<action>"))` to all 13 endpoints. On `/leads` and `/leads/recycle`, add `customer:read` on top of existing role checks. |
| [`src/api/routers/sales.py`](../../../src/api/routers/sales.py) | Same import. Add `Depends(require_permission("opportunity:<action>"))` to opportunity endpoints and `pipeline:<action>` to pipeline endpoints across 12 endpoints. |
| [`src/api/routers/tickets.py`](../../../src/api/routers/tickets.py) | Same import. Add `Depends(require_permission("ticket:create"))` / `ticket:read` / `ticket:update` to 12 endpoints. |

### 3.3 新增能力

- **Permission enforcement** on 13 customer endpoints: `customer:create`, `customer:read`, `customer:update`, `customer:delete` — assigned per HTTP method/resource per dev-plan §3.3
- **Permission enforcement** on 12 sales endpoints: `opportunity:create`, `opportunity:read`, `opportunity:update`, `opportunity:delete`, `pipeline:create`, `pipeline:read`, `pipeline:update`, `pipeline:delete` — assigned per HTTP method/resource
- **Permission enforcement** on 12 ticket endpoints: `ticket:create`, `ticket:read`, `ticket:update` — assigned per HTTP method/resource
- **Layered enforcement** on `/leads` and `/leads/recycle`: existing admin/manager role check retained, `customer:read` added as a second gate

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **Use `Depends(require_permission(...))` as a separate parameter, not a decorator-only pattern**: The issue body explicitly specifies `_: None = Depends(require_permission("resource:action"))` as a second dependency after `require_auth`. This matches FastAPI's DI conventions and keeps the permission string visible in the function signature, making it greppable and self-documenting. The `_` discard name signals the return value is not used directly.
- **Do not replace existing inline role checks on `/leads` and `/leads/recycle`**: The issue body says to "add `customer:read` on top" — this means layered enforcement, not replacement. Role checks are a coarser mechanism; `customer:read` is the fine-grained permission. Both are needed.
- **Permission strings are static (not computed at runtime)**: Each endpoint gets a literal `"resource:action"` string. No dynamic string construction based on request data — that would be a security smell and an unnecessary complication.

### 4.2 版本约束

无新依赖 — `require_permission` already exists in `src/dependencies/rbac.py`.

### 4.3 兼容性约束

- The parameter name `_` is used for the `require_permission` dependency to signal the return value is discarded — do not rename to something like `_perm` or `perm` since the issue body is explicit.
- Session injection pattern unchanged: `session: AsyncSession = Depends(get_db)` stays exactly as-is (see CLAUDE.md §Router Pattern).
- `require_auth` stays as the first dependency on every endpoint — `require_permission` is added *after* it, not instead of it.
- Service-layer code is untouched — all RBAC enforcement is at the router boundary.
- No changes to response envelope structure (`{"success": true, "data": ...}`); permission denial raises `ForbiddenException` which the global handler converts to 403 (see CLAUDE.md §Error Handling).
- Multi-tenant filtering in service SQL is unchanged — `tenant_id` filtering remains a service-layer concern (see CLAUDE.md §Multi-Tenancy).

### 4.4 已知坑

1. **`require_permission` may not exist or may have a different signature than assumed** → 规避：在动笔前先 `grep -rn "def require_permission" src/dependencies/` 确认函数签名及 import path。如果 parent issue #643 的实现尚未合并，阻塞本板块并标记。
2. **Existing `/leads` and `/leads/recycle` role checks may use a different dependency mechanism** (e.g., `Depends(require_role("admin"))` vs. inline `if` check) → 规避：先 `grep -n "leads" src/api/routers/customers.py` 确认现有检查形态，再决定是 add-on 还是 refactor（issue 体指示是 add-on）。
3. **Permission string typo: writing `"customers:read"` (plural) instead of `"customer:read"`** → 规避：dev-plan §3.3 是 single source of truth. 复制粘贴权限字符串而非手打. 全部 37 个 endpoint 完成后用 `grep -E "require_permission\(\"[a-z]+:[a-z]+\""` 验证每个字符串都匹配 `^[a-z]+:[a-z]+$` 且符合 plan.
4. **Import path mismatch: `from src.dependencies.rbac import ...` vs. repo convention `from dependencies.rbac import ...`** → 规避：先看相邻 router 文件的现有 import 风格（CLAUDE.md 提示 `PYTHONPATH=src` 模式，import 写 `from db.models...`）。本项目路径前缀视具体子目录而定 — 在第一处 import 时 `grep "from src" src/api/routers/` 确认.

---

## 5. 实现步骤（按顺序）

### Step 1: 验证 `require_permission` 已存在并确认签名

在动笔改 router 之前，确认上游 #643 已落地。

操作：
- a) `grep -rn "def require_permission" src/dependencies/rbac.py` — 确认函数定义存在
- b) `grep -rn "from src.dependencies.rbac\|from dependencies.rbac" src/api/routers/` — 确认 import 路径惯例（如果 0 结果，看 git log 中 #643 的实现分支）
- c) 读取 `src/dependencies/rbac.py` 中 `require_permission` 的签名，确认为 `def require_permission(permission: str) -> ...`，返回值是 FastAPI-compatible dependency

**完成判定**：`grep` 找到唯一一处 `def require_permission`，且签名为 `def require_permission(permission: str)`。

### Step 2: 列出 `customers.py` 13 个 endpoint 及当前 permission 分配

操作：
- a) 打开 `src/api/routers/customers.py`，逐个 endpoint 记录：HTTP method、path、当前 dependency 列表
- b) 按 dev-plan §3.3 分配 `customer:create` / `customer:read` / `customer:update` / `customer:delete` 到每个 endpoint
- c) 特别标记 `/leads` 和 `/leads/recycle` — 这两个已有 admin/manager 角色检查，需要在其后追加 `customer:read`
- d) 在本板块文档下维护一个临时 mapping table（13 行）供 Step 4 使用

**完成判定**：产出 13 行 mapping table（`method`, `path`, `permission` 三列），无遗漏无歧义。

### Step 3: 列出 `sales.py` 12 个 endpoint 和 `tickets.py` 12 个 endpoint 的 permission 分配

操作：
- a) 同样方法对 `src/api/routers/sales.py` 12 个 endpoint 分配 `opportunity:*` 和 `pipeline:*` 权限
- b) 同样方法对 `src/api/routers/tickets.py` 12 个 endpoint 分配 `ticket:create` / `ticket:read` / `ticket:update` 权限
- c) 三个 mapping table 加起来共 37 行

**完成判定**：37 行 mapping table 全部就绪，每行 permission 字符串符合 `^[a-z]+:[a-z]+$`。

### Step 4: 改 `customers.py` — 加入 import 和 13 处 dependency

操作：
- a) 在 `src/api/routers/customers.py` 顶部加入 import：`from src.dependencies.rbac import require_permission`（或相对路径，按 Step 1b 确认的惯例）
- b) 对 13 个 endpoint 中的每一个，在 `ctx: AuthContext = Depends(require_auth)` 之后追加 `_: None = Depends(require_permission("<分配好的权限字符串>"))`
- c) 对 `/leads` 和 `/leads/recycle` 这两个 endpoint，在现有 role-based 检查后追加 `_: None = Depends(require_permission("customer:read"))` — 保留原 role check
- d) 保持缩进、换行、其他参数完全不动

示例代码（典型 CRUD endpoint）：

```python
@router.post("/")
async def create_customer(
    payload: CustomerCreate,
    ctx: AuthContext = Depends(require_auth),
    _: None = Depends(require_permission("customer:create")),
    session: AsyncSession = Depends(get_db),
):
    svc = CustomerService(session)
    customer = await svc.create_customer(payload, tenant_id=ctx.tenant_id)
    return {"success": True, "data": customer.to_dict()}
```

**完成判定**：`grep -c "require_permission(" src/api/routers/customers.py` → 13（包括 import 行的 1 次 + endpoint 处的 12 次，或 13 次 endpoint 使用 + 1 次 import = 14 — 实际数字取决于统计口径，关键是 ≥ 13）。`ruff check src/api/routers/customers.py` → 0 errors。

### Step 5: 改 `sales.py` — 12 处 dependency

操作：
- a) 在 `src/api/routers/sales.py` 顶部加入同样的 import
- b) 对 12 个 endpoint 按 Step 3a 的 mapping table 逐个追加 `_: None = Depends(require_permission("opportunity:<action>"))` 或 `pipeline:<action>`
- c) 注意区分 opportunity router 和 pipeline router（如果文件内部分段）

**完成判定**：`ruff check src/api/routers/sales.py` → 0 errors。`grep -c "require_permission(" src/api/routers/sales.py` ≥ 12。

### Step 6: 改 `tickets.py` — 12 处 dependency

操作：
- a) 在 `src/api/routers/tickets.py` 顶部加入同样的 import
- b) 对 12 个 endpoint 按 Step 3b 的 mapping table 逐个追加 `_: None = Depends(require_permission("ticket:create"))` / `ticket:read` / `ticket:update`
- c) 注意 ticket delete（如果有）按 dev-plan §3.3 决定 — issue 体仅列 `ticket:create/read/update`，所以 delete 端点可能不需要此 permission，或需要 `ticket:delete`（待 Step 1 确认 dev-plan 完整列表）

**完成判定**：`ruff check src/api/routers/tickets.py` → 0 errors。`grep -c "require_permission(" src/api/routers/tickets.py` ≥ 12。

### Step 7: 全量验证

操作：
- a) `ruff check src/api/routers/customers.py src/api/routers/sales.py src/api/routers/tickets.py` → 期望 0 errors
- b) `PYTHONPATH=src pytest tests/unit/ -v` → 期望全部 passed（不应有回归）
- c) `grep -E "require_permission\(\"[a-z]+:[a-z]+\""` 三个文件 → 期望共 37 个匹配（每个 endpoint 一处）
- d) 手动 spot-check 3-5 个 endpoint 的函数签名，确认 `_` 参数位置在 `require_auth` 之后、其他参数之前

**完成判定**：a/b/c 三条全部满足；d 步无异常。

---

## 6. 验收

- [ ] `ruff check src/api/routers/customers.py src/api/routers/sales.py src/api/routers/tickets.py` → 0 errors
- [ ] `grep -c "require_permission(" src/api/routers/customers.py` → ≥ 13
- [ ] `grep -c "require_permission(" src/api/routers/sales.py` → ≥ 12
- [ ] `grep -c "require_permission(" src/api/routers/tickets.py` → ≥ 12
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → all pre-existing tests pass (no regression)
- [ ] 每个 endpoint 的 `_` dependency 参数位置：`Depends(require_auth)` 在前，`Depends(require_permission("..."))` 紧随其后

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `require_permission` 在 #643 中尚未实现或签名与预期不符 | 中 | 高 | 在 Step 1 立即阻塞本板块并等待 #643 合并；不进行任何 router 改动以避免引入未验证的 import |
| Permission string 与 dev-plan §3.3 不一致（typo / 误用复数） | 中 | 中 | 全部改动完成后用 `grep -E "require_permission\(\"[a-z]+:[a-z]+\""` 列出所有 permission string 并逐条与 §3.3 对照；不一致处手动修正 |
| 改动某个 endpoint 时漏掉 `_` 前缀或误用其他变量名 | 低 | 低 | Step 7d 的 spot-check 显式核对 3-5 个 endpoint 的签名；如有遗漏回到 Step 4-6 修补 |
| 现有测试在权限层未 mock `require_permission`，引入后部分测试 403 | 中 | 中 | 视情况：(a) 如果是单元测试且本板块不新增测试 scope，跳过并记录到下游测试板块；(b) 如果是回归，需要在该测试 fixture 中加一个允许所有权限的 override dependency |
| `/leads` 和 `/leads/recycle` 现有 role check 机制与 `Depends` 模式不兼容（如是 inline `if`） | 低 | 低 | 保留 inline 检查不动，`customer:read` 作为额外的 `Depends` 参数叠加，layered enforcement 即可 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/customers.py src/api/routers/sales.py src/api/routers/tickets.py
git commit -m "feat(rbac): wire require_permission into customers, sales, and tickets routers

Closes #790"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "Wire @require_permission into customers, sales, and tickets routers" --body "Closes #790

Subtask of #643. Adds Depends(require_permission('resource:action')) to all
endpoints in customers.py (13), sales.py (12), and tickets.py (12).
Permission strings follow dev-plan §3.3. /leads and /leads/recycle retain
existing role checks with customer:read added on top."

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 父 issue / 关联：#790, subtask of #643
- 同类参考实现：TBD - 待验证：src/api/routers/ 下可能已 wired 的其他 router 文件（如 reports / users / rbac / tenants）可作为 import 和 dependency 摆放位置的参照
- 第三方文档：TBD - 待验证：FastAPI 官方文档关于 `Depends` 链式依赖的部分（仅当 Step 1 发现 require_permission 的实现细节不直观时查阅）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-06-04 | 创建 | TBD |
