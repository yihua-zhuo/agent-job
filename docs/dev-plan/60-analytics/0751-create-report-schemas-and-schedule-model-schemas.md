# 报表 Schema · 新建报告与调度 Pydantic 模型

| 元数据 | 值 |
|---|---|
| Issue | #751 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.25 工作日 |
| 依赖 | TBD - 待验证：关联的 Reports Router 基础结构文档（#750） |
| 启用后赋能 | 所有调用 `CreateReportSchema` / `CreateScheduleSchema` 的 router 与 service（本板块之后创建） |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

当前 [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) 中报告创建与调度创建相关的 schema 以内联 `BaseModel` 类形式定义，分散在不同路由函数附近。当多个端点需要复用同一 schema 时产生了重复定义，且无法集中维护字段约束与验证逻辑。将这些 schema 提取为具名模型是 #632 子任务的标准路径。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层 schema 重构。
- **开发者视角**：`src/models/schemas/report.py` 提供 `CreateReportSchema` 与 `CreateScheduleSchema` 两个 Pydantic 模型；[`reports.py`](../../../src/api/routers/reports.py) 的 imports 改为从具名 schema 引用，字段约束集中一处、可复用。

### 1.3 不做什么（剔除）

- [ ] 不实现报告存储（ORM model 在后续板块处理）
- [ ] 不实现报告 API endpoint（router 在 #750 已建，具体 handler 后续板块处理）
- [ ] 不实现数据库 migration（schema 仅作请求/响应序列化，不需要表结构）

### 1.4 关键 KPI

- `ruff check src/models/schemas/report.py` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_report_schemas.py -v` → 全部 passed（schema 字段解析正确）
- reports.py 现有 imports 更新后 `ruff check src/api/routers/reports.py` → 0 errors

---

## 2. 当前现状（起点）

### 2.1 现有实现

TBD - 待验证：`src/api/routers/reports.py` — 需要确认当前内联 BaseModel schema 的具体字段定义（`name`、`report_type`/`type`、`schedule_cron`/`cron` 等字段名与类型），据此设计 `CreateReportSchema` 与 `CreateScheduleSchema`。

### 2.2 涉及文件清单

- 要改：
  - [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) — 更新 import 段，从 `src/models/schemas/report.py` 引用具名 schema，删除对应的内联 BaseModel 类
- 要建：
  - `src/models/schemas/report.py` — 新建，含 `CreateReportSchema` 与 `CreateScheduleSchema`
  - `tests/unit/test_report_schemas.py` — 新建，验证 schema 字段解析与验证行为

### 2.3 缺什么

- [ ] `src/models/schemas/report.py` — Pydantic schema 文件不存在
- [ ] `CreateReportSchema` — 报告创建请求的字段定义（name、type、description 等）
- [ ] `CreateScheduleSchema` — 调度创建请求的字段定义（cron 表达式、enabled 等）
- [ ] reports.py 中内联 schema 未集中化，复用困难

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/models/schemas/report.py` | 报表与调度 Pydantic schema：`CreateReportSchema`、`CreateScheduleSchema` |
| `tests/unit/test_report_schemas.py` | schema 字段解析与 validator 单元测试 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) | 删除内联 BaseModel schema 类；import 改为 `from src.models.schemas.report import CreateReportSchema, CreateScheduleSchema` |

### 3.3 新增能力

- **Pydantic schema**：`CreateReportSchema` — 报告创建字段（name、type、description 等）
- **Pydantic schema**：`CreateScheduleSchema` — 调度创建字段（cron 表达式、enabled 等）
- **Module export**：上述两个 schema 在 `src/models/schemas/report.py` 导出，供 router 引用

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 Pydantic BaseModel 而非 dataclass**：与现有 `src/models/schemas/` 下其他 schema 保持一致；提供内置 validator 与 JSON schema 生成能力。
- **字段命名跟随现有 reports.py 惯例**：不引入新的命名约定，确保 import 替换时字段名称兼容。

### 4.2 版本约束

无新增外部依赖；Pydantic 为本项目已有依赖，保持现有版本约束。

### 4.3 兼容性约束

- Pydantic schema 继承 `BaseModel`，不使用 `Base`（本板块无 ORM，不涉及 `Base.metadata` 冲突）
- Import 路径使用 `from src.models.schemas.report import ...` 而非 `from src.models.schemas.report import *`（显式导出，便于 ruff 检查）
- 字段全部具名，不依赖位置参数

### 4.4 已知坑

1. **ruff import 顺序错误** → 规避：`ruff check --fix src/models/schemas/report.py` 自动排序后检查；必要时手动调整
2. **reports.py 内联 schema 字段名与新 schema 不一致** → 规避：Step 1 前先通过 grep 确认现有字段名（见 §2.1），对齐后再创建 schema

---

## 5. 实现步骤（按顺序）

