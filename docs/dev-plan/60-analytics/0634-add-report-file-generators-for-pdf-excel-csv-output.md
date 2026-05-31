# 报表生成器模块 · 实现 PDF/Excel/CSV 文件生成器

| 元数据 | 值 |
|---|---|
| Issue | #634 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2 工作日 |
| 依赖 | TBD - 待验证：关联 issue #633 的文件名是否仍为 `0633-报表配置与调度服务.md`，或在 60-analytics 目录下另有其他编号 |
| 启用后赋能 | 无 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`ReportService`（[`src/services/report_service.py`](../../../src/services/report_service.py) L31-L61）当前 `generate_pdf_report` 只返回占位符 `%PDF-1.4\n…%%EOF\n`，`generate_excel_report` 只返回 `"PK\x03\x04" + text` 字节串。两者都不是真正的多工作簿/多sheet内容，也没有超时保护。`export_to_csv` 虽用了 Python stdlib `csv` 模块，但也没有超时保护或生成器抽象。当系统需要生成可分发的业务报表（给客户/管理层发送 PDF/Excel/CSV）时，现有 stub 无法满足需求。

### 1.2 做完后

- **用户视角**：API `POST /api/v1/reports/pdf`、`POST /excel`、`POST /csv` 返回真实的文件内容（真实 PDF/Excel/多sheet/CSV），生成超过 30 秒会得到 `TimeoutException`（HTTP 422）。
- **开发者视角**：新增 `src/services/report_generation/generators/` 包，包含 `BaseGenerator` 抽象类和三个具体实现（PDF/Excel/CSV）。`ReportService.generate_pdf_report` / `generate_excel_report` / `export_to_csv` 内部调用对应生成器，`ReportService` 接口签名不变。

### 1.3 不做什么（剔除）

- [ ] 不实现图表渲染（matplotlib / reportlab 的图表绑定）——这是 issue #633 的范围，本板块只提供文件容器框架
- [ ] 不修改已有 API endpoint 路径（`/pdf`、`/excel`、`/csv` 保持不变；不在本板块新增 `/generate` 路由）
- [ ] 不实现调度（`ReportScheduleModel` 的调度触发逻辑由 #633 负责）

### 1.4 关键 KPI

- `PYTHONPATH=src ruff check src/services/report_generation/` → 0 errors
- `PYTHONPATH=src pytest tests/unit/test_report_generators.py -v` → ≥ 5 passed
- `PYTHONPATH=src pytest tests/integration/test_analytics_integration.py -k "report" -v` → ≥ 6 passed
- `POST /api/v1/reports/pdf`（mock auth）返回 `Content-Type: application/pdf` 且 body 以 `%PDF-1.4` 开头（或真实 PDF 头部）

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/report_service.py`](../../../src/services/report_service.py) L31-L61

```{python}:31-61:src/services/report_service.py
    async def generate_pdf_report(
        self,
        report_data: dict | None = None,
        title: str | None = None,
        tenant_id: int = 0,
        report_type: str | None = None,
        config: dict | None = None,
        date_range: dict | None = None,
    ) -> dict:
        """生成PDF报表 — sync, no DB needed."""
        report_data = report_data or {"config": config or {}, "date_range": date_range or {}}
        title = title or f"{report_type or 'report'} report"
        content = (
            "%PDF-1.4\n"
            f"1 0 obj << /Type /Catalog >> endobj\n% {title}\n"
            "%%EOF\n"
        ).encode()
        filename = f"{report_type or 'report'}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
        return {
            "status": "generated",
            "title": title,
            "format": "pdf",
            "generated_at": datetime.now(UTC).isoformat(),
            "content_base64": base64.b64encode(content).decode("ascii"),
            "filename": filename,
            "size_bytes": len(content),
            "data_summary": {...},
        }
