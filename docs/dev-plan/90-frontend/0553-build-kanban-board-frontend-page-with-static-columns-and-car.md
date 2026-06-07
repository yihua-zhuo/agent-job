# src/frontend/components/sales/pipeline/card.pyx
def PipelineCard(props):
 value_str = format_currency(props.opportunity["value"])
    close_date = format_date(props.opportunity["expected_close_date"])
    avatar = props.opportunity["owner_avatar_url"] or initials(props.opportunity["owner_name"])

    return Box(
        className="pipeline-card",
        children=[
            Text(strong=True, children=props.opportunity["company"]),
            Text(children=value_str),
            Text(size="sm", children=f"📅 {close_date}"),
            Avatar(src=avatar, alt=props.opportunity["owner_name"]),
        ]
    )
```

**完成判定**：创建文件 `src/frontend/components/sales/pipeline/card.pyx`（或等效扩展名）存在，非空---

### Step 3: 创建列脚组件 `ColumnFooter`

在同目录下创建 `col_footer.pyx`：

- props：`count: int`, `total_value: float`
- 展示：`N 个机会 · $X,XXX,XXX 总计`
- 格式化：金额走 `format_currency`

```python
# src/frontend/components/sales/pipeline/col_footer.pyx
def ColumnFooter(props):
    return Box(
        className="col-footer",
        children=[
            Text(size="sm", children=f"{props.count} 个机会"),
            Text(strong=True, children=f"· {format_currency(props.total_value)} 总计"),
        ]
    )
```

**完成判定**：文件 `src/frontend/components/sales/pipeline/col_footer.pyx` 存在，非空

---

### Step 4: 创建管线列组件 `PipelineColumn`

在同目录下创建 `column.pyx`：

- props：`stage_name: str`, `color: str`, `opportunities: list`
- 布局：列头（含 stage_name + 色块标识）→ 卡片列表（Map over opportunities）→ 列脚（调用 ColumnFooter）
- 列脚传入：`count = len(opportunities)`, `total_value = sum(o.value for o in opportunities)`

```python
# src/frontend/components/sales/pipeline/column.pyx
def PipelineColumn(props):
    total = sum(o["value"] for o in props.opportunities)
    cards = [PipelineCard(opportunity=o) for o in props.opportunities]
    return Box(
        className=f"pipeline-col pipeline-col--{props.stage_key}",
        children=[
            Box(className="col-header", children=[
                Box(className="stage-badge", style={"background": props.color}),
                Text(strong=True, children=props.stage_name),
            ]),
            *cards,
            ColumnFooter(count=len(props.opportunities), total_value=total),
        ]
    )
```

**完成判定**：文件 `src/frontend/components/sales/pipeline/column.pyx` 存在，非空

---

### Step 5: 创建管线页面入口 `pipeline.pyx`

在 `#60` 指定的页面目录下创建 `pipeline.pyx`：

- 在 `useEffect`（或等效生命周期）内调用机会列表 API
- 将返回数据按 `stage` 字段分组到 dict（key: stage枚举值，value: opportunity list）
- 6 个列硬编码 stage config（Prospecting/Qualification/Proposal/Negotiation/Closed Won/Closed Lost，各配颜色）
- 渲染：外层横向滚动容器 > Flex row of `PipelineColumn` ×6

```python
# src/frontend/pages/pipeline.pyx
STAGES = [
    {"key": "prospecting",  "label": "Prospecting",  "color": "#3b82f6"},
    {"key": "qualification", "label": "Qualification", "color": "#8b5cf6"},
    {"key": "proposal",     "label": "Proposal",     "color": "#f59e0b"},
    {"key": "negotiation",  "label": "Negotiation",  "color": "#ec4899"},
    {"key": "closed_won",   "label": "Closed Won",   "color": "#10b981"},
    {"key": "closed_lost",  "label": "Closed Lost",  "color": "#6b7280"},
]

@pipeline_page("/sales/pipeline")
def PipelinePage():
    opportunities = use_fetch("/api/sales/opportunities")
    data_by_stage = group_by(opportunities, key=lambda o: o["stage"])

    return Box(
        className="pipeline-page",
        children=[
            Text(h1=True, children="销售管线"),
            Box(className="pipeline-board", children=[
                PipelineColumn(
                    stage_name=config["label"],
                    color=config["color"],
                    opportunities=data_by_stage.get(config["key"], []),
                )
                for config in STAGES
            ]),
        ]
    )
```