### Step 1: 创建 report.py schema 文件

在 `src/models/schemas/report.py` 创建两个 Pydantic schema 类：

操作：
- a) 确认现有 reports.py 中内联 schema 的字段名与类型（grep `class.*BaseModel` 在 [`reports.py`](../../../src/api/routers/reports.py) 中）
- b) 创建 `src/models/schemas/report.py`，写入 `CreateReportSchema` 与 `CreateScheduleSchema`

示例代码（字段名待 §2.1 确认后调整）：

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateReportSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="报表名称")
    report_type: str = Field(..., description="报表类型")
    description: Optional[str] = Field(None, max_length=1000)
    tenant_id: int = Field(..., description="租户 ID")

    class Config:
        from_attributes = True


class CreateScheduleSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="调度名称")
    cron_expression: str = Field(..., description="Cron 表达式")
    enabled: bool = Field(True, description="是否启用")
    report_id: Optional[int] = Field(None, description="关联报表 ID")
    tenant_id: int = Field(..., description="租户 ID")

    class Config:
        from_attributes = True
```

**完成判定**：`ruff check src/models/schemas/report.py` → 0 errors / `ls src/models/schemas/report.py` 文件存在

---

### Step 2: 更新 reports.py 的 imports

操作：
- a) 读取当前 [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) 的 import 段与内联 BaseModel 类
- b) 删除内联 schema 类定义
- c) 在 import 段添加：`from src.models.schemas.report import CreateReportSchema, CreateScheduleSchema`

示例 diff：

```diff
- from pydantic import BaseModel
- class CreateReportSchema(BaseModel):
-     name: str
-     ...
- class CreateScheduleSchema(BaseModel):
-     cron_expression: str
-     ...

+ from src.models.schemas.report import CreateReportSchema, CreateScheduleSchema
```

**完成判定**：`ruff check src/api/routers/reports.py` → 0 errors

---

### Step 3: 编写 schema 单元测试

创建 `tests/unit/test_report_schemas.py`：

操作：
- a) 在 `tests/unit/test_report_schemas.py` 写入测试用例，验证字段解析、必填校验、类型错误被 Pydantic 正确拒绝
- b) 如 reports.py 需要 mock fixture（`mock_db_session`），在 conftest.py 中确认 `make_mock_session` 可用

示例代码：

```python
import pytest
from pydantic import ValidationError
from src.models.schemas.report import CreateReportSchema, CreateScheduleSchema


class TestCreateReportSchema:
    def test_valid_fields(self):
        data = {"name": "Monthly Sales", "report_type": "sales", "tenant_id": 1}
        schema = CreateReportSchema(**data)
        assert schema.name == "Monthly Sales"
        assert schema.report_type == "sales"

    def test_missing_required_field_raises(self):
        data = {"report_type": "sales", "tenant_id": 1}
        with pytest.raises(ValidationError) as exc_info:
            CreateReportSchema(**data)
        assert "name" in str(exc_info.value)

    def test_optional_description(self):
        data = {"name": "Test", "report_type": "test", "tenant_id": 1}
        schema = CreateReportSchema(**data)
        assert schema.description is None


class TestCreateScheduleSchema:
    def test_valid_schedule(self):
        data = {"name": "Daily Run", "cron_expression": "0 0 * * *", "enabled": True, "tenant_id": 1}
        schema = CreateScheduleSchema(**data)
        assert schema.cron_expression == "0 0 * * *"

    def test_enabled_default_true(self):
        data = {"name": "Run", "cron_expression": "0 9 * * *", "tenant_id": 1}
        schema = CreateScheduleSchema(**data)
        assert schema.enabled is True
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_report_schemas.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/models/schemas/report.py` → 0 errors
- [ ] `ruff check src/api/routers/reports.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_report_schemas.py -v` → 全 passed
- [ ] `PYTHONPATH=src ruff check src/models/schemas/ src/api/routers/reports.py` → 0 errors（两个文件合并检查）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| 新 schema 字段名与 reports.py 现有内联 schema 不一致导致运行时错误 | 低 | 中 | Step 1 前先 grep 确认字段名，不匹配时调整 schema 字段名保持兼容 |
| reports.py import 更新后其他调用方（service 层）未同步更新 | 低 | 中 | service 层 schema 引用在后续板块（#632 子任务）中统一处理，本板块仅限 router 层 |
| ruff 排序后 import 行数变化导致其他测试 fixture 路径断裂 | 极低 | 中 | 通过全量 `ruff check` 验收，如失败用 `ruff check --fix` 自动修复 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/models/schemas/report.py src/api/routers/reports.py tests/unit/test_report_schemas.py
git commit -m "feat(reports): extract CreateReportSchema and CreateScheduleSchema to src/models/schemas/report.py"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(reports): extract report schemas (#751)" --body "Closes #751"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-31 | 创建 | TBD |
