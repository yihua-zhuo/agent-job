# AI 摘要生成 · 中文自然语言报告摘要

| 元数据 | 值 |
|---|---|
| Issue | #591 |
| 分类 | 60-analytics |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | [0627-add-llmservice-with-multi-provider-support.md](../62e7-add-llmservice-with-multi-provider-support.md) |
| 启用后赋能 | [0592-extend-insights-to-remaining-4-report-types-and-add-integrat.md](./0592-extend-insights-to-remaining-4-report-types-and-add-integrat.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 `AnalyticsService` 的聚合报表（`get_sales_revenue_report`、`get_pipeline_forecast` 等）只返回结构化的 JSON 数据（`labels`、`datasets`、`chart_type`），没有自然语言摘要能力。用户需要在报表结果旁看到一行中文执行摘要，以快速理解数据含义，而非自己解读图表。此外 #41 引入的 `AIChatGateway` 已在 `AIService` 中成功集成，本板块只需将其扩展到分析域。

### 1.2 做完后

- **用户视角**：调用 `AnalyticsService.run_report` 后，返回的 `dict` 中包含 `summary` 字段，值为中文自然语言摘要（≤2 句）。
- **开发者视角**：`AnalyticsService` 新增 `generate_chinese_summary(report_type: str, metrics: dict, tenant_id: int) -> str` 方法，底层调用 `AIChatGateway.chat()`；`AIChatGateway` 通过构造函数注入，支持单元测试 mock。

### 1.3 不做什么（剔除）

- [ ] 不实现新的 AI 模型接入或 provider 切换（本板块依赖 #41 提供的 `AIChatGateway` 框架）
- [ ] 不修改现有 report 模型 schema（`ReportModel`、`DashboardModel`）的数据库结构
- [ ] 不实现流式输出（streaming）

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v` → 全 passed]
- [指标 2：`ruff check src/services/analytics_service.py` → 0 errors]
- [指标 3：生成的摘要通过 `len(summary.split('。')) <= 3` 且全中文（无 ASCII 字母数字混合句子）]

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/analytics_service.py`](../../../src/services/analytics_service.py) L1-L157

```python
1:1:src/services/analytics_service.py
"""Analytics service — DB-backed dashboards & reports + aggregated query reports."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.analytics import DashboardModel, ReportModel
from db.models.customer import CustomerModel
from db.models.opportunity import OpportunityModel
from pkg.errors.app_exceptions import NotFoundException


class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session
```

`AIChatGateway` 已存在且可注入：[`src/internal/ai_gateway.py`](../../../src/internal/ai_gateway.py) L17-L35

```python
17:35:src/internal/ai_gateway.py
class AIChatGateway:
    """Async adapter for AI chat calls.
    The ``_call_gateway`` method is the only place that needs to change when
    swapping the stub for a real MiniMax-M2.7 integration — no call sites need updating.
    """
    async def chat(self, messages: list[dict[str, str]], context: dict[str, Any] | None = None) -> AIResponse:
        """Send a chat request to the AI gateway."""
        return await self._call_gateway(messages, context or {})
```

### 2.2 涉及文件清单

- 要改：
  - [`src/services/analytics_service.py`](../../../src/services/analytics_service.py) — 新增 `generate_chinese_summary` 方法，构造函数注入 `AIChatGateway`
  - [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) — 如需新增 mock handler 则扩展；否则各测试文件自建 fixture
- 要建：
  - `tests/unit/test_analytics_service.py` — 单元测试，mock `AIChatGateway`，断言摘要为中文且 ≤2 句

### 2.3 缺什么

- [ ] `AnalyticsService` 没有 `AIChatGateway` 依赖，无法生成 LLM 驱动的摘要
- [ ] `AnalyticsService.run_report` 返回的 `dict` 没有 `summary` 字段
- [ ] 没有 `AIChatGateway` 的 mock 注入方式，无法对 `generate_chinese_summary` 做单元测试
- [ ] 没有任何测试覆盖 `AnalyticsService` 的摘要生成路径（现有只有集成测试）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/test_analytics_service.py` | 单元测试：mock `AIChatGateway`，断言摘要为中文 ≤2 句 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/analytics_service.py`](../../../src/services/analytics_service.py) | 构造函数增加可选 `gateway: AIChatGateway` 参数；新增 `generate_chinese_summary` 方法调用 gateway；`run_report` 结果中注入 `summary` 字段 |

