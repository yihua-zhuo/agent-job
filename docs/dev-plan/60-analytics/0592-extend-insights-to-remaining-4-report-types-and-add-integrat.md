# Analytics Insights 扩展至其余 4 种报表 & 新增集成测试

| 元数据 | 值 |
|---|---|
| Issue | #592 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [Analytics Insights 基础实现](待补充-依赖594) |
| 启用后赋能 | [Analytics完整看板](../00-foundations/00-overview.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #592 的父 issue #48 定义了统一的 Analytics Insights 层。当前已有 `analytics_service.py` 实现了 trend + anomaly + recommendation 逻辑（代码位置待验证），但仅覆盖3 种报表类型。剩余 4 种——`pipeline_forecast`、`customer_activity`、`team_performance`、`ticket_sla`——仍然缺失这些能力，导致系统无法对全量报表类型提供一致的洞察输出。集成测试也全部缺失，无法验证 response shape、缓存机制和中文摘要的端到端正确性。

### 1.2 做完后

- **用户视角**：无直接用户可见变化——本板块是底层 analytics service 增强。
- **开发者视角**：`AnalyticsService` 获得了对 4 种新报表类型的 `get_trends`、`generate_anomaly_alert`、`get_recommendation` 方法支持，可通过 `db_schema` fixture 端到端验证；新增的集成测试覆盖所有 7 种报表类型，任何 regression都会被 CI 捕获。

### 1.3 不做什么（剔除）

- [ ] 不新增数据库表或 schema变更——本板块是 service/logic 扩展- [ ] 不新增 router/endpoint——仅扩展 `analytics_service.py`内部逻辑
- [ ] 不新增用户面向的 UI 或 dashboard改动
- [ ] 不实现 `pipeline_forecast`、`customer_activity`、`team_performance`、`ticket_sla` 各自的底层数据查询（仅在已有 query基础上包装 trend/anomaly/recommendation）

### 1.4 关键 KPI

- [ ] `pytest tests/integration/test_analytics_insights_integration.py -v` → ≥ 12 passed（含 pipeline_forecast × 3、customer_activity × 3、team_performance × 3、ticket_sla × 3 assertions）
- [ ] `ruff check src/services/analytics_service.py` → 0 errors
- [ ] `ruff check tests/integration/test_analytics_insights_integration.py` → 0 errors
- [ ] 7 种报表类型（含已有3 种）全部返回 `summary`字段内容为非空中文字符串，集成测试 assertion 通过

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/services/analytics_service.py` — 需要确认现有 trend + anomaly + recommendation 方法签名和 report type 枚举，支持的3 种已有报表类型名称（疑似 pipeline / opportunity / customer 三选一，需 grep），以及是否已有 `pipeline_forecast`、`customer_activity`、`team_performance`、`ticket_sla` 的 stubs。

现有集成测试：TBD - 待验证：`tests/integration/test_analytics_insights_integration.py` 是否已存在——如果不存在则整个文件属于"要建"范围。

### 2.2 涉及文件清单

- 要改：
  - `src/services/analytics_service.py` —扩展 trend/anomaly/recommendation 方法至4 种新 report type
- 要建：
  - `tests/integration/test_analytics_insights_integration.py` —覆盖 4 种新报表类型的端到端测试（含 response shape / caching / Chinese summary assertion）

### 2.3 缺什么

- [ ] `analytics_service.py` 缺失对 `pipeline_forecast` 的 trend/anomaly/recommendation 逻辑- [ ] `analytics_service.py` 缺失对 `customer_activity` 的 trend/anomaly/recommendation 逻辑
- [ ] `analytics_service.py` 缺失对 `team_performance` 的 trend/anomaly/recommendation 逻辑
- [ ] `analytics_service.py` 缺失对 `ticket_sla` 的 trend/anomaly/recommendation 逻辑
- [ ] 全套集成测试缺失（4 × 3 assertions: response shape / caching / Chinese summary）
- [ ] CI 无法检测新报表类型 trend/anomaly/recommendation 的 regression

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/integration/test_analytics_insights_integration.py` |覆盖 4 种新报表类型的集成测试（response shape / caching / Chinese summary） |

### 3.2 修改文件

|路径 | 改动要点 |
|------|---------|
| [`src/services/analytics_service.py`](../../src/services/analytics_service.py) | 为 `pipeline_forecast`、`customer_activity`、`team_performance`、`ticket_sla` 实现 get_trends / generate_anomaly_alert / get_recommendation 方法；确保7 种类型（含已有）均返回中文 summary |

### 3.3 新增能力

- **Service method**：`AnalyticsService.get_trends(report_type: str, tenant_id: int, **kwargs) -> dict` —扩展支持7 种 report type
- **Service method**：`AnalyticsService.generate_anomaly_alert(report_type: str, tenant_id: int, **kwargs) -> dict | None`
- **Service method**：`AnalyticsService.get_recommendation(report_type: str, tenant_id: int, **kwargs) -> list[dict]`
- **Integration test**：`test_analytics_insights_integration.py` —4 ×3 assertions per report type

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **复用已有抽象模式，不重新发明**：`analytics_service.py` 已有的 3 种报表实现是高保真模板——直接复制同一模式（相同方法签名、相同的 helper 结构）到 4 种新类型，保持代码风格一致。
- **集成测试优先 fixture**：`db_schema` fixture 管理表创建/销毁，确保测试完全隔离——不依赖外部 ordering 或手动 setup。
- **中文 summary 生成**：使用 jinja2 template 或 dict lookup方案；key 为 `trend_title`、`anomaly_desc`、`recommendation_text`；每个 report type 的中文文案预定义在 `analytics_service.py` 常量字典中。

### 4.2 版本约束

N/A — 本板块未引入新的 pip依赖。

### 4.3 兼容性约束

- 多租户：所有 analytics query 必须 `WHERE tenant_id = :tenant_id`
- Service 返回 dict/dataclass 对象，**不**调用 `.to_dict()`；序列化由调用方/router 负责
- Service错误抛 `AppException` 子类，**不**返回 `{"success": false}`字典
- 已有 3 种报表的行为不得 regress——新代码仅做 extension 而非 modification of existing branch paths

### 4.4 已知坑

1. **Alembic autogen 会把 `JSONB`误写为 `sa.JSON()`** → 本板块无新迁移，不受影响；但如果后续需要添加 `analytics_cache` 表，手动将 `sa.JSON()` 改回 `sa.JSONB()`。
2. **中文 summary 依赖 hardcoded string dict** →避免日后 locale膨胀；若已有 template引擎，则继续使用同一模板引擎而非散列字典。
3. **缓存 assertion 需要真实的缓存层** → TBD - 待验证 `analytics_service.py` 是否已集成 Redis / in-memory LRU cache；如果 cache 层缺失，`pytest.raises(CacheMiss)` 类 assertion 会失败；先用 `mock` patch 绕过，待缓存层实现后再迁移到真实集成测试。
4. **report type枚举拼写必须与 DB query 层一致** → 使用与父 issue #591 协调一致的 constant字符串（不重新发明 enum），避免运行时 `KeyError`。

---

## 5. 实现步骤（按顺序）

### Step 1:确认已有 3 种报表的实现模式在 `analytics_service.py` 中 grep/clang，找出已有 trend / anomaly / recommendation 方法的签名、report type 常量定义、中文 summary 模板/字典。将结果记录到本板块 §2.1。

操作：
- a) 读取 [`src/services/analytics_service.py`](../../src/services/analytics_service.py)全文，确认已有 method 签名（`get_trends`、`generate_anvelope_alert`、`get_recommendation` 或类似）
- b) 确认 report type 常量名称（如 `PipelineType`, `REPORT_TYPES` dict 等）
- c) 确认中文 summary 的实现方式（jinja2 / hardcoded dict / i18n 函数）

