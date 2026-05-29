# Dev-Plan · 文档中心

> **版本**：v0.1（自动生成 + 人工补全）
> **目标读者**：(1) 接手开发的人类工程师；(2) 拿到本文档直接写代码的 AI Agent
> **来源**：每个开放状态的 GitHub Issue（ready / blocked / 未triaged），由 `scripts/ci/validate_open_issues.py` 在 monitor-issues 流水线里自动产出对应板块文档
> **存放**：`docs/dev-plan/<category>/<NNNN>-<slug>.md`
> **分类**：见 §1.2 「分类总览」。`generate_dev_plan_board.py` 在落盘前先调用 Claude 做一次轻量分类

---

## 0. 怎么用这套文档（30 秒上手）

```
1. 读本 README §2 全局约束 → 这是宪法，所有板块都遵守
2. 打开对应板块文档（issues/N-slug.md） → 顺 8 段（中模板）或 10+ 段（深模板）执行
3. 验收：板块文档 §6「验证」全绿后 commit
4. 不确定的设计决策 → 回本 README §3「横切关注点」查；查不到 → 在 issue 上提问，不要擅自定
```

**核心原则**：每份板块文档**独立可执行**，不依赖隔壁板块文档的上下文；上下游依赖在文档顶部「元数据」声明。

---

## 1. 总览

### 1.1 文档列表（按分类）

| 分类 | 板块文档 | 模板深度 | 状态 |
|------|---------|---------|--------|
| 自动维护 | _以下条目由 validate_open_issues.py 在写入板块文档时自动追加_ | - | - |

<!-- AUTO-INDEX:START -->
<!-- AUTO-INDEX:END -->

### 1.2 分类总览

每份板块文档落在唯一的分类目录下。分类码（如 `20-sales`）作为目录名，前缀数字决定排序。

| 分类码 | 中文说明 | 涵盖范围（关键词） |
|---|---|---|
| `00-foundations` | 基础设施 | 数据库连接 / 认证 / 中间件 / Alembic 迁移 / `db.base` / `models.response` |
| `10-customers` | 客户管理 | CustomerModel / 联系人 / 分群 / 客户标签 / CRM 主体对象 |
| `20-sales` | 销售流程 | Opportunity / Pipeline / Stage / Kanban 后端 / Deal / Sales Activity |
| `30-tickets` | 工单支持 | Ticket / SLA / Escalation / 客服会话 |
| `40-campaigns` | 营销活动 | Campaign / Notification / Email/SMS 触达 / 模板 |
| `50-automation` | 自动化 | AutomationRule / 触发器 / 执行引擎 / 规则评估 / 工作流 |
| `60-analytics` | 数据分析 | ChurnPrediction / RFM / Report / BI / 预测模型 / KPI 仪表盘 |
| `70-platform` | 平台能力 | Import / Export / RBAC / User / Settings / Audit Log |
| `90-frontend` | 前端 / Web UI | Vue/React 组件 / 拖拽 / 路由 / 状态管理 / 切片浏览器 |
| `99-misc` | 兜底 | 暂无明确分类 / 需要二次人工归档（自动分类失败时默认进入这里） |

> 添加新分类前先评估能否归到上述任一类目；只有当你能给出 ≥ 3 个无法落入现有分类的真实例子时再扩。

---

## 2. 全局约束（宪法）

每份板块文档无条件遵守。冲突项以本节为准。