### 3.3 新增能力

- **Service method**：`AnalyticsService.generate_chinese_summary(report_type: str, metrics: dict, tenant_id: int) -> str` — 调用 `AIChatGateway.chat()` 返回中文摘要
- **字段注入**：`run_report` 返回的 `dict` 增加 `summary: str` 键

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **在 `AnalyticsService` 内部直接注入 `AIChatGateway`，不新建 `InsightsService`**
  - 理由：摘要生成是报表的附加能力，与 `run_report` 紧密耦合（同一 tenant、同一 session），新建 service 增加跨域调用成本；`AIChatGateway` 已支持通过构造函数注入。
- **gateway 参数可选（`gateway: AIChatGateway | None = None`）并内部 `or AIChatGateway()`**
  - 理由：向后兼容 — 已有代码直接 `AnalyticsService(session)` 不应崩溃；测试可显式传入 mock。

### 4.2 版本约束

无新增依赖（`AIChatGateway` 已由 #41 提供）。

### 4.3 兼容性约束

- 多租户：每个 SQL 查询必须 `WHERE tenant_id = :tenant_id`（已有，无需新增查询）
- Service 返回 ORM/dataclass 对象，**不**调用 `.to_dict()`；序列化由 router 负责
- Service 错误抛 `AppException` 子类（`NotFoundException` / `ValidationException` / `ForbiddenException` / `ConflictException`），**不**返回 `ApiResponse.error()`
- `AIChatGateway` 必须支持构造函数注入，以便单元测试 mock

### 4.4 已知坑

1. **AIChatGateway 的 stub 回复是英文** → 规避：单元测试中的 mock 应返回确定的中文文本（如 `"本月销售表现良好，交易额环比增长。"`），通过 `MagicMock` 直接赋值 `reply`，不依赖真实 gateway。
2. **摘要可能超过 2 句** → 规避：`generate_chinese_summary` 方法内部用 `summary.count('。') + summary.count('！') + summary.count('？') <= 2` 校验，若超则截取前两个句号之间的内容并追加 `…`。
3. **Alembic 不涉及** — 本板块不修改任何 ORM 模型表结构，无 migration 文件。

---

## 5. 实现步骤（按顺序）

### Step 1: 修改 `AnalyticsService` 构造函数，增加 `AIChatGateway` 注入

在 `src/services/analytics_service.py` 文件顶部添加 `from internal.ai_gateway import AIChatGateway` import，并将构造函数改为：

```python
from internal.ai_gateway import AIChatGateway

class AnalyticsService:
    def __init__(self, session: AsyncSession, gateway: AIChatGateway | None = None):
        self.session = session
        self.gateway = gateway or AIChatGateway()
```

**完成判定**：`PYTHONPATH=src ruff check src/services/analytics_service.py` → 0 errors

---

### Step 2: 在 `AnalyticsService` 中新增 `generate_chinese_summary` 方法

在 `src/services/analytics_service.py` 末尾（`get_chart_data` 方法之后）添加：

```python
async def generate_chinese_summary(
    self, report_type: str, metrics: dict, tenant_id: int
) -> str:
    """Generate a 2-sentence Chinese executive summary for a report using the AI gateway."""
    prompt_lines = [
        "你是一位 CRM 数据分析师。请根据以下指标生成一段不超过 2 句的中文执行摘要。",
        f"报表类型：{report_type}",
    ]
    for key, value in metrics.items():
        prompt_lines.append(f"- {key}: {value}")
    prompt_lines.append("请用中文回答，不要超过 2 个句子。")

    messages = [{"role": "user", "content": "\n".join(prompt_lines)}]
    context = {"tenant_id": tenant_id, "report_type": report_type}
    response = await self.gateway.chat(messages, context)

    summary = response.reply.strip()
    sentence_count = summary.count("。") + summary.count("！") + summary.count("？")
    if sentence_count > 2:
        parts = summary.split("。")
        summary = "。".join(parts[:2]) + "…"
    return summary
```

