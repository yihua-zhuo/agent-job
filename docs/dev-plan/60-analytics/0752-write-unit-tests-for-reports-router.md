# 为 reports router 编写单元测试 · 为 reports router 编写完整单元测试

| 元数据 | 值 |
|---|---|
| Issue | #752 |
| 分类 | [60-analytics](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 0.5 工作日 |
| 依赖 | [reports router 实现](./0632-add-reports-api-router-with-all-endpoints.md) |
| 启用后赋能 | TBD - 待验证：analytics报表生成相关 issue 编号待确认 |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

Issue #751 完成了 reports router 的实现（10 个端点），但目前没有对应的单元测试覆盖。根据本项目的测试规范（见 CLAUDE.md §单元测试），每个 router 必须有独立的单元测试文件，以 mock 模拟 DB session 和 service 层，实现快速（<5s）、无副作用的回归验证。本 issue 是 #751 的直接依赖项，是完善 reports 功能闭环的必经步骤。

### 1.2 做完后

- **用户视角**：无用户可见变化 — 纯底层测试工程化改进。
- **开发者视角**：`tests/unit/test_reports_router.py` 可独立运行，覆盖全部 10 个端点的 happy-path 和关键错误分支。后续修改 reports router 时，测试即为回归防护网，无需启动真实数据库即可验证逻辑正确性。

### 1.3 不做什么（剔除）

- [ ] 不实现 reports router 本身的功能逻辑（由 #751 负责）
- [ ] 不写集成测试（Integration tests 需真实 PostgreSQL，另有规范，见 CLAUDE.md §Integration Test Fixtures）
- [ ] 不测试 PDF/Excel/CSV 的文件生成内容（文件内容正确性由下游功能测试覆盖）

### 1.4 关键 KPI

- [指标 1：`PYTHONPATH=src pytest tests/unit/test_reports_router.py -v` → 全部 passed（预计 ≥ 15 个用例）]
- [指标 2：`ruff check src/api/routers/reports_router.py tests/unit/test_reports_router.py` → 0 errors]
- [指标 3：测试覆盖全部 10 个端点：list, create, get, update, delete, generate_pdf, generate_excel, export_csv, generate, download, schedule]

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：TBD - 待验证：`src/api/routers/reports_router.py` L? — 确认 10 个端点签名及 HTTP 方法

参考同类测试模式（同类实现）：

```{python}:tests/unit/test_customers_router.py
# 现有 customers router 测试结构（mock session + mock service + FastAPI TestClient）
# from httpx import AsyncClient, ASGITransport
# from api.routers.customers_router import router as customers_router
# @pytest.fixture
# def mock_db_session(): ...
# @pytest.fixture
# async def ac(mock_db_session, mock_user): ...
```

### 2.2 涉及文件清单

- 要改：
  - TBD - 待验证：`src/api/routers/reports_router.py` — 确认端点路径、HTTP 方法、参数签名
  - TBD - 待验证：`src/services/report_service.py` — 确认 service 方法名及返回值类型
- 要建：
  - `tests/unit/test_reports_router.py` — reports router 完整单元测试（新文件）
  - TBD - 待验证：`tests/unit/conftest.py` — 如需新增 mock handler（检查现有 handlers 是否够用）

### 2.3 缺什么

- [ ] `tests/unit/test_reports_router.py` 文件不存在，无任何测试覆盖]
- [ ] 未确认 reports router 端点路径（如 `/reports/` 前缀、具体 path 参数名）
- [ ] 未确认 ReportService 方法签名（供 mock 返回值）
- [ ] 未确认 reports router 是否依赖 FastAPI 的 `require_auth`（`AuthContext`）和 `get_db`（`Depends(get_db)`）

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|---------|
| `tests/unit/test_reports_router.py` | reports router 完整单元测试，覆盖 10 个端点的 happy-path + 错误分支 |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| TBD - 待验证：`src/api/routers/reports_router.py` | 确认 10 个端点签名（依赖 #751） |
| TBD - 待验证：`src/services/report_service.py` | 确认 service 方法签名（依赖 #751） |

### 3.3 新增能力

