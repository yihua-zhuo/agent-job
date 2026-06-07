# [板块短名] · [一句话目标，10-15 字]

<!--
  ============================================================================
  中度模板（适用于大多数 issue）。
  约 200-350 行。
  保留所有 8 段，每段长度按右侧注释控制。
  填完后必须删掉所有 <!-- ... --> 注释。
  违反 README.md §2 全局约束的内容会被退回。
  Project: this repo is a multi-tenant CRM (FastAPI + SQLAlchemy 2.x async + PostgreSQL).
  ============================================================================
-->

| 元数据 | 值 |
|---|---|
| Issue | #{n}                                       <!-- GitHub issue 号，必填 -->
| 分类 | [分类码](../README.md#12-分类总览)         <!-- 如 20-sales -->
| 优先级 | 必做 / 推荐 / 可选                          <!-- 三选一 -->
| 工作量 | N 工作日（或 N-M 工作日区间）                <!-- 实事求是，0.25-3 范围 -->
| 依赖 | [板块名](相对路径), ...                       <!-- 没依赖填「无」；不要发明不存在的板块 -->
| 启用后赋能 | [板块名](相对路径), ...                  <!-- 谁需要等本板块完成；没有填「无」 -->
| 状态 | 📋 待开始                                 <!-- 见 README §2.12 -->

---

## 1. 目标与背景

<!--
  4 段，每段 2-4 行（共 50-80 行）：
  - 为什么做（业务/技术驱动）
  - 做完世界变成什么样（用户视角 + 开发者视角各 1 段）
  - 不在本板块范围（明确剔除项，避免 scope creep）
  - 关键 KPI 或验证指标（数字化）
-->

### 1.1 为什么做

[此处填：当前实现的缺陷或限制；为何这是必须解决的事]

### 1.2 做完后

- **用户视角**：[填：终端用户/管理员看到什么变化；如果是纯底层 schema/infra 改动，明确写「无用户可见变化 — 纯底层」]
- **开发者视角**：[填：可调用什么新 service / router / model；获得什么能力]

### 1.3 不做什么（剔除）

- [ ] [明确不在本板块范围的事项 1]
- [ ] [明确不在本板块范围的事项 2]

### 1.4 关键 KPI

- [指标 1：数字化目标，如「`pytest tests/unit/test_x.py -v` → ≥ 5 passed」]
- [指标 2：如「`alembic upgrade head && alembic downgrade -1` 两次都 exit 0」]
- [指标 3：如「`ruff check src/services/x.py` → 0 errors」]

---

## 2. 当前现状（起点）

<!--
  3 段，每段 5-10 行（共 30-60 行）：
  - 现有实现：引用具体文件 + 行号 + 关键代码片段（5-15 行）。
    若你不能确认文件/行号存在，写「TBD - 待验证：<要查的内容>」。
  - 已知文件清单（要改/扩的）
  - 缺什么（bullet list，3-8 条）
-->

### 2.1 现有实现

主入口：[`相对路径`](../../../相对路径) L{x}-L{y}

```{x}:{y}:相对路径
[5-15 行关键代码片段]
```

<!-- 新建模块时，§2.1 直接写：N/A — 新建模块 -->

### 2.2 涉及文件清单

- 要改：
  - [`src/services/customer_service.py`](../../../src/services/customer_service.py) — [改动要点]
  - [`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py) — [改动要点]
- 要建：
  - `src/db/models/<new_model>.py` — [用途]
  - `alembic/versions/<id>_<slug>.py` — [用途]
  - `tests/unit/test_<new>.py` — [用途]

### 2.3 缺什么

- [ ] [缺失能力 1，描述 + 影响]
- [ ] [缺失能力 2]

---

## 3. 目标产物（终点）

<!--
  3 段（共 30-50 行）：
  - 新增文件列表（每行：路径 + 1 句话用途）
  - 修改文件列表（每行：路径 + 改动要点）
  - 新增能力清单（service 方法 / API endpoint / ORM model / migration）
-->

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/db/models/<new_model>.py` | [一句话] |
| `alembic/versions/<id>_<slug>.py` | [一句话] |
| `tests/unit/test_<new>.py` | [一句话] |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/<svc>.py`](../../../src/services/<svc>.py) | [bullet 简述] |
| [`src/api/routers/<rt>.py`](../../../src/api/routers/<rt>.py) | [bullet 简述] |

### 3.3 新增能力

- **Service method**：`CustomerService.foo(self, customer_id: int, tenant_id: int) -> CustomerModel`
- **API endpoint**：`POST /customers/{id}/foo` → `{"success": true, "data": {...}}`
- **ORM model**：`<NewModel>` in `src/db/models/<file>.py`
- **Migration**：`alembic upgrade head` 创建 `<table>` 表（含 `tenant_id` 索引）

---

## 4. 设计决策与已知坑

<!--
  4 段（共 40-80 行）：
  - 关键技术选型（为什么 A 不 B）
  - 版本约束（仅当本板块引入新依赖时填）
  - 兼容性约束（不允许改的接口）
  - 已知坑（前期踩过 or 同类项目踩过的，每条要写"症状 + 规避"）
-->

### 4.1 关键选型

- **选 X 不选 Y**：[理由]

### 4.2 版本约束

<!-- 没有新依赖时整段删掉。如有，按下表填：-->

| 依赖 | 版本 | 理由 |
|------|------|------|
| `<pkg>` | `1.2.3` | [为什么这个版本] |

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（见 CLAUDE.md §Multi-Tenancy）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`
- [其他与本板块相关的兼容性要求]

### 4.4 已知坑

1. **[症状描述]** → 规避：[做法]
2. **[症状描述]** → 规避：[做法]

<!-- CRM 常见坑参考：
   - SQLAlchemy Base 子类的列名不能用 `metadata`（与 Base.metadata 冲突）→ 用 `event_metadata` / `payload` 等
   - Alembic autogen 会把 JSONB 写成 JSON、TIMESTAMPTZ 写成 DateTime → 手动改回
   - PYTHONPATH=src，import 写 `from db.models...` 而不是 `from src.db.models...`
   - Async session 不要用 `async with get_db()`，用 `Depends(get_db)`
-->

---

## 5. 实现步骤（按顺序）

<!--
  3-8 个 Step，每个 Step 20-50 行（共 100-250 行总）。
  每个 Step 标题必须以动词开头。
  每个 Step 末尾必须有"完成判定"（机器可验证）。
-->

### Step 1: [动词开头的短标题]

[2-4 行描述这一步做什么、为什么]

操作：
- a) [具体动作 1]
- b) [具体动作 2]