**完成判定**：`PYTHONPATH=src python -c "from services.analytics_service import AnalyticsService; print('import ok')"` → 无报错

---

### Step 3: 修改 `run_report`，在返回的 `dict` 中注入 `summary` 字段

找到 `run_report` 方法（L131-L150），在返回前加入摘要生成调用。找到 `run_report` 的 return 语句，改为：

```python
# After building the result dict (e.g. "result = await self.get_sales_revenue_report(...)")
summary = await self.generate_chinese_summary(report.type, result, tenant_id)
result["summary"] = summary
return result
```

具体在 `run_report` 每个 `if report.type == "..."` 分支的 return 之前插入。

**完成判定**：`git diff src/services/analytics_service.py | grep "summary"` → 有差异输出

---

### Step 4: 新建 `tests/unit/test_analytics_service.py`，mock `AIChatGateway`

创建 `tests/unit/test_analytics_service.py`：

```python
"""Unit tests for AnalyticsService — mock DB, no real DB needed."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on sys.path
_project_root = Path(__file__).resolve().parents[2]
_src_root = _project_root / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from unittest.mock import AsyncMock, MagicMock

import pytest

from internal.ai_gateway import AIChatGateway, AIResponse
from services.analytics_service import AnalyticsService


class MockState:
    def __init__(self):
        self.customers: dict[int, dict] = {}
        self.customers_next_id: int = 1


class MockRow:
    def __init__(self, mapping):
        self._mapping = mapping

    def __getitem__(self, key):
        return self._mapping[key]

    def __contains__(self, key):
        return key in self._mapping

    def keys(self):
        return self._mapping.keys()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._mapping.get(name)


class MockResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return MagicMock(
            all=MagicMock(return_value=self._rows),
            first=MagicMock(return_value=self._rows[0] if self._rows else None),
        )


def make_mock_session(**handlers):
    session = MagicMock()
    session.execute = AsyncMock(side_effect=lambda sql, params=None: handlers.get("execute_result", MockResult()))
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_gateway():
    gateway = MagicMock(spec=AIChatGateway)
    gateway.chat = AsyncMock(return_value=AIResponse(reply="本月销售表现良好，交易额环比增长 15%。"))
    return gateway


@pytest.fixture
def mock_db_session():
    return make_mock_session(execute_result=MockResult())


@pytest.fixture
def analytics_service(mock_db_session, mock_gateway):
    return AnalyticsService(mock_db_session, gateway=mock_gateway)


class TestGenerateChineseSummary:
    async def test_summary_is_chinese(self, analytics_service):
        """摘要必须为中文，不含英文句子。"""
        result = await analytics_service.generate_chinese_summary(
            report_type="sales_revenue",
            metrics={"总交易额": "¥120,000", "环比增长": "15%"},
            tenant_id=1,
        )
        # Check no ASCII letters in a sentence that also contains Chinese chars
        has_english_sentence = any(
            any(c.isascii() and c.isalpha() for c in sent) and any('\u4e00' <= c <= '\u9fff' for c in sent)
            for sent in result.replace("。", "！").replace("？", "！").split("！")
            if sent.strip()
        )
        assert not has_english_sentence, f"摘要包含中英混杂句子：{result}"

    async def test_summary_within_two_sentences(self, analytics_service):
        """摘要不超过 2 个汉语句号/感叹号/问号结尾的句子。"""
        result = await analytics_service.generate_chinese_summary(
            report_type="sales_conversion",
            metrics={"线索数": 50, "转化率": "8%"},
            tenant_id=1,
        )
        sentence_count = result.count("。") + result.count("！") + result.count("？")
        assert sentence_count <= 2, f"摘要句子数 {sentence_count} 超过 2：{result}"

    async def test_summary_called_with_correct_report_type(self, analytics_service, mock_gateway):
        """gateway.chat 应被调用，context 应包含 report_type。"""
        await analytics_service.generate_chinese_summary(
            report_type="pipeline_forecast",
            metrics={"预期营收": "¥500,000"},
            tenant_id=42,
        )
        mock_gateway.chat.assert_called_once()
        call_args = mock_gateway.chat.call_args
        messages = call_args[0][0]
        context = call_args[0][1]
        assert context.get("report_type") == "pipeline_forecast"
        assert context.get("tenant_id") == 42
        assert any("pipeline_forecast" in m["content"] for m in messages)

    async def test_summary_truncation_on_excess_sentences(self, mock_db_session):
        """超过 2 句时，摘要应截断到前两句并追加 '…'。"""
        gateway = MagicMock(spec=AIChatGateway)
        long_chinese = (
            "本月销售表现良好，交易额环比增长 15%。"
            "新客户获取数量达 30 家，转化率提升至 12%。"
            "预计下季度营收将突破 150 万大关。"
        )
        gateway.chat = AsyncMock(return_value=AIResponse(reply=long_chinese))
        svc = AnalyticsService(mock_db_session, gateway=gateway)
        result = await svc.generate_chinese_summary(
            report_type="sales_revenue",
            metrics={"总交易额": "¥120,000"},
            tenant_id=1,
        )
        sentence_count = result.count("。") + result.count("！") + result.count("？")
        assert sentence_count <= 2, f"截断后句子数仍为 {sentence_count}：{result}"
        assert result.endswith("…"), f"摘要应以 '…' 结尾：{result}"


class TestGatewayInjection:
    def test_default_gateway_is_instantiated(self):
        """不传 gateway 参数时，AnalyticsService 应内部 new 一个 AIChatGateway。"""
        session = MagicMock()
        svc = AnalyticsService(session)
        assert svc.gateway is not None
        assert isinstance(svc.gateway, AIChatGateway)

    def test_custom_gateway_is_used(self, mock_gateway):
        """传入 gateway 参数时，应直接使用该实例。"""
        session = MagicMock()
        svc = AnalyticsService(session, gateway=mock_gateway)
        assert svc.gateway is mock_gateway
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v` → `5 passed`