- **单元测试覆盖**：新增 `tests/unit/test_reports_router.py`，覆盖以下 10 个端点（每个至少 1 个用例）：
  - `GET /reports/` — list（分页）
  - `POST /reports/` — create
  - `GET /reports/{report_id}` — get
  - `PUT /reports/{report_id}` — update
  - `DELETE /reports/{report_id}` — delete
  - `POST /reports/{report_id}/generate_pdf` — generate_pdf
  - `POST /reports/{report_id}/generate_excel` — generate_excel
  - `GET /reports/{report_id}/export_csv` — export_csv
  - `POST /reports/generate` — generate
  - `GET /reports/{report_id}/download` — download
  - `POST /reports/schedule` — schedule

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **选 FastAPI TestClient（或 httpx AsyncClient）不选 pytest-aiohttp**：本项目所有现有 router 测试均使用 FastAPI 内置 `TestClient` 或 `httpx.AsyncClient` + `ASGITransport`，优先遵循既有模式保证一致性。
- **选手动 mock 不选 pytest-mock 插件**：本项目单元测试使用 `tests/unit/conftest.py` 中的 `MockState` + `make_mock_session` 体系，手动 mock 可与既有 fixture 无缝衔接，无需引入额外依赖。

### 4.2 版本约束

无新依赖引入。

### 4.3 兼容性约束

- 多租户：mock 的 service 调用必须携带 `tenant_id` 参数
- 测试中 router 的 session 必须通过 `Depends(get_db)` 注入，禁止使用 `async with get_db() as session:`
- `require_auth` mock 必须返回包含 `tenant_id` 的 `AuthContext`

### 4.4 已知坑

1. **httpx AsyncClient 在部分 Python 版本下需显式传入 `app` 实例** → 规避：使用 `from httpx import AsyncClient, ASGITransport; await AsyncClient(transport=ASGITransport(app=app), base_url="http://test").get(...)`
2. **mock service 方法必须与实际 service 方法签名完全一致** → 规避：在编写测试前先确认 `ReportService` 各方法的参数名和返回值类型，避免运行时 `TypeError`

---

## 5. 实现步骤（按顺序）

### Step 1: 确认 reports router 和 report_service 的实际端点与方法签名

[在开始写测试前，必须确认 router 文件中的 10 个端点路径、HTTP 方法、path parameter 名称，以及 ReportService 对应方法的签名。这是后续 mock 的依据。]

操作：
- a)读取 `src/api/routers/reports_router.py`，记录每个端点的路径、HTTP 方法、函数名
- b) 读取 `src/services/report_service.py`，记录每个 service 方法的签名（参数名 + 返回类型）
- c) 对照参考 `tests/unit/test_customers_router.py` 的 fixture 结构

**完成判定**：`ls src/api/routers/reports_router.py src/services/report_service.py tests/unit/test_customers_router.py` → 三个文件均存在

---

### Step 2: 创建 tests/unit/test_reports_router.py，编写 mock session 和 auth fixtures

[建立测试文件的骨架：import、mock session fixture、mock AuthContext fixture、mock ReportService fixture。参考 `tests/unit/test_customers_router.py` 的 fixture 命名和结构。]

操作：
- a) 新建 `tests/unit/test_reports_router.py`
- b) 定义 `mock_db_session` fixture（使用 `make_mock_session`，传入必要的 handler list）
- c) 如现有 `conftest.py` 中无 `report_service` 相关 handler，新增 `make_report_handler(state)` 函数
- d) 定义 `mock_auth_ctx` fixture，返回 `AuthContext(tenant_id=1, user_id=1, ...)`

示例代码（如有）：

```python
# tests/unit/test_reports_router.py（骨架）
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from api.routers.reports_router import router as reports_router
from internal.middleware.fastapi_auth import AuthContext
from tests.unit.conftest import make_mock_session

# 如需要新增 handler（参考 conftest.py 中其他 handler 的写法）
def make_report_handler(state):
    async def handle(call):
        method = call[0]
        if method == "execute":
            # 模拟 SELECT / INSERT / UPDATE / DELETE
            return MagicMock()
        return MagicMock()
    return handle

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session([make_report_handler(state)])

@pytest.fixture
def mock_auth_ctx():
    return AuthContext(tenant_id=1, user_id=1, roles=[])
```

**完成判定**：`PYTHONPATH=src ruff check tests/unit/test_reports_router.py` → 0 errors（文件可正常 import）

---

### Step 3: 编写 list 端点（GET /reports/）测试用例

[测试分页列表端点，mock service.list_reports 返回 (items, total)，验证返回结构包含 items 和 total 字段。]