```

`generate_excel_report`（L63-L92）同样只返回伪造的 `"PK\x03\x04"` 字节串，无真实工作簿内容。

### 2.2 涉及文件清单

- 要改：
  - [`src/services/report_service.py`](../../../src/services/report_service.py) — `generate_pdf_report`、`generate_excel_report`、`export_to_csv` 内部替换为生成器调用
  - [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) — 端点保持不变（路由逻辑不变）
- 要建：
  - `src/services/report_generation/generators/base.py` — `BaseGenerator` 抽象基类 + `GeneratorTimeoutError`
  - `src/services/report_generation/generators/pdf_generator.py` — ReportLab PDF 生成器
  - `src/services/report_generation/generators/excel_generator.py` — openpyxl 多 sheet Excel 生成器
  - `src/services/report_generation/generators/csv_generator.py` — CSV 生成器
  - `src/services/report_generation/__init__.py` — 包导出
  - `src/services/report_generation/generators/__init__.py` — 子包导出
  - `tests/unit/test_report_generators.py` — 单元测试（mock DB，不需要真实 DB）

### 2.3 缺什么

- [ ] 无 `BaseGenerator` 抽象层：当前三个格式逻辑全写在 `ReportService` 里，紧耦合，无法单独测试
- [ ] PDF 生成器返回占位符：无法生成含标题/页眉/数据行的真实 PDF
- [ ] Excel 生成器返回伪造内容：无法生成含多 sheet 的真实 `.xlsx`
- [ ] CSV 生成器无超时保护：`export_to_csv` 直接在主线程写文件，无 30 秒超时
- [ ] 无 `GeneratorTimeoutError` / 30 秒超时兜底：慢查询或大文件场景无感知超时

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/services/report_generation/__init__.py` | 包入口，导出 `get_generator(format)` 工厂函数 |
| `src/services/report_generation/generators/__init__.py` | generators 子包入口，导出所有生成器类 |
| `src/services/report_generation/generators/base.py` | `BaseGenerator` 抽象基类 + `GeneratorTimeoutError` |
| `src/services/report_generation/generators/pdf_generator.py` | ReportLab PDF 生成，实现 `generate(data, format) -> bytes` |
| `src/services/report_generation/generators/excel_generator.py` | openpyxl 多 sheet Excel 生成，实现 `generate(data, format) -> bytes` |
| `src/services/report_generation/generators/csv_generator.py` | CSV 生成，实现 `generate(data, format) -> bytes` |
| `tests/unit/test_report_generators.py` | 单元测试（MockRow/MockSession），覆盖 happy/boundary/error 场景 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/services/report_service.py`](../../../src/services/report_service.py) | `generate_pdf_report`/`generate_excel_report`/`export_to_csv` 内部调用 `get_generator(format).generate(data)`；保留接口签名不变 |
| [`src/api/routers/reports.py`](../../../src/api/routers/reports.py) | 无改动（路由不变，生成器替换在 service 层） |

### 3.3 新增能力

- **生成器包**：`src/services/report_generation/generators/` — `BaseGenerator` + PDF/Excel/CSV 三个实现
- **超时异常**：`GeneratorTimeoutError`，在生成耗时 >30 秒时由 `BaseGenerator.generate` 抛出
- **工厂函数**：`get_generator(format: Literal["pdf", "excel", "csv"]) -> BaseGenerator`
- **Service 方法**：`ReportService` 三个方法内部委托生成器，接口签名不变，向后兼容

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 ReportLab（PDF）不选 WeasyPrint / pdfkit**：纯 Python（无外部系统依赖），与本项目 stack 一致，pip install reportlab 即用。
- **选 openpyxl 不选 xlsxwriter**：openpyxl 支持读写已有 Excel 文件（含多 sheet），xlsxwriter 只支持创建新文件；CRM 报表需要追加/合并 sheet。
- **PDF/Excel/CSV 三层平级，不做继承链**：三者都是 `generate(data: dict, format: str) -> bytes`，接口扁平，不引入不必要的抽象层级。
- **超时用 `signal.SIGALRM`（类 Unix）**：`BaseGenerator.generate` 在子进程/线程池中运行，用 `signal.alarm(30)` 实现超时；Windows fallback 用 `threading.Timer` 模拟。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `reportlab` | `>=4.0,<5.0` | 当前项目未引入，与 openpyxl 兼容 |
| `openpyxl` | `>=3.1,<4.0` | SQLAlchemy 生态常用，pip install openpyxl |

### 4.3 兼容性约束

- `ReportService.generate_pdf_report` / `generate_excel_report` / `export_to_csv` 接口签名**不变**（向后兼容已有 router 调用方）
- 多租户：生成器无 DB 写操作，不需要 `tenant_id` 透传
- Service 错误抛 `AppException` 子类；`GeneratorTimeoutError` 在 router 层捕获并转化为 `ValidationException`
- `PYTHONPATH=src`，import 路径写 `from services.report_generation import get_generator`，不要写 `from src.services...`

### 4.4 已知坑

1. **ReportLab 生成的 PDF 必须有中文字体** → 规避：默认使用 Helvetica（ASCII 安全），如需中文传 `fontname="Helvetica"` 并在 `data` 中注明可扩展方向
2. **openpyxl 对同一 workbook 的并发写会导致文件损坏** → 规避：每个 `generate()` 调用创建独立的 `Workbook()` 实例，不复用
3. **signal.SIGALRM 在非主线程中不触发** → 规避：生成逻辑运行在主线程；超时用 `functools.partial` + `signal.alarm` 在调用前设闹钟
4. **base64 编码后返回时 `Content-Length` 需要用原始字节长度** → 规避：router 先 `base64.b64decode` 得到 `bytes`，再取 `len(bytes)` 填 header

---

## 5. 实现步骤（按顺序）

### Step 1: 创建生成器包结构

新建 `src/services/report_generation/` 目录及 `__init__.py`，定义 `get_generator` 工厂函数和 `GeneratorTimeoutError` 异常类。

操作：
- a) 创建 `src/services/report_generation/__init__.py`
- b) 创建 `src/services/report_generation/generators/__init__.py`
- c) 在 `__init__.py` 写入：

```python
"""Report generation package — factory for format-specific generators."""