---

## 6. 验收

- [ ] `ruff check src/services/analytics_service.py` → 0 errors
- [ ] `PYTHONPATH=src ruff format --check src/services/analytics_service.py` → exit 0
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v` → 全 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_analytics_integration.py -v` → 全 passed（如涉及集成测试）
- [ ] 端到端模拟（无 router 改动则跳过）：`pytest tests/unit/ -v -k analytics` → 全 passed

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| AIChatGateway 的 stub（而非真实 LLM）生成的摘要质量不达预期 | 中 | 中 | `generate_chinese_summary` 结果暂存字段，后端可被真实 LLM 替换；不影响 report 数据本身 |
| `run_report` 在 gateway 调用失败时整体抛异常 | 低 | 中 | `generate_chinese_summary` 包裹 `try/except`，gateway 异常时返回空字符串 `summary=""`，`run_report` 仍正常返回结构化数据 |
| 单元测试 mock 的 `AIChatGateway` 与真实行为不一致 | 低 | 低 | 集成测试 `test_analytics_integration.py` 已覆盖 `AnalyticsService` 核心路径；新增测试只覆盖摘要生成逻辑 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/analytics_service.py tests/unit/test_analytics_service.py
git commit -m "feat(analytics): add AI-generated 2-sentence Chinese summaries to report results"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(analytics): integrate AI gateway for Chinese report summaries" --body "Closes #591

## Summary
- Add `generate_chinese_summary` to `AnalyticsService` via `AIChatGateway` injection
- Wire summary into `run_report` return dict as `summary` field
- Unit tests mock `AIChatGateway` and assert Chinese + ≤2 sentence constraint

## Test plan
- [ ] `PYTHONPATH=src pytest tests/unit/test_analytics_service.py -v` → 5 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_analytics_integration.py -v` → 全 passed
- [ ] `ruff check src/services/analytics_service.py` → 0 errors

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## 9. 参考

- 同类参考实现：[`src/services/ai_service.py`](../../../src/services/ai_service.py) — `AIService` 如何注入和使用 `AIChatGateway` 的模式
- 第三方文档：[AIChatGateway class](https://github.com/your-org/agent-job/blob/master/src/internal/ai_gateway.py)（`src/internal/ai_gateway.py` L17-L35）
- 父 issue / 关联：#48（父 issue），#41（`AIChatGateway` 提供者，被本板块依赖）

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | TBD |
