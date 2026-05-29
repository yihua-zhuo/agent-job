# 555 · Add inline card actions: detail slide-over, quick edit, delete, assign

| 元数据 | 值 |
|---|---|
| Issue | #555 |
| 分类 | 20-sales |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0544-快速筛选与批量操作工具栏](0544-快速筛选与批量操作工具栏.md) |
| 启用后赋能 | [0540-仪表盘销售漏斗与阶段统计](0540-仪表盘销售漏斗与阶段统计.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 opportunities 列表仅支持静态卡片展示，用户无法在卡片层直接查看完整字段、修改核心数据、删除商机或重新分配负责人。每次编辑都需要跳转到详情页，割裂了工作流，增加了操作成本。销售团队高频使用批量操作工具栏（#554），与之配套的卡片级快捷操作是完整交互体验的最后缺口。

### 1.2 做完后

- **用户视角**：点击卡片任意区域弹出详情侧边栏（slide-over），显示所有 opportunity 字段；stage / value / close_date 三字段支持点击即编辑；卡片提供删除按钮（附确认对话框）和 assign 下拉菜单（选择团队成员）。所有操作均在卡片层完成，无需跳转页面。
- **开发者视角**：新增 `OpportunityService.patch_opportunity` 方法支持部分字段更新；新增 `/opportunities/{id}` GET 端点返回完整 opportunity 数据；新增 `/opportunities/{id}/assign` POST 端点；前端新增 `OpportunitySlideOver`、`InlineEditField`、`AssignDropdown` 组件。

### 1.3 不做什么（剔除）

- [ ] 不在本板块实现商机创建流程（创建入口已在其他板块覆盖）
- [ ] 不实现批量删除或批量 assign（属 #554 工具栏范畴）
- [ ] 不改动 opportunity 数据模型 schema（如需 schema 变更，须走独立 migration 板块）
- [ ] slide-over 不实现全字段编辑表单（仅 stage / value / close_date 支持内联编辑，其余字段为只读展示）

### 1.4 关键 KPI

- `PYTHONPATH=src pytest tests/unit/test_opportunity_service.py -v` → 全 passed
- `ruff check src/services/opportunity_service.py src/api/routers/opportunity.py` → 0 errors
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如 Step 2 涉及 migration）
- 前端单元测试：`src/frontend/components/opportunity/__tests__/` → 全 passed

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/opportunity_service.py` — 现有 `OpportunityService` 类的 `get_opportunity` / `list_opportunities` 方法；卡片渲染入口在 `src/frontend/components/opportunity/Card.tsx` 或类似路径；#554 已实现工具栏筛选。

TBD - 待验证：`src/api/routers/opportunity.py` — 现有 GET `/opportunities/{id}` 返回哪些字段；PATCH `/opportunities/{id}` 是否已支持部分字段更新。

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/services/opportunity_service.py` — 新增 `patch_opportunity` 和 `assign_opportunity` 方法
  - TBD - 待验证：`src/api/routers/opportunity.py` — 新增 PATCH `/opportunities/{id}/fields` 和 POST `/opportunities/{id}/assign` 端点
  - TBD - 待验证：`src/frontend/components/opportunity/Card.tsx` — 绑定 click handler、显示内联编辑态
- 要建：
  - TBD - 待验证：`src/frontend/components/opportunity/OpportunitySlideOver.tsx` — 详情侧边栏组件
  - TBD - 待验证：`src/frontend/components/opportunity/InlineEditField.tsx` — stage / value / close_date 内联编辑组件
  - TBD - 待验证：`src/frontend/components/opportunity/AssignDropdown.tsx` — assign 下拉菜单组件
  - TBD - 待验证：`tests/unit/test_opportunity_service.py` — 新方法单元测试
  - TBD - 待验证：`alembic/versions/<id>_add_opportunity_assignee.sql` — 如需新增 assignee 列（若 schema 中尚无此字段）

### 2.3 缺什么

- [ ] OpportunityService 缺少 `patch_opportunity(tenant_id, opportunity_id, fields: dict)` 部分字段更新方法
- [ ] `/opportunities/{id}` GET 端点未返回所有 opportunity 字段（详情 slide-over 需要完整数据）
- [ ] `/opportunities/{id}/assign` POST 端点不存在（assign 操作无对应 API）
- [ ] 前端无 detail slide-over 组件（用户无法在卡片层展开完整视图）
- [ ] 前端无 inline-edit 交互（stage / value / close_date 三字段无法原地编辑）
- [ ] 前端无商机删除确认对话框（现有删除入口缺失或未闭环）
- [ ] 前端无 assign-to-team-member 下拉菜单

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/frontend/components/opportunity/OpportunitySlideOver.tsx` | 商机详情侧边栏，含只读字段展示 + 删除/assign 操作入口 |
| `src/frontend/components/opportunity/InlineEditField.tsx` | stage / value / close_date 三字段的 click-to-edit 交互封装 |
| `src/frontend/components/opportunity/AssignDropdown.tsx` | assign-to-team-member 下拉菜单，调用 POST `/opportunities/{id}/assign` |
| `src/frontend/components/opportunity/__tests__/OpportunitySlideOver.test.tsx` | slide-over 组件测试 |
| `tests/unit/test_opportunity_service.py` | patch_opportunity + assign_opportunity 单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| `src/services/opportunity_service.py` | 新增 `patch_opportunity(session, tenant_id, opp_id, fields)` 和 `assign_opportunity(session, tenant_id, opp_id, user_id)` 方法 |
| `src/api/routers/opportunity.py` | 新增 PATCH `/opportunities/{id}` 部分更新端点；新增 POST `/opportunities/{id}/assign` 端点 |
| `src/frontend/components/opportunity/Card.tsx` | 绑定 click 打开 slide-over；渲染 InlineEditField（stage / value / close_date）；渲染删除按钮和 AssignDropdown |

### 3.3 新增能力

- **Service method**：`OpportunityService.patch_opportunity(self, tenant_id: int, opportunity_id: int, fields: dict) -> OpportunityModel`
- **Service method**：`OpportunityService.assign_opportunity(self, tenant_id: int, opportunity_id: int, user_id: int) -> OpportunityModel`
- **API endpoint**：`PATCH /opportunities/{id}` → `{"success": true, "data": {...}}`（部分字段更新）
- **API endpoint**：`POST /opportunities/{id}/assign` body `{"user_id": int}` → `{"success": true, "data": {...}}`
- **API endpoint**：`GET /opportunities/{id}` → `{"success": true, "data": {...}}`（补全所有 opportunity 字段返回）
- **ORM model**：`OpportunityModel`（如 `assigned_to` / `assignee_id` 列缺失则新增 migration）

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **slide-over 用 conditional render 而非路由** — 避免 URL 变更和 history 栈膨胀；与现有列表页交互一致
- **内联编辑用 optimistic update + rollback** — 用户点击确认后立即更新 UI，API 失败时回滚并提示；避免等待网络的 lag
- **删除操作用确认对话框而非危险按钮直接删除** — 防止误触，符合 CRM 数据安全要求
- **assign 下拉只展示当前 tenant 下的 active 用户** — 多租户隔离，API 层按 tenant_id 过滤

### 4.2 版本约束

无新外部依赖引入。

### 4.3 兼容性约束

- 多租户：所有 service 方法和 API 端点均以 `tenant_id` 过滤数据
- Service 返回 `OpportunityModel` ORM 对象，不调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类，不返回 `ApiResponse.error()`
- 前端 API 调用使用 `tenant_id` 从当前 session/context 获取，不硬编码
- 新增 API 端点遵守现有 response envelope 格式：`{"success": true, "data": {...}}`

### 4.4 已知坑

1. **Alembic autogen 把 JSONB 写成 JSON、把 TIMESTAMPTZ 写成 DateTime** → 规避：若涉及新 migration，手动将 `sa.JSON()` 改为 `sa.JSONB()`，将 `DateTime` 改为 `DateTime(timezone=True)`
2. **SQLAlchemy Base 子类列名不可用 `metadata`**（与 `Base.metadata` 冲突）→ 规避：新模型中若需存储元数据，使用 `event_metadata`、`payload` 或 `attrs` 列名
3. **PYTHONPATH=src，前端引用后端模块时 import 路径必须以 `from db.models...` 开头** → 规避：确认所有 service/router import 符合此规范，不写 `from src.db.models...`

---

## 5. 实现步骤（按顺序）

### Step 1: 审计 opportunity_service.py 和 opportunity router，补充 patch + assign 端点

在 `OpportunityService` 中新增 `patch_opportunity` 和 `assign_opportunity` 两个方法：

```python
# src/services/opportunity_service.py
async def patch_opportunity(
    self, tenant_id: int, opportunity_id: int, fields: dict
) -> OpportunityModel:
    result = await self.session.execute(
        select(OpportunityModel).where(
            OpportunityModel.id == opportunity_id,
            OpportunityModel.tenant_id == tenant_id,
        )
    )
    opp = result.scalar_one_or_none()
    if opp is None:
        raise NotFoundException("Opportunity")
    for key, value in fields.items():
        if hasattr(opp, key):
            setattr(opp, key, value)
    await self.session.flush()
    return opp

async def assign_opportunity(
    self, tenant_id: int, opportunity_id: int, user_id: int
) -> OpportunityModel:
    result = await self.session.execute(
        select(OpportunityModel).where(
            OpportunityModel.id == opportunity_id,
            OpportunityModel.tenant_id == tenant_id,
        )
    )
    opp = result.scalar_one_or_none()
    if opp is None:
        raise NotFoundException("Opportunity")
    opp.assigned_to = user_id  # 或 assigned_user_id，看现有 schema
    await self.session.flush()
    return opp
```

在 `opportunity.py` router 中补充：

```python
@router.patch("/{opportunity_id}")
async def patch_opportunity(
    opportunity_id: int,
    fields: dict,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = OpportunityService(session)
    opp = await svc.patch_opportunity(ctx.tenant_id, opportunity_id, fields)
    return {"success": True, "data": opp.to_dict()}

@router.post("/{opportunity_id}/assign")
async def assign_opportunity(
    opportunity_id: int,
    body: dict,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    svc = OpportunityService(session)
    opp = await svc.assign_opportunity(ctx.tenant_id, opportunity_id, body["user_id"])
    return {"success": True, "data": opp.to_dict()}
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity_service.py -v` → 全 passed / `ruff check src/services/opportunity_service.py src/api/routers/opportunity.py` → 0 errors

---

### Step 2: 确认或新增 assignee 列 migration（如需要）

检查 `OpportunityModel` 是否已有 `assigned_to` / `assignee_id` 列：

```bash
grep -n "assigned" src/db/models/opportunity.py
```

若列不存在，生成 migration：

```bash
export PYTHONPATH=src
export DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5432/alembic_dev"
alembic revision --autogenerate -m "add_assigned_to_to_opportunity"
```

生成后手动检查并修正 alembic 自动生成的 `opportunity.assigned_to` 列类型：JSON/TIMESTAMPTZ 问题按 §4.4 修正。

**完成判定**：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0 / `ruff check alembic/versions/` → 0 errors

---

### Step 3: 补充 GET /opportunities/{id} 返回所有字段

检查现有 GET 端点是否已返回所有 opportunity 字段（stage / value / close_date / assigned_to 等）。若缺失字段，在 router return 处补充完整 `opp.to_dict()` 的完整字段映射。

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_opportunity_service.py -v` → 全 passed

---

### Step 4: 新增 OpportunitySlideOver 详情侧边栏组件

在 `src/frontend/components/opportunity/` 下新建 `OpportunitySlideOver.tsx`：

- 接收 `opportunityId: number` prop，打开时 GET `/opportunities/{id}` 获取完整数据
- slide-over 从右侧滑入（固定宽度 480px），点击遮罩或关闭按钮关闭
- 只读展示所有字段；顶部显示操作按钮（删除、assign）
- 删除按钮触发确认对话框（见 Step 5）

```tsx
// 结构示例（≤15 行）
interface Props {
  opportunityId: number;
  onClose: () => void;
  onDeleted: () => void;
}
export function OpportunitySlideOver({ opportunityId, onClose, onDeleted }: Props) {
  const [opp, setOpp] = useState<Opportunity | null>(null);
  useEffect(() => {
    api.get(`/opportunities/${opportunityId}`).then(r => setOpp(r.data));
  }, [opportunityId]);
  return (
    <div className="slide-over-backdrop" onClick={onClose}>
      <div className="slide-over-panel" onClick={e => e.stopPropagation()}>
        {/* 操作按钮区：删除 / assign */}
        {/* 字段展示区 */}
      </div>
    </div>
  );
}
```

**完成判定**：`src/frontend/components/opportunity/__tests__/OpportunitySlideOver.test.tsx` 存在且全 passed / `npm run test -- --testPathPattern=OpportunitySlideOver` → 全 passed

---

### Step 5: 新增 InlineEditField 组件（stage / value / close_date）

新建 `InlineEditField.tsx`，支持两种模式：展示态（显示文本 + 编辑图标）和编辑态（input/select，点击外部自动保存）：

- `stage`：Select 下拉（对应 opportunity stage 枚举值）
- `value`：Number input（支持千分位格式化显示）
- `close_date`：Date picker input

每个字段编辑成功后调用 `PATCH /opportunities/{id}` 提交变更，失败时 rollback 并 toast 提示。

**完成判定**：`npm run test -- --testPathPattern=InlineEditField` → 全 passed

---

### Step 6: 新增 AssignDropdown 组件

新建 `AssignDropdown.tsx`：

- 点击触发下拉菜单，GET `/users?tenant_id={tenantId}&active=true` 加载当前租户下的用户列表
- 选择用户后 POST `/opportunities/{id}/assign` body `{"user_id": userId}`
- 更新成功后刷新卡片展示的 assignee 信息

**完成判定**：`npm run test -- --testPathPattern=AssignDropdown` → 全 passed

---

### Step 7: 集成到 Card 组件并实现删除确认对话框

在 `Card.tsx` 中：

- 点击卡片（非操作按钮区域）调用 `onOpenSlideOver(opportunity.id)` 打开 slide-over
- 在 slide-over 中渲染 `InlineEditField`（stage / value / close_date 三字段，替换原有的静态展示）
- 删除按钮触发 `window.confirm()` 或自定义确认对话框，确认后 DELETE `/opportunities/{id}`，成功后调用 `onDeleted` 回调刷新列表
- 删除成功后 slide-over 自动关闭

**完成判定**：`npm run test -- --testPathPattern=opportunity/Card` → 全 passed / 端到端手动验证卡片点击 → slide-over 展开 → 三字段可内联编辑 → assign 可选人 → 删除弹确认框 → 确认后卡片消失

---

## 6. 验收

- [ ] `ruff check src/services/opportunity_service.py src/api/routers/opportunity.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_opportunity_service.py -v` → 全 passed
- [ ] `npm run test -- --testPathPattern=opportunity` → 全 passed（如有前端测试配置）
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如 Step 2 触发了 migration 文件）
- [ ] 端到端（手动）：点击卡片 → slide-over 展开 → 三字段可内联编辑 → assign 下拉可选人 → 删除弹确认框 → 确认后卡片从列表消失

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| assign 列 migration 与现有 opportunity 表结构不兼容（生产已有人工改动） | 低 | 中 | Step 2 生成的 migration 由 DBA review 后再合入；使用 `--dry-run` 预检；降级方案为 `alembic downgrade` 回退该列 |
| inline edit PATCH 并发冲突（两用户同时编辑同一字段） | 低 | 低 | 后端以 last-write-wins 处理；前端无锁机制；在 slide-over 标题区显示 "最后编辑于 X 时间" 提示用户 |
| slide-over 与工具栏（#554）交互冲突（点击工具栏操作时 slide-over 未关闭） | 中 | 中 | Card 组件顶层监听工具栏 activate 事件，收到时强制 `onClose()`；#554 工具栏实现须 emit 该事件 |
| PATCH 端点破坏现有 opportunity 创建流程（字段过滤不全） | 低 | 高 | 仅允许 `stage`、`value`、`close_date`、`assigned_to` 四个字段，其余字段静默忽略；测试覆盖非法字段注入 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/opportunity_service.py src/api/routers/opportunity.py \
        src/frontend/components/opportunity/ \
        tests/unit/test_opportunity_service.py \
        alembic/versions/
git commit -m "feat(opportunity): add inline card actions — detail slide-over, quick edit, assign, delete"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(opportunity): inline card actions (#555)" --body "Closes #555"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证 — `src/frontend/components/ticket/Card.tsx`（#544 工具栏关联的卡片组件，可参考其工具栏激活事件监听机制）
- 父 issue：#54
- 依赖板块：#554

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