from __future__ import annotations

import importlib

class GeneratorTimeoutError(Exception):
    """Raised when file generation exceeds the 30-second timeout."""

_GENERATOR_MAP = {
    "pdf": ".generators.pdf_generator",
    "excel": ".generators.excel_generator",
    "csv": ".generators.csv_generator",
}

def get_generator(format: str):
    """Return the generator instance for the given format."""
    if format not in _GENERATOR_MAP:
        raise ValueError(f"Unknown format: {format}")
    module_name = _GENERATOR_MAP[format]
    mod = importlib.import_module(module_name, package="services.report_generation")
    return mod.Generator()
```

- c) 创建 `src/services/report_generation/generators/__init__.py`，导出全部类

**完成判定**：`PYTHONPATH=src python -c "from services.report_generation import get_generator; g = get_generator('csv'); print('OK')"` → 输出 `OK`（不抛异常）

### Step 2: 实现 BaseGenerator 抽象基类

操作：
- a) 创建 `src/services/report_generation/generators/base.py`
- b) 写入 `BaseGenerator` 抽象类：

```python
"""Base generator interface and shared timeout logic."""

from __future__ import annotations

import signal
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

class GeneratorTimeoutError(Exception):
    """Raised when generation exceeds 30 seconds."""

class BaseGenerator(ABC):
    """Abstract base for all file generators."""

    TIMEOUT_SECONDS = 30

    def generate(self, data: dict | None = None, fmt: str = "") -> bytes:
        """Run generate_impl with 30-second timeout. Returns raw bytes."""
        def _run():
            return self.generate_impl(data or {}, fmt)

        old_alarm = signal.alarm(self.TIMEOUT_SECONDS)
        try:
            result = _run()
        except TimeoutError:
            raise GeneratorTimeoutError(
                f"Generation timed out after {self.TIMEOUT_SECONDS}s"
            )
        finally:
            signal.alarm(old_alarm)
        return result

    @abstractmethod
    def generate_impl(self, data: dict, fmt: str) -> bytes:
        """Subclasses implement the actual file generation."""
        ...
```

**完成判定**：`PYTHONPATH=src ruff check src/services/report_generation/generators/base.py` → 0 errors

### Step 3: 实现 PdfGenerator（ReportLab）

操作：
- a) 创建 `src/services/report_generation/generators/pdf_generator.py`
- b) 实现 `PdfGenerator(BaseGenerator)`，关键逻辑：
  - `data` 格式：`{"title": str, "sections": [{"heading": str, "rows": [[str]]}]}`
  - 使用 `reportlab.lib.pagesizes.A4` 作为页面大小
  - 用 `SimpleDocTemplate` + `Table` 渲染每个 section
  - 返回 `bytes`（PDF 原始内容）

```python
"""PDF generator using ReportLab."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from .base import BaseGenerator, GeneratorTimeoutError

class PdfGenerator(BaseGenerator):
    def generate_impl(self, data: dict[str, Any], fmt: str) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        elements = []

        title = data.get("title", "Report")
        elements.append(Paragraph(title, styles["Title"]))
        elements.append(Spacer(1, 0.5 * cm))

        for section in data.get("sections", []):
            heading = section.get("heading", "")
            elements.append(Paragraph(heading, styles["Heading2"]))
            rows = section.get("rows", [])
            if rows:
                t = Table(rows)
                t.setStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ])
                elements.append(t)
            elements.append(Spacer(1, 0.3 * cm))

        doc.build(elements)
        return buffer.getvalue()
```

**完成判定**：`PYTHONPATH=src python -c "from services.report_generation.generators.pdf_generator import PdfGenerator; g = PdfGenerator(); b = g.generate({'title':'t','sections':[{'heading':'h','rows':[['a','b'],['c','d']]}]},''); print(len(b), b[:4])"` → 输出 `bytes` 长度 > 0 且以 `b'%PDF'` 开头

### Step 4: 实现 ExcelGenerator（openpyxl）

操作：
- a) 创建 `src/services/report_generation/generators/excel_generator.py`
- b) 实现 `ExcelGenerator(BaseGenerator)`：
  - `data` 格式：`{"title": str, "sheets": [{"name": str, "headers": [str], "rows": [[str]]}]}`
  - 每个 sheet 名对应一个 `Worksheet`
  - 第一行写入 `headers`，后续行写入 `rows`
  - 使用 `BytesIO` 序列化 `Workbook`

```python
"""Excel generator using openpyxl."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook

from .base import BaseGenerator

class ExcelGenerator(BaseGenerator):
    def generate_impl(self, data: dict[str, Any], fmt: str) -> bytes:
        wb = Workbook()
        first = True
        for sheet_def in data.get("sheets", []):
            ws = wb.active if first else wb.create_sheet(sheet_def.get("name", "Sheet"))
            first = False
            headers = sheet_def.get("headers", [])
            if headers:
                ws.append(headers)
            for row in sheet_def.get("rows", []):
                ws.append(row)
        buffer = BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
```

**完成判定**：`PYTHONPATH=src python -c "from services.report_generation.generators.excel_generator import ExcelGenerator; g = ExcelGenerator(); b = g.generate({'sheets':[{'name':'s','headers':['a','b'],'rows':[['1','2'],['3','4']]}]},''); print(len(b), b[:4])"` → 输出 `bytes` 长度 > 0 且以 `b'PK'` 开头（ZIP/XLSX 魔数）

### Step 5: 实现 CsvGenerator

操作：
- a) 创建 `src/services/report_generation/generators/csv_generator.py`
- b) 实现 `CsvGenerator(BaseGenerator)`：

```python
"""CSV generator using the Python csv stdlib."""

from __future__ import annotations

import csv
import io
from typing import Any

from .base import BaseGenerator

class CsvGenerator(BaseGenerator):
    def generate_impl(self, data: dict[str, Any], fmt: str) -> bytes:
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        output = io.StringIO()
        writer = csv.writer(output)
        if headers:
            writer.writerow(headers)
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")
```

**完成判定**：`PYTHONPATH=src python -c "from services.report_generation.generators.csv_generator import CsvGenerator; g = CsvGenerator(); b = g.generate({'headers':['a','b'],'rows':[['1','2']]},''); print(b)"` → 输出 `b'a,b\r\n1,2\r\n'`

### Step 6: 将生成器接入 ReportService

操作：
- a) 在 `src/services/report_service.py` 顶部添加：

```python
from services.report_generation import get_generator
```

- b) 替换 `generate_pdf_report` 的内容，保留方法签名：

```python
    async def generate_pdf_report(self, report_data: dict | None = None, title: str | None = None,
        tenant_id: int = 0, report_type: str | None = None,
        config: dict | None = None, date_range: dict | None = None) -> dict:
        title = title or f"{report_type or 'report'} report"
        data = report_data or {"config": config or {}, "date_range": date_range or {}}
        wrapped = {"title": title, "sections": data.get("sections", [
            {"heading": title, "rows": data.get("rows", [])}
        ])}
        try:
            content = get_generator("pdf").generate(wrapped, "pdf")
        except GeneratorTimeoutError as e:
            raise ValidationException(str(e)) from e
        filename = f"{report_type or 'report'}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
        return {
            "status": "generated",
            "title": title,
            "format": "pdf",
            "generated_at": datetime.now(UTC).isoformat(),
            "content_base64": base64.b64encode(content).decode("ascii"),
            "filename": filename,
            "size_bytes": len(content),
            "data_summary": {"labels_count": len(data.get("labels", [])),
                              "datasets_count": len(data.get("datasets", []))},
        }
