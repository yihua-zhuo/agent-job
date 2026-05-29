# 更新 Identity 模型导入路径 · 统一所有旧路径指向新 identity 模块

| 元数据 | 值 |
|---|---|
| Issue | #428 |
| 分类 | [00-foundations](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5-1 工作日 |
| 依赖 | [统一 Identity ORM 模型结构 #427](../10-customers/0427-unify-identity-orm-model-structure.md) |
| 启用后赋能 | [创建 CustomerService + DB 仓储层 #430](), [实现 CampaignService #454](), [实现 WorkflowService #463]() |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #427 consolidated the legacy `tenant`, `user`, and `rbac` ORM models into a single `db.models.identity` module. All code that still imports from the old paths (`db.models.tenant`, `db.models.user`, `db.models.rbac`) is now broken — it references files that no longer exist or have been removed. Every source file under `src/` and `tests/` must be audited and updated to use the new canonical import path.

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯内部重构。
- **开发者视角**：All service, router, middleware, and dependency modules import identity models exclusively from `db.models.identity`. Re-exports in `db.models.__init__.py` for the old files are removed. `pytest tests/unit/ -v` passes with zero failures.

### 1.3 不做什么（剔除）

- [ ] No new ORM models or database migrations — this is purely import-path cleanup.
- [ ] No changes to business logic in services or routers.
- [ ] No changes to API surface or request/response schemas.

### 1.4 关键 KPI

- `grep -r "from db\.models\.tenant\|from db\.models\.user\|from db\.models\.rbac" src/ tests/` → 0 results
- `PYTHONPATH=src pytest tests/unit/ -v` → all passed (baseline established in #427 must not regress)
- `ruff check src/` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD — 待验证：`src/db/models/identity.py` L? — 新 consolidated identity model 文件（由 #427 创建）
TBD — 待验证：`src/db/models/__init__.py` L? — 可能仍 re-export from `tenant`, `user`, `rbac`（需移除）
TBD — 待验证：`src/db/models/tenant.py` L? — 旧文件（可能已被 #427 删除或保留为 alias）
TBD — 待验证：`src/db/models/user.py` L? — 旧文件（同上）
TBD — 待验证：`src/db/models/rbac.py` L? — 旧文件（同上）

### 2.2 涉及文件清单

- 要改：
  - `src/db/models/__init__.py` — 移除对旧 tenant/user/rbac 的 re-export
  - `src/services/*.py` — 全量扫描，更新 import 路径
  - `src/api/routers/*.py` — 全量扫描，更新 import 路径
  - `src/middleware/*.py` — 全量扫描，更新 import 路径
  - `src/dependencies/*.py` — 全量扫描，更新 import 路径
  - `tests/unit/test_*.py` — 全量扫描，更新 import 路径
  - `tests/integration/test_*_integration.py` — 全量扫描，更新 import 路径
- 要建：
  - 无新文件

### 2.3 缺什么

- [ ] 全量 `grep` 统计：哪些文件仍持有旧 import（`db.models.tenant`, `db.models.user`, `db.models.rbac`）
- [ ] 已更新 import 的文件需验证 `ruff check` 零报错
- [ ] `__init__.py` re-export 清理未完成（若有）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| 无 | 无新建模块 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/db/models/__init__.py` | 移除 `from .tenant import`, `from .user import`, `from .rbac import` re-export行 |
| `src/services/*.py` | `from db.models.identity import ...` 替换旧 `from db.models.tenant/user/rbac` |
| `src/api/routers/*.py` | 同上 import 替换 |
| `src/middleware/*.py` | 同上 import 替换 |
| `src/dependencies/*.py` | 同上 import 替换 |
| `tests/unit/test_*.py` | 同上 import 替换 |
| `tests/integration/test_*_integration.py` | 同上 import 替换 |

### 3.3 新增能力

- **Import consolidation**：所有身份模型（Tenant, User, RBAC 实体）统一从 `db.models.identity` 导入
- **Re-export cleanup**：`db.models.__init__.py` 不再 re-export 旧路径下的任何符号
- **Test coverage**：全部既有单元测试和集成测试在 import 重定向后仍通过

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **保留旧文件 vs. 删除**：若 `tenant.py` / `user.py` / `rbac.py` 在 #427 中被删除，则此板块无此选择；若仍存在但仅作 stub alias，则统一导入新模块更简洁。
- **逐文件修改 vs. 全局 sed**：推荐逐文件确认（manual grep review），避免误替换非 identity 相关的同名词（如某服务内有 `tenant = ...` 局部变量）。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 所有 service 的 `__init__` 保持 `session: AsyncSession` 无默认值（不变）
- 所有 service 方法签名不变，仅 import 语句变化
- Router 的 `Depends(get_db)` 用法不变
- 测试 mock fixture 结构不变

### 4.4 已知坑

1. **误替换局部变量**：`tenant` / `user` / `rbac` 可能作为局部变量名存在于函数体内，sed 替换时必须只替换 `import` 行和 `from ... import` 行，不能替换函数体内的赋值。→ 规避：只用 `grep -n "from db\.models\.\(tenant\|user\|rbac\)"` 定位 import 行，逐文件手动修改。
2. **Re-export 残留**：`__init__.py` 的 re-export 若不移除，其他模块仍可通过 `from db.models import Tenant` 绕过，导致两套路径并存。→ 规避：修改后执行 `grep "from db\.models import" src/ tests/ -r` 确认没有通过 `__init__.py` 再导出旧符号。
3. **Alembic autogen 写 JSON 而非 JSONB**（不直接相关于此 issue，但 lint 检查时若涉及 migration 文件需注意）。

---

## 5. 实现步骤（按顺序）

### Step 1: 全量扫描旧 import，生成清单

用 `grep` 列出所有持旧路径 import 的文件，确认范围。

操作：
a) 在 `src/` 目录执行：

```bash
grep -rn "from db\.models\.tenant\|from db\.models\.user\|from db\.models\.rbac" src/ --include="*.py"
```

b) 在 `tests/` 目录执行：

```bash
grep -rn "from db\.models\.tenant\|from db\.models\.user\|from db\.models\.rbac" tests/ --include="*.py"
```

c) 统计输出行数，确认范围。

**完成判定**：`grep -rn "from db\.models\.\(tenant\|user\|rbac\)" src/ tests/` 输出行数已知，文件清单已记录于 §2.2

---

### Step 2: 更新 `src/db/models/__init__.py` 的 re-export

检查并移除对旧模块的 re-export 行（若存在）。

操作：
a) 读取 `src/db/models/__init__.py`
b) 找到类似以下行并删除：

```python
from .tenant import Tenant  # 删除
from .user import User     # 删除
from .rbac import Role, Permission  # 删除
```

c) 确认文件中仅从 `.identity` 导出身份模型（若 `.identity` 有自己的 `__all__`）。

**完成判定**：`grep "from db\.models\.\(tenant\|user\|rbac\)" src/db/models/__init__.py` → 0 results

---

### Step 3: 更新 `src/` 下所有文件的 import（services / api / middleware / dependencies）

逐文件将旧 import 替换为新路径。

操作：
a) 对于每个在 Step 1 中发现的文件，替换 import 行：

```python
# 旧（替换前）
from db.models.tenant import Tenant
from db.models.user import User
from db.models.rbac import Role, Permission

# 新（替换后）
from db.models.identity import Tenant, User, Role, Permission
```

b) 若同一文件同时 import 了多个旧模块，合并为一条 `from db.models.identity import ...`（按该文件已有 `.identity` import 风格对齐）。

示例代码：

```python
# src/services/customer_service.py
# 更新前
from db.models.tenant import Tenant
from db.models.user import User

# 更新后
from db.models.identity import Tenant, User
```

**完成判定**：`grep -rn "from db\.models\.\(tenant\|user\|rbac\)" src/` → 0 results

---

### Step 4: 更新 `tests/` 下所有文件的 import

操作：同 Step 3，对 `tests/unit/` 和 `tests/integration/` 下所有文件执行相同 import 替换。

**完成判定**：`grep -rn "from db\.models\.\(tenant\|user\|rbac\)" tests/` → 0 results

---

### Step 5: 运行测试验证无回归

执行完整测试套件，确认 import 重定向未破坏任何现有测试。

操作：

```bash
export PYTHONPATH=src
pytest tests/unit/ -v
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/ -v` → all passed（exit 0）

---

## 6. 验收

- [ ] `grep -rn "from db\.models\.\(tenant\|user\|rbac\)" src/` → 0 results
- [ ] `grep -rn "from db\.models\.\(tenant\|user\|rbac\)" tests/` → 0 results
- [ ] `PYTHONPATH=src pytest tests/unit/ -v` → all passed (exit 0)
- [ ] `PYTHONPATH=src pytest tests/integration/ -v` → all passed (exit 0)
- [ ] `ruff check src/` → 0 errors
- [ ] `ruff check tests/` → 0 errors

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 误替换函数体内的局部变量名（`tenant`/`user`/`rbac`）导致运行时错误 | 低 | 中 | 人工 review 每个文件的 diff；若已推送，`git revert <commit>` 回退该文件 |
| 遗漏某个文件未更新 import，导致 `ImportError` 在 CI | 中 | 中 | 以 Step 1 的完整清单为 checklist，逐文件核销；CI 失败即补充修复 |
| `__init__.py` re-export 未清除干净，部分测试仍通过旧路径引用 | 低 | 低 | 运行 `grep "from db\.models import Tenant" src/ tests/` 确认无残留 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/db/models/__init__.py src/services/ src/api/routers/ src/middleware/ src/dependencies/ tests/unit/ tests/integration/
git commit -m "refactor: update all imports to db.models.identity (closes #428)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "refactor(#428): update identity model import paths" --body "Closes #428"

# 2. 更新进度
# - 在本板块文档 Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[统一 Identity ORM 模型结构 #427](../10-customers/0427-unify-identity-orm-model-structure.md)
- 父 issue：[实现 Identity 模型层 #270](../../README.md)
- 依赖前置：[统一 Identity ORM 模型结构 #427](../10-customers/0427-unify-identity-orm-model-structure.md)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