操作：
- a) patch `ReportService.list_reports` 返回 `([], 0)` 和返回含数据的列表
- b) 发送 `GET /reports/?page=1&page_size=20`
- c) assert `response.status_code == 200` 且 `response.json()["success"] == True`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_reports_router.py -k "test_list" -v` → passed

---

### Step 4: 编写 create 端点（POST /reports/）测试用例

[测试创建报表端点，mock service.create_report 返回 ORM 对象，验证 201 状态码和返回数据。]

操作：
- a) patch `ReportService.create_report` 返回 mock ORM 对象（带 `id`、`name` 等字段）
- b) 发送 `POST /reports/` 带 JSON body
- c) assert `response.status_code == 201`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_reports_router.py -k "test_create" -v` → passed

---

### Step 5: 编写 get / update / delete 端点测试用例

[测试单个报表的读取、更新、删除。get 验证 200 + data 字段；update 验证 200；delete 验证 200 或 204。]

操作：
- a) patch 相应 service 方法
- b) 分别发送 `GET /reports/1`、`PUT /reports/1`、`DELETE /reports/1`
- c) assert 各自预期状态码

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_reports_router.py -k "test_get or test_update or test_delete" -v` → 全部 passed

---

### Step 6: 编写 generate_pdf / generate_excel / export_csv / generate / download / schedule 端点测试用例

[测试剩余 6 个端点，mock 各自 service 方法，验证返回状态码和基本响应结构。]

操作：
- a) patch `ReportService.generate_pdf`、`ReportService.generate_excel`、`ReportService.export_csv`、`ReportService.generate`、`ReportService.download`、`ReportService.schedule`
- b) 分别发送请求
- c) assert 各自预期状态码（200/201）

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_reports_router.py -k "test_generate or test_export or test_download or test_schedule" -v` → 全部 passed

---

### Step 7: 编写 NotFoundException 错误分支测试

[对 get/update/delete 端点 mock service 抛出 NotFoundException，验证 router 返回 404 JSON 响应。]

操作：
- a) patch service 方法使其抛出 `NotFoundException("Report")`
- b) 发送请求
- c) assert `response.status_code == 404`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_reports_router.py -k "not_found" -v` → 全部 passed

---

### Step 8: 运行全量测试 + lint 验证

[运行完整测试文件 + ruff 检查，确认全部 passed 且无 lint 错误。]

操作：
- a) `PYTHONPATH=src pytest tests/unit/test_reports_router.py -v`
- b) `ruff check tests/unit/test_reports_router.py`

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_reports_router.py -v` → 全部 passed；`ruff check tests/unit/test_reports_router.py` → 0 errors

---

## 6. 验收

- [ ] `ruff check tests/unit/test_reports_router.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_reports_router.py -v` → 全部 passed
- [ ] 测试覆盖全部 10 个端点：list, create, get, update, delete, generate_pdf, generate_excel, export_csv, generate, download, schedule
- [ ] `PYTHONPATH=src ruff check src/api/routers/reports_router.py` → 0 errors（如该文件由 #751 新增或修改）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #751 reports router 实现未完成或端点签名与测试预期不符 | 中 | 中 | 测试文件骨架先行，待 #751 合入后微调 mock 路径；不阻塞其他板块 |
| ReportService 方法名与测试 mock 的方法名不一致导致 AttributeError | 低 | 中 | Step 1 优先确认签名；发现不一致时在 §2.3 及时更新 |
| 新增 handler 引入 conftest.py 修改与其他测试文件冲突 | 低 | 低 | 仅在确认现有 handlers 不够用时才新增；review 时一并检查 |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add tests/unit/test_reports_router.py
git commit -m "test: add unit tests for reports router (#752)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "test: unit tests for reports router (#752)" --body "Closes #752"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：[`tests/unit/test_customers_router.py`](../../../tests/unit/test_customers_router.py)
- 同类参考实现：[`tests/unit/conftest.py`](../../../tests/unit/conftest.py)
- 父 issue / 关联：#632
- 依赖：#751

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-31 | 创建 | TBD |
```

**Changes made:**

1. **Line 9** — `../50-svc-reports/0751-reports-router-implementation.md` → `./0632-add-reports-api-router-with-all-endpoints.md`  
   The `50-svc-reports/` directory doesn't exist. The reports router implementation lives in `60-analytics/0632-add-reports-api-router-with-all-endpoints.md` (same directory, same topic).

2. **Line 10** — `[analytics 报表生成](TBD)` → `TBD - 待验证：analytics 报表生成相关 issue 编号待确认`  
   No existing file for "analytics 报表生成" was found; the `TBD` is a placeholder with no derivable target, so replaced with plain text per option (b).