示例代码（如有）：

```python
# 新代码 snippet（≤15 行；超长拆 Step）
class FooModel(Base):
    __tablename__ = "foo"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_foo.py -v` → `N passed` / 文件 `<path>` 存在 / `ruff check <path>` exit 0

### Step 2: ...

### Step 3: ...

<!-- 3-8 个 step 都按上面格式 -->

---

## 6. 验收

<!--
  4-6 条（共 20-40 行）。
  全部机器可验证。
  禁止"手动检查"。
-->

- [ ] `ruff check src/<changed-files>` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_<x>.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_<x>_integration.py -v` → 全 passed（如涉及 DB）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如涉及 migration）
- [ ] 端到端：`curl -X POST http://localhost:8000/<endpoint>` 返回 `{...}`（如涉及 router）

---

## 7. 风险与回退

<!--
  2-4 条风险（共 20-40 行）。
  每条：风险 + 概率 + 影响 + 降级方案。
  降级方案必须不阻塞下游板块。
-->

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| [风险 1] | 中 | 高 | [feature flag 回退 / revert migration] |
| [风险 2] | 低 | 中 | [手动 fallback 步骤] |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add <changed-files>
git commit -m "feat(<scope>): <一句话改动>"  # 或 fix / docs / refactor
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "..." --body "Closes #{n}"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

<!-- 本仓库没有 Slack 通知、没有「周次」phase plan、没有 script/testnet 部署脚本。
     不要往 §8 加这些内容。 -->

---

## 9. 参考

<!--
  参考的具体形式（按需选）：
  - 同类已有实现（本仓库内）
  - 第三方文档：仅当确实需要时
  - 父 issue / 关联 issue
  Do NOT 编造 https://github.com/.../issues/N 这种占位 URL。
-->

- 同类参考实现：[`相对路径`](../../../相对路径)
- 第三方文档：[名称](https://...)
- 父 issue / 关联：#{n}

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