**完成判定**：§2.1 现有实现段不再有 "TBD" 前缀；已记录具体 method name 和 report type 常量。

### Step 2: 扩展 analytics_service.py 支持 4 种新 report type

在 `analytics_service.py` 中为 `pipeline_forecast`、`customer_activity`、`team_performance`、`ticket_sla` 各实现 trend / anomaly / recommendation 分支。

操作：
- a) 在 report type 常量 dict 中添加 4 个新 key（report type string → handler function / method name mapping）
- b) 在 `get_trends()` 中添加 `if report_type == "pipeline_forecast": ...` 分支，复制已有报表 pattern- c)重复 b) 对 customer_activity、team_performance、ticket_sla
- d) 在 anomaly / recommendation methods 中重复 b-c
- e) 为每种新报表类型在中文字典中添加 `trend_title`、`anomaly_desc`、`recommendation_text` 字段，内容为自然中文（2-5 字）

示例代码（如有）：

```python
# analytics_service.py — 新增 report type 分支（≤15 行）
REPORT_TYPES = {
    "pipeline": _pipeline_trends,
    "opportunity": _opportunity_trends,
    "pipeline_forecast": _pipeline_forecast_trends,  # 新增
    "customer_activity": _customer_activity_trends,  # 新增
    "team_performance": _team_performance_trends,   # 新增
    "ticket_sla": _ticket_sla_trends,               # 新增
}

SUMMARY_TEMPLATES = {
    "pipeline_forecast": {
        "trend_title": "管线预测趋势正常",
        "anomaly_desc": "管线预测出现异常波动",
        "recommendation_text": "建议关注预测偏差超过20%的管线",
    },
    "customer_activity": {
        "trend_title": "客户活跃度趋势稳定",
        "anomaly_desc": "客户活跃度出现异常下降",
        "recommendation_text": "建议发起客户激活活动",
    },
    # ... team_performance / ticket_sla 同理
}
```

**完成判定**：`ruff check src/services/analytics_service.py` →0 errors

### Step 3: 编写集成测试文件框架

创建 `tests/integration/test_analytics_insights_integration.py`，使用 `db_schema` fixture。测试类按 report type 分组，每种类型3 个 assertion。