```

- c) 同理替换 `generate_excel_report`，调用 `get_generator("excel")`
- d) 同理替换 `export_to_csv`，调用 `get_generator("csv")`

**完成判定**：`PYTHONPATH=src ruff check src/services/report_service.py` → 0 errors

### Step 7: 编写单元测试

操作：
创建 `tests/unit/test_report_generators.py`，测试用例：

**Case 1（happy path）**：`PdfGenerator.generate` 传入 `{"title":"t","sections":[{"heading":"h","rows":[["a","b"],["c","d"]]}]}` → 返回 bytes 以 `b'%PDF'` 开头，长度 > 0

**Case 2（happy path）**：`ExcelGenerator.generate` 传入含两个 sheet 的 data → `Workbook` 可正常打开

**Case 3（happy path）**：`CsvGenerator.generate` 传入 `{"headers":["x","y"],"rows":[["1","2"]]}` → 返回正确 UTF-8 内容

**Case 4（boundary）**：`CsvGenerator.generate` 传入空 `rows` → 不抛异常，返回仅含 header 的 CSV

**Case 5（error）**：`get_generator("pptx")` → 抛 `ValueError`

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from services.report_generation import get_generator
from services.report_generation.generators.base import GeneratorTimeoutError

class TestPdfGenerator:
    def test_generate_returns_pdf_bytes(self):
        g = get_generator("pdf")
        b = g.generate({"title": "Test", "sections": [{"heading": "H", "rows": [["a", "bاقشة]}, "pdf")
        assert b[:4] == b"%PDF"
        assert len(b) > 0

class TestExcelGenerator:
    def test_generate_returns_xlsx_bytes(self):
        g = get_generator("excel")
        b = g.generate({"sheets": [{"name": "S", "headers": ["x", "y"], "rows": [["1", "2}, "excel")
        assert b[:4] == b"PK\x03\x04"
        assert len(b) > 0

class TestCsvGenerator:
    def test_generate_csv_with_headers_and_rows(self):
        g = get_generator("csv")
        b = g.generate({"headers": ["a", "b"], "rows": [["1", "2"], ["3", "4"]}}, "csv")
        assert b"a,b" in b
        assert b"1,2" in b

    def test_generate_csv_empty_rows(self):
        g = get_generator("csv")
        b = g.generate({"headers": ["x"], "rows": []}, "csv")
        assert b"x" in b

class TestFactory:
    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            get_generator("pptx")
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_report_generators.py -v` → ≥ 5 passed

---

## 6. 验收

- [ ] `PYTHONPATH=src ruff check src/services/report_generation/` → 0 errors
- [ ] `PYTHONPATH=src ruff check src/services/report_service.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_report_generators.py -v` → ≥ 5 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_analytics_integration.py -k "report" -v` → ≥ 6 passed（已有测试覆盖 `generate_pdf_report`、`generate_excel_report`、`export_to_csv`，生成器替换后应全部仍 pass）
- [ ] `PYTHONPATH=src python -c "from services.report_generation import get_generator; g = get_generator('pdf'); b = g.generate({'title':'t','sections':[{'heading':'h','rows':[['a','b']]}]},''); print(b[:4])"` → 输出 `b'%PDF'`

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| ReportLab / openpyxl 依赖引入后在某些 Linux 发行版缺失字体 | 低 | 中 | Docker 镜像中已安装 `fonts-dejavu-core`，DejaVu 字体在 ReportLab 默认搜索路径；如仍缺失 PDF 中文显示为空格，降级为仅 ASCII Helvetica |
| `signal.SIGALRM` 在 Windows 上不生效（超时永远不触发） | 低 | 中 | Windows 上 `BaseGenerator.generate` 检测 `sys.platform == "win32"` 后改用 `threading.Timer(30, raise_timeout)` 路径，不阻塞 CI（CI 运行在 Linux） |
| 生成器替换导致已有集成测试失败（格式变化） | 低 | 中 | `ReportService` 接口不变，已有 router/集成测试仍用 `{"status": "generated", "format": "pdf"}` 断言，只验证 dict 字段，不验证 `content_base64` 具体内容 |
| 安装新依赖（reportlab / openpyxl）在某些环境下失败 | 低 | 中 | 将两者加入 `pyproject.toml` 的 `dependencies` 数组，CI 的 pip install 阶段自动处理；旧环境手动 `pip install reportlab openpyxl` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/services/report_generation/ src/services/report_service.py tests/unit/test_report_generators.py
git commit -m "feat(reports): add PDF/Excel/CSV file generators with 30s timeout"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(reports): add file generators for pdf/excel/csv output (closes #634)" --body "Closes #634"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`src/services/report_service.py`](../../../src/services/report_service.py) — 当前 stub 实现
- 同类参考实现：[`src/api/routers/reports.py`](../../../src/api/routers/reports.py) — router 调用 service 的模式
- 第三方文档：[ReportLab User Guide](https://docs.reportlab.com/) — PDF 生成
- 第三方文档：[openpyxl documentation](https://openpyxl.readthedocs.io/) — Excel 生成
- 父 issue / 关联：#40
- 依赖 issue / 关联：#633

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
