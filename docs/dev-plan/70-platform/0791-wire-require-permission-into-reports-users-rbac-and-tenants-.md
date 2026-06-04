# RBAC 权限装饰器接入 · Wire require_permission into 4 routers

| 元数据 | 值 |
|---|---|
| Issue | #791 |
| 分类 | [70-platform](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [Wire require_permission into activities, notifications, automation (#792)](../70-platform/0792-wire-require-permission-into-activities-notifications-automa.md)（并行，无代码依赖）, #790（提供 `require_permission` 装饰器本身） |
| 启用后赋能 | [Create test_permission_denied.py and run full verification (#793)](../70-platform/0793-create-test-permission-denied-py-and-run-full-verification.md)（跨切面权限测试依赖本板块完成） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `src/api/routers/reports.py`、`src/api/routers/users.py`、`src/api/routers/rbac.py`、`src/api/routers/tenants.py` 四个 router 中所有 endpoint 缺少统一的权限校验装饰器，导致任何已认证用户都能调用任意 endpoint，违反多租户 CRM 的最小权限原则。这与 #643 的 RBAC 体系建设目标直接对齐，而 #790 已提供 `require_permission` 装饰器实现，本板块负责将其落地到第二批 4 个 router（首批见 #792）。

### 1.2 做完后

- **用户视角**：非授权用户调用 reports/users/rbac/tenants 下任一受保护 endpoint 时，统一收到 403 Forbidden（由 `AppException` 全局处理器序列化为标准错误响应），而非返回成功结果。
- **开发者视角**：所有 4 个 router 中的 endpoint 显式声明所需权限 code（如 `report:create`、`user:read`、`rbac:manage`、`tenant:read`），新代码贡献者一眼可读，权限矩阵在 router 层集中可见。

### 1.3 不做什么（剔除）

- [ ] 不修改 `require_permission` 装饰器实现本身（属于 #790 范围）
- [ ] 不实现活动、通知、自动化等 router 的权限装饰（属于 #792）
- [ ] 不编写跨切面权限拒绝测试（属于 #793）
- [ ] 不引入新依赖、不修改数据库 schema、不生成 Alembic migration

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src ruff check src/api/routers/reports.py src/api/routers/users.py src/api/routers/rbac.py src/api/routers/tenants.py` → 0 errors]
- [指标 2：4 个 router 中 `report:create`/`report:read`/`report:update`/`report:delete`/`user:create`/`user:read`/`user:update`/`user:delete`/`rbac:manage`/`rbac:read`/`tenant:manage`/`tenant:read` 共 12 个权限 code 全部出现，每个 code 至少被一个 `@require_permission` 装饰器引用]
- [指标 3：users router 中 `/auth/login` 与 `/auth/register` 两个 endpoint 不带 `@require_permission` 装饰器]
- [指标 4：`PYTHONPATH=src pytest tests/unit/ -v` → 全部 passed（无回归）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

`require_permission` 装饰器定义入口：[`src/dependencies/rbac.py`](../../../src/dependencies/rbac.py) L{TBD - 待验证：`require_permission` 函数定义行}

```python
# TBD - 待验证：require_permission 装饰器签名 + 行为
# from src/dependencies/rbac.py（由 #790 提供）
def require_permission(permission: str):
    """Decorator that enforces a named permission on a FastAPI endpoint."""
    ...
```

主入口（待修改的 4 个 router）：

- [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) L{TBD - 待验证：7 个 endpoint 定义起始行} — 含 7 个 endpoint
- [`src/api/routers/users.py`](../../../src/api/routers/users.py) L{TBD - 待验证：除 /auth/login 与 /auth/register 外的 endpoint 行} — 含除 2 个 auth endpoint 外的全部 endpoint
- [`src/api/routers/rbac.py`](../../../src/api/routers/rbac.py) L{TBD - 待验证：13 个 endpoint 定义行} — 含 13 个 endpoint
- [`src/api/routers/tenants.py`](../../../src/api/routers/tenants.py) L{TBD - 待验证：7 个 endpoint 定义行} — 含 7 个 endpoint

代码片段（典型 endpoint 现状，4 个 router 共用模式）：

```python
# TBD - 待验证：典型 endpoint 当前签名（缺少 @require_permission 装饰器）
@router.get("/")
async def list_reports(
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ReportService(session)
    items, total = await svc.list_reports(tenant_id=ctx.tenant_id, ...)
    return {"success": True, "data": {"items": [i.to_dict() for i in items], "total": total}}
```

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) — 为 7 个 endpoint 添加 `@require_permission` 装饰器
  - [`src/api/routers/users.py`](../../../src/api/routers/users.py) — 为除 `/auth/login` 与 `/auth/register` 外的所有 endpoint 添加 `@require_permission` 装饰器
  - [`src/api/routers/rbac.py`](../../../src/api/routers/rbac.py) — 为 13 个 endpoint 添加 `@require_permission` 装饰器
  - [`tests/unit/test_reports.py`](../../../tests/unit/test_reports.py) — 等等：当前仅有 router 改动，单元测试覆盖在 #793 中处理；如现有 unit test 期望 200 而新行为返回 403，则需更新
- 要建：
  - 无新文件

### 2.3 缺什么

- [ ] 4 个 router 中所有 endpoint 缺少显式权限声明，无法实施最小权限原则
- [ ] 无统一机制区分读操作与写操作的权限 code
- [ ] 缺少对未授权调用者的标准化 403 响应（依赖 #790 已提供的 `ForbiddenException` 路径）
- [ ] users router 中的 auth 端点（login/register）需豁免权限校验，目前缺少文档化该特例的注释或模式

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| 无 | 本板块不创建新文件 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) | 在文件顶部新增 `from src.dependencies.rbac import require_permission`；为 7 个 endpoint 添加装饰器，权限映射：写操作用 `report:create`/`report:update`/`report:delete`，读操作用 `report:read` |
| [`src/api/routers/users.py`](../../../src/api/routers/users.py) | 新增 `require_permission` 导入；为除 `/auth/login` 与 `/auth/register` 外的所有 endpoint 添加装饰器，权限 code：`user:create`/`user:read`/`user:update`/`user:delete` |
| [`src/api/routers/rbac.py`](../../../src/api/routers/rbac.py) | 新增 `require_permission` 导入；为 13 个 endpoint 添加装饰器，写操作用 `rbac:manage`，读操作用 `rbac:read` |
| [`src/api/routers/tenants.py`](../../../src/api/routers/tenants.py) | 新增 `require_permission` 导入；为 7 个 endpoint 添加装饰器，写操作用 `tenant:manage`，读操作用 `tenant:read` |

### 3.3 新增能力

- **Service method**：无（本板块纯 router 层装饰器接入）
- **API endpoint**：无新增 endpoint；为 34 个（7 + 8–10 + 13 + 7）现有 endpoint 增加权限校验
- **ORM model**：无
- **Migration**：无

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 import-level `from src.dependencies.rbac import require_permission` 不选函数内延迟导入**：装饰器在模块加载时就需要被解析（用于 endpoint 注册），延迟导入会导致 `NameError`。且这与 #790 中 `require_auth` 的现有导入模式一致。
- **选 router 入口装饰器不选 service 层校验**：service 仍只接受 `tenant_id` 参数，权限是 HTTP 层关注点（FastAPI `Depends` 体系），保持 service 纯净可被其他内部调用者复用。
- **选 12 个细粒度权限 code 不选单一通配 code（如 `reports:all`）**：与 #643 的 RBAC 设计保持一致，未来可按角色精细分配；issue body 明确指定 code 集合。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）—— 本板块不改变 SQL，但权限装饰器位于 `tenant_id` 注入之前，依赖 `require_auth` 提供 `AuthContext`
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责 —— 本板块不触碰 service
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()` —— `require_permission` 在缺少权限时由 #790 实现为抛 `ForbiddenException`
- Auth 端点豁免：`/auth/login` 与 `/auth/register` 不加 `@require_permission`（未认证用户也必须能调用），与 #790 的设计保持一致
- 导入路径必须为 `from src.dependencies.rbac import require_permission`（CLAUDE.md 未显式列出 src. 前缀规则，但 #790 与本板块的 issue body 均使用 `src/dependencies/rbac.py` 路径）

### 4.4 已知坑

1. **装饰器顺序：`@require_permission` 必须位于 `@router.{method}` 之下、`@app.{method}` 之上，且通常在 `async def` 函数定义紧贴其上** → 规避：每个 endpoint 保持单一 `@router.*` + 单一 `@require_permission` + 单一 `@...`（如有其他装饰器）顺序；不要把 `@require_permission` 写在 `@router.get` 之上（会被 FastAPI 忽略）
2. **PYTHONPATH=src 必须在运行 ruff/pytest 前 export**（见 CLAUDE.md §Gotchas）→ 规避：所有验证命令前缀 `PYTHONPATH=src`
3. **若现有 unit test 直接调用 endpoint 而未 mock `require_permission`，加装饰器后测试可能开始失败**（mock 链不匹配）→ 规避：先运行 `pytest tests/unit/ -v` 确认 baseline；如出现新失败，在 #793 中统一处理（不在本板块单独修测试，避免与 #793 scope 冲突）
4. **auth 端点误加装饰器会导致未登录用户无法登录** → 规避：在 users.py 中显式为 `/auth/login` 与 `/auth/register` 加 1 行注释 `<!-- intentionally no @require_permission: public auth endpoint -->`

---

## 5. 实现步骤（按顺序）

### Step 1: 在 reports.py 中加入 require_permission 导入

在 [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) 顶部 import 区块（紧邻 `from src.dependencies...` 或 `from internal.middleware.fastapi_auth import ...` 之后）新增一行 import。

操作：
- a) 在文件最顶部 import 区块添加 `from src.dependencies.rbac import require_permission`
- b) 不修改 import 区块中其他行的顺序

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/reports.py` → 0 errors（仅新增 import 不破坏语法）

### Step 2: 为 reports.py 的 7 个 endpoint 添加装饰器

在 [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) 中为 7 个 endpoint（list/create/get/update/delete/export/...) 逐个添加 `@require_permission("<code>")`。

操作：
- a) 写操作（POST/PUT/PATCH/DELETE）endpoint 上方添加 `@require_permission("report:create")` 或 `report:update` 或 `report:delete`
- b) 读操作（GET）endpoint 上方添加 `@require_permission("report:read")`
- c) 装饰器置于 `@router.*` 与 `async def` 之间

示例代码（写操作 endpoint 模式）：

```python
@router.post("/")
@require_permission("report:create")
async def create_report(
    payload: ReportCreate,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = ReportService(session)
    report = await svc.create_report(payload, tenant_id=ctx.tenant_id, user_id=ctx.user_id)
    return {"success": True, "data": report.to_dict()}
```

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/reports.py` → 0 errors；`grep -c "@require_permission" src/api/routers/reports.py` → 7

### Step 3: 在 users.py 中加入 require_permission 导入

在 [`src/api/routers/users.py`](../../../src/api/routers/users.py) 顶部 import 区块新增 `from src.dependencies.rbac import require_permission`。

操作：
- a) 添加 import 行，位置与 reports.py 一致
- b) 不修改 auth 子路由的现有 import

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/users.py` → 0 errors

### Step 4: 为 users.py 的非 auth endpoint 添加装饰器

在 [`src/api/routers/users.py`](../../../src/api/routers/users.py) 中为除 `/auth/login` 与 `/auth/register` 外的所有 endpoint 添加 `@require_permission("user:...")` 装饰器。

操作：
- a) 在 `/auth/login` 与 `/auth/register` 的 `async def` 上方添加 1 行注释说明 public 豁免
- b) POST 写操作（create user）添加 `@require_permission("user:create")`
- c) PUT/PATCH/DELETE 操作分别添加 `user:update` / `user:delete`
- d) GET 操作添加 `@require_permission("user:read")`

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/users.py` → 0 errors；`grep -c "@require_permission" src/api/routers/users.py` 与该文件非 auth endpoint 数量相等；`grep "auth/login\|auth/register" src/api/routers/users.py` 命中行上下文中无 `@require_permission`

### Step 5: 在 rbac.py 中加入 require_permission 导入

在 [`src/api/routers/rbac.py`](../../../src/api/routers/rbac.py) 顶部 import 区块新增 `from src.dependencies.rbac import require_permission`。

操作：
- a) 添加 import 行

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/rbac.py` → 0 errors

### Step 6: 为 rbac.py 的 13 个 endpoint 添加装饰器

在 [`src/api/routers/rbac.py`](../../../src/api/routers/rbac.py) 中为 13 个 endpoint 添加装饰器。

操作：
- a) 写操作（POST/PUT/PATCH/DELETE：角色/权限/赋权）添加 `@require_permission("rbac:manage")`
- b) 读操作（GET：列出角色/权限/用户角色）添加 `@require_permission("rbac:read")`

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/rbac.py` → 0 errors；`grep -c "@require_permission" src/api/routers/rbac.py` → 13

### Step 7: 在 tenants.py 中加入 require_permission 导入

在 [`src/api/routers/tenants.py`](../../../src/api/routers/tenants.py) 顶部 import 区块新增 `from src.dependencies.rbac import require_permission`。

操作：
- a) 添加 import 行

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/tenants.py` → 0 errors

### Step 8: 为 tenants.py 的 7 个 endpoint 添加装饰器

在 [`src/api/routers/tenants.py`](../../../src/api/routers/tenants.py) 中为 7 个 endpoint 添加装饰器。

操作：
- a) 写操作（POST/PUT/PATCH/DELETE：创建/更新/删除 tenant）添加 `@require_permission("tenant:manage")`
- b) 读操作（GET：列出/获取 tenant）添加 `@require_permission("tenant:read")`

**完成判定**：`PYTHONPATH=src ruff check src/api/routers/tenants.py` → 0 errors；`grep -c "@require_permission" src/api/routers/tenants.py` → 7

### Step 9: 全量 ruff 与 import 一致性校验

对 4 个文件统一运行 ruff，并对权限 code 字符串进行去重与存在性检查。

操作：
- a) 运行 `PYTHONPATH=src ruff check src/api/routers/reports.py src/api/routers/users.py src/api/routers/rbac.py src/api/routers/tenants.py`
- b) 运行 `grep -hE "require_permission\(\"[a-z:]+" src/api/routers/reports.py src/api/routers/users.py src/api/routers/rbac.py src/api/routers/tenants.py | sort -u` 确认 12 个 code 全部出现：`report:create`、`report:read`、`report:update`、`report:delete`、`user:create`、`user:read`、`user:update`、`user:delete`、`rbac:manage`、`rbac:read`、`tenant:manage`、`tenant:read`

**完成判定**：ruff 0 errors；grep 输出包含上述全部 12 个权限 code

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/api/routers/reports.py src/api/routers/users.py src/api/routers/rbac.py src/api/routers/tenants.py` → `0 errors`
- [ ] `grep -c "@require_permission" src/api/routers/reports.py` → `7`
- [ ] `grep -c "@require_permission" src/api/routers/users.py` → 与非 auth endpoint 数量一致（auth/login 与 auth/register 除外）
- [ ] `grep -c "@require_permission" src/api/routers/rbac.py` → `13`
- [ ] `grep -c "@require_permission" src/api/routers/tenants.py` → `7`
- [ ] 12 个权限 code 全部出现在对应 router 中：`report:create`、`report:read`、`report:update`、`report:delete`、`user:create`、`user:read`、`user:update`、`user:delete`、`rbac:manage`、`rbac:read`、`tenant:manage`、`tenant:read`
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → 全部 passed（如出现新失败，归入 #793 处理；本板块不强制要求 0 新失败，但应记录到 PR 描述）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 装饰器接入后现有 unit test 因未 mock 权限链路而失败 | 中 | 中 | 立即 revert 单个 router 改动；将该 router 暂时排除在 PR 之外；其余 router 继续；失败测试在 #793 中统一处理 |
| 误给 `/auth/login` 或 `/auth/register` 添加装饰器导致登录接口 403 | 低 | 高 | 在 merge 前对 users.py 运行 `grep -B1 "auth/login\|auth/register" src/api/routers/users.py` 人工复核；如已合并，hotfix 删除装饰器即可，无 schema 变更 |
| `require_permission` 在 #790 阶段未实现或 import 路径不匹配导致模块加载报错 | 低 | 高 | 在 Step 1 前先 `python -c "from src.dependencies.rbac import require_permission"` 验证 import 可用；如不可用，暂停本板块并阻塞 #790 |
| 装饰器顺序错误（写在 `@router.*` 之上）导致被 FastAPI 忽略 | 中 | 中 | Step 9 统一通过 grep 校验所有 `@require_permission` 紧跟在 `@router.*` 之后；如发现顺序错误，编辑器手动调整 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/reports.py src/api/routers/users.py src/api/routers/rbac.py src/api/routers/tenants.py
git commit -m "feat(rbac): wire @require_permission into reports, users, rbac, tenants routers"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "Wire @require_permission into 4 routers (#791)" --body "Closes #791"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：#792（activities/notifications/automation router 接入，同结构）
- 第三方文档：FastAPI 装饰器顺序 — https://fastapi.tiangolo.com/tutorial/bigger-applications/
- 父 issue / 关联：#643（RBAC 体系父 issue）、#790（require_permission 装饰器提供方）、#792（并行板块）、#793（依赖本板块的测试板块）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-06-04 | 创建 | TBD |