1. **每份板块独立可执行**：模板 §1-§8（或深模板的 §1-§10）按顺序填完即可由另一名工程师/Agent 接手实施，无需当面交接。
2. **元数据表必填**：周次、优先级、工作量、依赖、启用后赋能、状态 6 项缺一不可。`依赖` 与 `启用后赋能` 必须互引（双向声明）。
3. **路径必须真实**：所有 `path/to/file` 形式的引用，要么是当前仓库存在的文件，要么是「§3 涉及文件清单」中标注为「要建」的产物。其他全部禁止。
4. **§2「当前现状」必须给行号**：引用代码时使用 ``[`path`](../../path) L{start}-L{end}`` 形式，加 5-15 行关键代码片段。无现状的新建板块在 §2.1 写「N/A — 新建模块」。
5. **§5「实施步骤」必须可机器执行**：每一步是 shell 命令、代码 diff、或具体到「在 `foo.py` 第 N 行后插入 X」的指令。禁止「优化 foo 模块」这种含糊措辞。
6. **§6「验证」必须给具体命令 + 期望输出**：`pytest tests/unit/test_x.py -v` → 「`5 passed`」是合格；「跑测试看是否通过」是不合格。
7. **§7「测试用例」给出至少 3 条**：成功路径 1 条 + 边界 1 条 + 错误路径 1 条，每条点明用什么 fixture、断言什么。
8. **不在范围必须显式列出**（§1.3）：避免 scope creep。后续需求另开 issue + 另开板块。
9. **关键 KPI 数字化**（§1.4）：「用户体验更好」不算 KPI；「P95 延迟 < 200ms」算。
10. **板块不应跨越前后端 + DB 全栈**：跨栈拆分为多个板块，深模板专用于必须全栈一致的场景（如新增一条 schema → 模型 → 服务 → 路由 → 前端 → 测试 的完整通路）。
11. **`<!-- 注释 -->` 必须删干净**：模板里所有 `<!-- ... -->` 在最终文档中一个都不剩。
12. **状态字段单选**：`📋 待开始` / `🚧 进行中` / `✅ 已完成` / `⏸️ 阻塞中` / `❌ 已取消`。
13. **不允许 TODO 留白**：写不出来就写「TBD - 待补充：<具体什么内容>」并提 issue，禁止悄悄留 `TODO` 字面量。

---

## 3. 横切关注点（所有板块共用规则）

下列规则不写在每份板块里 — 来本节查。

### 3.1 多租户

- 所有 SQL 查询必须 `WHERE tenant_id = :tenant_id`。详见根目录 `CLAUDE.md` §「Multi-Tenancy」。
- 跨租户访问需要走 `RBAC` 服务并显式记录。

### 3.2 异步 + 数据库

- 使用 `postgresql+asyncpg`，所有 DB 操作 `async/await`。
- 服务返回 ORM/dataclass，**不**调用 `.to_dict()`；序列化由 router 负责。
- 服务抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`。

### 3.3 测试

- 单元测试：`tests/unit/test_*.py`，mock DB，<5s 内完成。
- 集成测试：`tests/integration/test_*_integration.py`，真实 Postgres（docker compose）。
- 每个测试文件自管 `mock_db_session` fixture（见根目录 `CLAUDE.md` §「Unit Test SQL Mocks」）。

### 3.4 Lint / 格式

- 仅 `ruff`（不要 flake8 / pylint / black）。
- `ruff check src/ && ruff format --check src/` 必须全绿。

### 3.5 Alembic 迁移

- 任何新 ORM 模型必须在 `alembic/env.py` 中 import。
- 用 `alembic_dev` 数据库做 `--autogenerate`，**不要**在 `test_db` 上跑（详见根目录 CLAUDE.md §「Alembic Migrations」）。
- 迁移必须可逆 — `downgrade()` 不可留空。

---

## 4. 验证

```bash
bash docs/dev-plan/_verify-links.sh
```

校验所有板块文档之间的互引 + 外部 URL 可达。`script/...` 这种「规划目标路径」**不**校验（每个板块的 §3 文件清单即产物清单）。

---

## 5. 维护

- **自动产出**：`monitor-issues.yml` 每次跑都会为新 `ready` issue 生成板块文档。
- **手工补全**：自动产出的文档是骨架，§2「当前现状」的代码片段、§4「设计与决策」的取舍、§7「测试用例」的细节通常需要工程师补充。
- **更新索引**：写入板块文档时自动维护 §1 表格的「AUTO-INDEX」区块。

---

## 6. 模板

- 中模板（默认）：[`_template-medium.md`](_template-medium.md) — 200-350 行，8 段
- 深模板（跨栈/架构级）：[`_template-deep.md`](_template-deep.md) — 400-600 行，10+ 段

模板深度由 issue 的预估工作量决定：
- ≤ 30 分钟：直接 `ready`，不出板块文档（PR 描述即足够）
- 30 min - 1 工作日：中模板
- > 1 工作日 + 跨栈：深模板（这些通常会被验证器标 `too_large` → 拆分）
