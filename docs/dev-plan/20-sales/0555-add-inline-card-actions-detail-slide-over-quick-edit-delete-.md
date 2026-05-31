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