操作：
- a) `touch tests/integration/test_analytics_insights_integration.py`
- b)导入 `db_schema`、`tenant_id`、`async_session` fixtures 及 `AnalyticsService`
- c) 定义 `class TestPipelineForecastInsights`、`TestCustomerActivityInsights`、`TestTeamPerformanceInsights`、`TestTicketSlaInsights`
- d) 每个 class 内定义 `test_response_shape`、`test_caching`、`test_chinese_summary` 三个 async method

### Step 4: 实现 response shape assertion

在每个 report type 测试 class 中，用 `assert isinstance(result, dict)` 和关键 key existence 检查 assertion 响应结构。

操作：
- a) `async def test_response_shape(self, db_schema, tenant_id, async_session):` → `svc = AnalyticsService(async_session); result = await svc.get_trends("pipeline_forecast", tenant_id=tenant_id); assert "data" in result or result shape starts with correct keys`
- b) 对 anomaly + recommendation端点重复- c)复制到 customer_activity、team_performance、ticket_sla

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_analytics_insights_integration.py::TestPipelineForecastInsights::test_response_shape -v` → 1 passed

### Step 5: 实现 caching assertion

使用 `mock.patch` 或检查返回结果一致性来验证缓存行为（视缓存层实现情况决定使用哪种策略）。

操作：
- a) 如果已有 cache 集成：两次调用同一 report type，第二次 assertion 响应时间 < 第一次50%（或检查 cache key存在）
- b) 如果无 cache 层：使用 `mock.patch("src.services.analytics_service.get_cache")` patch缓存模块并 assert call count == 2（第二次 skip DB query）
- c) 四种 report type 各执行一次

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_analytics_insights_integration.py -k "test_caching" -v` → 4 passed

### Step 6: 实现 Chinese summary assertion

在 `test_chinese_summary` 中 assert `re.summary` / `result["summary"]` 为非空字符串且包含中文字符（`re.search(r"[\u4e00-\u9fff]", summary)`）。

操作：
- a) `def test_chinese_summary(self, db_schema, tenant_id, async_session):` → `result = await svc.get_trends("pipeline_forecast", tenant_id=tenant_id); import re; assert result["summary"] and re.search(r"[\u4e00-\u9fff]", result["summary"])` → 对 4 种 report type 各执行
- b) 对 anomaly + recommendation 方法重复

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_analytics_insights_integration.py -k "test_chinese_summary" -v` → 4 passed

### Step 7: 运行全量集成测试并确保全部通过

操作：
- a) `PYTHONPATH=src pytest tests/integration/test_analytics_insights_integration.py -v`
- b) 如果有 failure，分析 failure message，修复 `analytics_service.py` 对应分支
- c) 重复直到全部 passed

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_analytics_insights_integration.py -v` → ≥ 12 passed（在已有3 种报表测试之外）

---

## 6. 验收

- [ ] `ruff check src/services/analytics_service.py` → 0 errors
- [ ] `ruff check tests/integration/test_analytics_insights_integration.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v` → 全 passed（如存在 unit 测试）
- [ ] `PYTHONPATH=src pytest tests/integration/test_analytics_insights_integration.py -v` → ≥12 passed
- [ ] `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` → 三次 exit 0（如本板块涉及 migration；若无则标记 N/A）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 缓存机制与集成测试断言不兼容（cache layer 尚未实装）导致 CI 失败 | 中 | 中 | 使用 `mock.patch` 替代真实缓存断言；CI 改为 `-k "not test_caching"`暂时跳过；后续缓存层实现后移除 mock |
| 新增分支引入已有3 种报表类型的 regression（拼写错误 /逻辑短路） | 低 | 高 | 在 `analytics_service.py` 添加 "新增类型不应破坏已有类型" 的 unit test；任何 CI failure 先回滚 service file |
| 中文 summary hardcoded string dict 导致后续 i18n 膨胀 | 低 | 低 | 在 README 留存设计注记；后续 i18n 方案（pOTT）另行开 issue，不阻塞本板块 |
| 报告 type 常量拼写与 DB query 层不一致导致运行时 KeyError | 中 | 高 | Step 1 严格验证后，Step 2严格对齐；使用 constant 而非 string literal 避免 copy-paste 错误 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/analytics_service.py tests/integration/test_analytics_insights_integration.py
git commit -m "feat(analytics): extend insights to pipeline_forecast/customer_activity/team_performance/ticket_sla"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): extend insights to remaining 4 report types" --body "Closes #592"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证 `src/services/analytics_service.py` 中已有的 3 种报表 trend/anomaly/recommendation 实现（建议以第一号已有实现的 branch path 为准，避免后续新增类型引入不一致）
- 父 issue / 关联：#48（Analytics Insights完整层）, #591（依赖的基础 analytics 实现）
-第三方文档：[FastAPI — Testing](https://fastapi.tiangolo.com/tutorial/testing/), [SQLAlchemy 2.x async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