**完成判定**：文件 `src/frontend/pages/pipeline.pyx`（或等效）存在，非空

---

### Step 6: 在路由配置中注册 `/sales/pipeline`

在 `#60`指定的路由配置文件（如 `src/frontend/routes.py` 或 `src/main.py` 的前端路由部分）中添加：

```python
router.add_page("/sales/pipeline", PipelinePage, name="sales_pipeline")
```

**完成判定**：`ruff check src/frontend/routes.py` →0 errors（如文件存在），或对应路由注册语句存在于路由文件

---

### Step 7: 编写测试根据 #60 确认的测试框架，在 `tests/unit/test_pipeline_page.py` 中编写：

- `test_pipeline_card_renders_company` —传入 opportunity dict，断言卡片文本含公司名
- `test_pipeline_card_fallback_initials` — `owner_avatar_url=None`，断言渲染 initials 而非破图
- `test_pipeline_column_footer_totals` — 传入 `opportunities=[{"value": 100}, {"value": 200}]`，断言列脚显示 `2 个机会 · $300 总计`
- `test_pipeline_page_groups_by_stage` — mock API 返回，断言 data_by_stage 正确分组

```python
# tests/unit/test_pipeline_page.py
def test_pipeline_card_fallback_initials():
    opportunity = {"company": "ACME", "value": 50000,
 "expected_close_date": "2026-07-01",
                  "owner_avatar_url": None, "owner_name": "John Doe"}
    rendered = render(PipelineCard(opportunity=opportunity))
    assert "John Doe" in rendered.text
    assert "JD" in rendered.html # initials fallback

def test_pipeline_column_footer_totals():
    opps = [{"value": 100}, {"value": 200}]
    rendered = render(ColumnFooter(count=2, total_value=300))
    assert "2 个机会" in rendered.text
    assert "300" in rendered.text
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_pipeline_page.py -v` → 全部 passed

---

## 6. 验收

- [ ] `ruff check src/frontend/components/sales/pipeline/` →0 errors
- [ ] `ruff check src/frontend/pages/pipeline.pyx` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_pipeline_page.py -v` →全部 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_pipeline_page_integration.py -v` →全部 passed（如 #60 已搭建集成测试框架）
- [ ] 页面文件存在：`src/frontend/pages/pipeline.pyx`（或等效扩展名）
- [ ] 列组件存在：`src/frontend/components/sales/pipeline/column.pyx`
- [ ] 卡片组件存在：`src/frontend/components/sales/pipeline/card.pyx`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #60 未完成导致前端框架无法确定，阻塞本板块 | 中 | 高 | 先行完成 #60；本板块在其完成后第一个开始 |
| 机会 API 未提供 stage 分组字段（仅返回列表） | 低 | 中 | 前端侧按 stage key 进行 group_by，变更不在本板块范围，需 #552修复 |
| 金额极大（>1B）格式化溢出 | 低 | 低 |限制金额格式化为百万缩写（`$1.2M`）或保持原值 |
| 前端组件测试框架未与后端 pytest打通 | 低 | 中 | 测试文件使用框架内断言，本板块验收以文件存在为主，测试通过为辅 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/frontend/components/sales/pipeline/ src/frontend/pages/pipeline.pyx
git add tests/unit/test_pipeline_page.py
git commit -m "feat(pipeline): add sales Kanban board page with 6 static columns and opportunity cards"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#553): Sales pipeline Kanban board frontend page" --body "Closes #553\n\nDepends on #552 and #60."

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：`src/frontend/pages/` 下其他列表页面的路由配置写法（待 #60 确定后补路径）
- 父 issue / 关联：#54
- 依赖板块：#552（机会列表 API）、#60（前端框架与目录结构）
- 后续关联：#554（Kanban 拖拽排序）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
