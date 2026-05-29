# 导入导出 API 路由 · 添加批量导入与导出端点

| 元数据 | 值 |
|---|---|
| Issue | #677 |
| 分类 | [70-platform](../README.md#12-分类总览) |
| 优先级 | 必做 |
| 工作量 | 2-3 工作日 |
| 依赖 | [0676-导入导出 Job 模型与 Service 层](../50-automation/0676-add-import-export-job-models-and-service-layer.md) |
| 启用后赋能 | [0686-自动化规则路由端点](../50-automation/0686-add-post-get-put-delete-automation-rules-router-endpoints.md), [0687-规则执行引擎与触发调度](../50-automation/0687-build-rule-execution-engine-and-trigger-dispatch.md) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

CRM 数据搬迁、客户数据批量录入、规则配置的导出备份均依赖手动 SQL 操作或管理员工具。当前后端没有统一的导入/导出 API：外部系统无法以编程方式向 CRM 批量写入数据，也无法将规则或配置导出到文件。使用 #676 已建好的 Job 模型与 Service 层，本板块为 API 层补全缺失的 HTTP 入口，使前后端和外部系统均可调用导入导出流程。

### 1.2 做完后

- **用户视角**：管理员可在 UI 上传 CSV/Excel 触发批量导入，查看导入进度与错误明细；也可发起数据导出并在有效期内下载文件包。无用户可见的底层变化 — 纯接口层实现。
- **开发者视角**：`src/api/routers/import_router.py` 与 `src/api/routers/export_router.py` 两个新 Router 挂载至 `main.py`，暴露 7 个端点。Service 层由 #676 提供，Router 仅负责参数解析、认证注入、ORM 序列化与响应包装。

### 1.3 不做什么（剔除）

- [ ] 导入文件解析逻辑（CSV/Excel parser）不在本板块 — 由 #676 Service 层提供，本板块仅调用其方法。
- [ ] 导出文件的实际生成（S3 / local storage write）不在本板块 — 本板块仅调用 #676 Service 层并返回签名 URL。
- [ ] 导入导出 Job 的删除 / 取消端点不在本板块。
- [ ] 前端 UI 不在本板块范围。

### 1.4 关键 KPI

- [端点可用性：7 个端点均返回正确 `{success, data}` 结构（200/422/401）]
- [单元测试：`PYTHONPATH=src pytest tests/unit/test_import_router.py tests/unit/test_export_router.py -v` → ≥ 14 passed]
- [集成测试：`PYTHONPATH=src pytest tests/integration/test_import_export_integration.py -v` → 全 passed]
- [Lint：`ruff check src/api/routers/import_router.py src/api/routers/export_router.py` → 0 errors]

---

## 2. 当前现状（起点）

### 2.1 现有实现

本板块为 #676 的下游，依赖其提供的 Job ORM 模型与 Service 层。Router 层的代码目前不存在（greenfield）。

TBD - 待验证：`src/api/routers/` 下现有路由文件列表与 `main.py` 中的 router 注册方式，以确认挂载路径前缀与标签命名规范。

参考已有 Router 实现：`src/api/routers/` 下任意现有 `.py` 文件（如 `customers.py` 或 `tickets.py`）的 `Depends(require_auth)` + `Depends(get_db)` 注入模式，以及 `{"success": True, "data": ...}` 响应包装格式。

### 2.2 涉及文件清单

- 要改：
  - [`src/main.py`](../../src/main.py) — 注册两个新 Router
- 要建：
  - `src/api/routers/import_router.py` — 5 个导入端点
  - `src/api/routers/export_router.py` — 2 个导出端点
  - `tests/unit/test_import_router.py` — 导入 Router 单元测试
  - `tests/unit/test_export_router.py` — 导出 Router 单元测试
  - `tests/integration/test_import_export_integration.py` — 导入导出集成测试

### 2.3 缺什么

- [ ] 导入上传端点 `POST /import/upload` — 接收文件 multipart/form-data，写入存储，调用 ImportService.create_job
- [ ] 导入校验端点 `POST /import/validate` — 触发 #676 ImportService.validate_job，返回校验错误列表
- [ ] 导入执行端点 `POST /import/execute` — 触发 #676 ImportService.execute_job
- [ ] 导入任务状态端点 `GET /import/jobs/{job_id}` — 查询 Job ORM 对象，序列化为 dict
- [ ] 导入任务错误明细端点 `GET /import/jobs/{job_id}/errors` — 分页返回 error rows
- [ ] 导出发起端点 `POST /export` — 触发 #676 ExportService.create_job，返回 job_id
- [ ] 导出下载端点 `GET /export/jobs/{job_id}/download` — 生成签名 URL（或内部路径 URL）
- [ ] 统一响应包装 `{success, data}` 与错误处理中间件的正确集成
- [ ] 所有端点的 `require_auth` 认证守卫与 `tenant_id` 注入

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `src/api/routers/import_router.py` | 5 个导入 REST 端点（upload/validate/execute/jobs/{id}/errors） |
| `src/api/routers/export_router.py` | 2 个导出 REST 端点（export/jobs/{id}/download） |
| `tests/unit/test_import_router.py` | import_router 单元测试（Mock AuthContext + MockService） |
| `tests/unit/test_export_router.py` | export_router 单元测试（Mock AuthContext + MockService） |
| `tests/integration/test_import_export_integration.py` | 端到端集成测试（real session + real service） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`src/main.py`](../../src/main.py) | 导入并挂载 `import_router`（prefix="/import"）与 `export_router`（prefix="/export"） |

### 3.3 新增能力

- **API endpoint**：`POST /import/upload` — multipart 文件上传 → `{"success": true, "data": {"job_id": 1}}`
- **API endpoint**：`POST /import/validate` — `{job_id, options}` → `{"success": true, "data": {"valid": false, "errors": [...]}}`
- **API endpoint**：`POST /import/execute` — `{job_id}` → `{"success": true, "data": {"job_id": 1}}`
- **API endpoint**：`GET /import/jobs/{job_id}` → `{"success": true, "data": {...job dict...}}`
- **API endpoint**：`GET /import/jobs/{job_id}/errors` → `{"success": true, "data": {"items": [...], "total": N}}`
- **API endpoint**：`POST /export` — `{entity_type, filters}` → `{"success": true, "data": {"job_id": 2}}`
- **API endpoint**：`GET /export/jobs/{job_id}/download` → `{"success": true, "data": {"url": "https://signed..."}}`
- **Router**：`import_router` / `export_router` — FastAPIAPIRouter，均挂载 `require_auth` 守卫

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **签名 URL 生成采用基础 URL + query param 签名，不引入额外 secret 存储库** → 规避：HMAC-SHA256(job_id + tenant_id + expiry，SECRET_KEY)，URL 有效期 15 分钟。理由：CRM 无独立对象存储服务，签名 URL 仅防未授权租户猜测 job_id；若将来引入 S3/GCS，可替换实现而不影响 Router 接口。
- **导入上传文件不直接落库，以 job_id + uuid 文件名存本地 tmp 目录或 object storage** → 规避：文件名 = `import_{tenant_id}_{job_id}_{uuid}.csv`。理由：避免大文件撑爆 DB；Job record 只存路径引用。
- **GET 端点（jobs/{id}, errors, download）使用 `Depends(require_auth)` + `tenant_id` 校验** → 规避：Job 查询必须 `WHERE tenant_id = :tenant_id`，防越权访问。理由：Job ID 无加密，恶意用户可枚举其他租户的 job。

### 4.2 版本约束

| 依赖 | 版本 | 理由 |
|------|------|------|
| `python-multipart` | `>=0.6.2` | FastAPI `UploadFile` 依赖，需在 `pyproject.toml` 声明 |

### 4.3 兼容性约束

- 多租户：每个 SQL / Service 查询必须 `WHERE tenant_id = :tenant_id`（已在 #676 Service 层保证，Router 调用时传参）
- Router 层使用 `session: AsyncSession = Depends(get_db)` 注入 session（不使用 `async with get_db()`）
- Router 不调用 `.to_dict()` — 由 Router 调用 Service 返回的 ORM 对象后执行序列化
- Router 错误不 try/catch — `AppException`（`NotFoundException`/`ValidationException`）由 `main.py` 全局中间件统一处理
- 响应结构：`{"success": true, "data": <dict|list>, "message": "..."}`，data 为 `to_dict()` 输出或数组

### 4.4 已知坑

1. **FastAPI `UploadFile` 需要 `python-multipart` 依赖** → 规避：在 `pyproject.toml` 的 `dependencies` 中添加 `python-multipart>=0.6.2`，运行 `pip install python-multipart`，避免部署时 500。
2. **SQLAlchemy Base 子类列名不能用 `metadata`（与 `Base.metadata` 冲突）** → 规避（已在 #676 模型层处理，本板块引用时注意）：若新增列避免用 `metadata`，用 `event_metadata` / `attrs` 等。
3. **Alembic autogenerate 对 JSONB 与 TIMESTAMPTZ 判断不准** → 规避（若本板块需额外 migration）：JSON 列手动改为 `sa.JSONB()`，DateTime 列检查 `timezone=True`。
4. **Router 参数 `job_id: int` 需做类型校验** → 规避：FastAPI 默认做类型校验，传入非整数返回 422，无需额外手动验证。
5. **导入执行 `POST /import/execute` 若文件已删除则需返回 409** → 规避：在 ImportService.execute_job 入口检查 `source_file_path` 存在，不存在则 raise `ConflictException`。

---

## 5. 实现步骤（按顺序）

### Step 1: 添加 python-multipart 依赖

在 `pyproject.toml` 的 `dependencies` 列表中添加 `python-multipart>=0.6.2`。FastAPI 的 `UploadFile` 类型依赖该包。

```toml
# pyproject.toml 片段
dependencies = [
    "fastapi>=0.110.0",
    "python-multipart>=0.6.2",   # 新增
    ...
]
```

**完成判定**：`grep -q "python-multipart" pyproject.toml` exit 0

---

### Step 2: 创建 import_router.py（5 个端点）

在 `src/api/routers/` 下新建 `import_router.py`，实现以下端点：

```python
# src/api/routers/import_router.py
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth

router = APIRouter(prefix="/import", tags=["Import"])

class ValidateRequest(BaseModel):
    job_id: int
    options: dict | None = None

class ExecuteRequest(BaseModel):
    job_id: int

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # 调用 ImportService.create_job(session, tenant_id=ctx.tenant_id, file=file)
    pass

@router.post("/validate")
async def validate_job(
    body: ValidateRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    pass

@router.post("/execute")
async def execute_job(
    body: ExecuteRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    pass

@router.get("/jobs/{job_id}")
async def get_job(
    job_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    pass

@router.get("/jobs/{job_id}/errors")
async def get_job_errors(
    job_id: int,
    page: int = 1,
    page_size: int = 20,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    pass
```

Service 调用占位 `#676 ImportService` — 实际 import 语句与调用参数待 #676 确定后填充。每个端点返回 `{"success": True, "data": <result>}`。

**完成判定**：`ruff check src/api/routers/import_router.py` exit 0；`python -c "from api.routers.import_router import router; print('ok')"` exit 0

---

### Step 3: 创建 export_router.py（2 个端点）

在 `src/api/routers/` 下新建 `export_router.py`，实现以下端点：

```python
# src/api/routers/export_router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from db.connection import get_db
from internal.middleware.fastapi_auth import AuthContext, require_auth

router = APIRouter(prefix="/export", tags=["Export"])

class CreateExportRequest(BaseModel):
    entity_type: str
    filters: dict | None = None

@router.post("")
async def create_export(
    body: CreateExportRequest,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # 调用 ExportService.create_job(session, tenant_id=ctx.tenant_id, ...)
    pass

@router.get("/jobs/{job_id}/download")
async def download_export(
    job_id: int,
    ctx: AuthContext = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # 调用 ExportService.get_signed_url(session, job_id=job_id, tenant_id=ctx.tenant_id)
    # 返回 {"url": "https://..."} 或内部 signed path
    pass
```

**完成判定**：`ruff check src/api/routers/export_router.py` exit 0；`python -c "from api.routers.export_router import router; print('ok')"` exit 0

---

### Step 4: 将两个 Router 注册到 main.py

在 `src/main.py` 中添加 import 并挂载：

```python
# src/main.py 片段
from api.routers import import_router, export_router

app = FastAPI(...)

app.include_router(import_router.router)
app.include_router(export_router.router)
```

**完成判定**：`ruff check src/main.py` exit 0；端点列表中出现 `/import/upload`、`/import/validate`、`/import/execute`、`/import/jobs/{id}`、`/import/jobs/{id}/errors`、`/export`、`/export/jobs/{id}/download`

---

### Step 5: 补充 import_router 端点实现

逐一填充 Step 2 中留空的端点实现：

`POST /import/upload`：接收 `UploadFile`，校验文件类型（`.csv` / `.xlsx`），调用 `ImportService.create_job`，返回 `{"success": True, "data": {"job_id": N}}`。

`POST /import/validate`：解析 body `{job_id, options}`，调用 `ImportService.validate_job`，返回校验结果。

`POST /import/execute`：解析 body `{job_id}`，调用 `ImportService.execute_job`，返回 `{"success": True, "data": {"job_id": N}}`。

`GET /import/jobs/{job_id}`：调用 `ImportService.get_job(job_id, tenant_id=ctx.tenant_id)`，返回 `entity.to_dict()` 包装。

`GET /import/jobs/{job_id}/errors`：调用 `ImportService.get_job_errors(job_id, tenant_id, page, page_size)`，返回分页 items + total。

所有端点的 session 注入使用 `session: AsyncSession = Depends(get_db)`，不手动管理 session 生命周期。

**完成判定**：`ruff check src/api/routers/import_router.py` exit 0；所有 5 个端点函数体无 `pass`

---

### Step 6: 补充 export_router 端点实现

逐一填充 Step 3 中留空的端点实现：

`POST /export`：解析 body `{entity_type, filters}`，调用 `ExportService.create_job`，返回 `{"success": True, "data": {"job_id": N}}`。

`GET /export/jobs/{job_id}/download`：调用 `ExportService.get_signed_url`，返回 `{"success": True, "data": {"url": "<signed>"}}`。签名逻辑采用 HMAC-SHA256(job_id + tenant_id + expiry, SECRET_KEY)，URL 有效期 15 分钟，query 参数附上 `expires` 与 `sig`。

**完成判定**：`ruff check src/api/routers/export_router.py` exit 0；所有 2 个端点函数体无 `pass`

---

### Step 7: 编写单元测试

`tests/unit/test_import_router.py`：Mock `require_auth`（注入固定 `AuthContext(tenant_id=1)`），Mock `get_db`（返回 mock session），Mock `ImportService` 各方法。使用 `TestClient`（同步）或 `httpx.AsyncClient`（异步）测试各端点返回码与响应结构。

`tests/unit/test_export_router.py`：Mock `require_auth` + `ExportService`，测试 signed URL 格式、`/export/jobs/{id}/download` 404（job 不存在）与 403（tenant 不匹配）场景。

```python
# tests/unit/test_import_router.py 片段
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app
from api.routers.import_router import router

@pytest.fixture
def client():
    app.include_router(router)
    with TestClient(app) as c:
        yield c

def test_upload_file_returns_job_id(client, monkeypatch):
    # Mock require_auth
    # Mock ImportService.create_job → return ImportJobModel(id=5, ...)
    # POST /import/upload with dummy file
    # assert response.status_code == 200
    # assert response.json()["success"] == True
    # assert "job_id" in response.json()["data"]
    pass
```

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_import_router.py tests/unit/test_export_router.py -v` → ≥ 14 passed

---

### Step 8: 编写集成测试

`tests/integration/test_import_export_integration.py`：使用 `db_schema` fixture（TRUNCATE CASCADE between tests），调用真实 `ImportService` + `ExportService`，验证端到端流程（上传 → 校验 → 执行 → 查状态 → 错误列表）。

```python
# tests/integration/test_import_export_integration.py 片段
@pytest.mark.integration
class TestImportRouterIntegration:
    async def test_upload_validate_execute_flow(
        self, db_schema, tenant_id, async_session
    ):
        import_sv = ImportService(async_session)
        # 创建 upload 文件
        # upload → assert job.status == "pending"
        # validate → assert job.status == "validated" or errors present
        # execute → assert job.status == "completed"
        pass

    async def test_get_job_not_found(self, db_schema, tenant_id, async_session):
        import_sv = ImportService(async_session)
        with pytest.raises(NotFoundException):
            await import_sv.get_job(99999, tenant_id=tenant_id)
```

**完成判定**：`PYTHONPATH=src pytest tests/integration/test_import_export_integration.py -v` → 全 passed

---

## 6. 验收

- [ ] `ruff check src/api/routers/import_router.py src/api/routers/export_router.py src/main.py` → 0 errors
- [ ] `PYTHONPATH=src pytest tests/unit/test_import_router.py tests/unit/test_export_router.py -v` → ≥ 14 passed
- [ ] `PYTHONPATH=src pytest tests/integration/test_import_export_integration.py -v` → 全 passed
- [ ] 端到端：`curl -s -X POST http://localhost:8000/import/upload -F "file=@/tmp/test.csv"` 返回 `{"success": true, "data": {"job_id": ...}}`
- [ ] 端到端：`curl -s http://localhost:8000/import/jobs/1` 返回 `{"success": true, "data": {...}}`
- [ ] 端到端：`curl -s http://localhost:8000/export/jobs/1/download` 返回 `{"success": true, "data": {"url": "..."}}`（URL 含 sig 与 expires 参数）

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| #676 ImportService/ExportService 接口与本板块假设不一致导致大量返工 | 中 | 中 | 在 Step 5-6 实施前与 #676 负责人确认 Service 方法签名；若接口变更，Router 层调整成本 ≤ 2h |
| 签名 URL 在无对象存储环境下无效（仅返回内部路径） | 低 | 低 | export download 端点降级为返回本地 `/tmp/export_{job_id}.csv` 的相对路径，UI 层处理下载 |
| 大文件上传超时（FastAPI 默认无限制，需配置 `max_upload_size`） | 低 | 中 | 添加 `FileUploadSettings`（max_file_size_mb），超限返回 413；文档说明推荐 < 50MB |
| Job 记录跨租户泄露（job_id 枚举攻击） | 低 | 高 | 所有 GET 端点强制 `WHERE tenant_id = :tenant_id`；Service 层已保证，Router 层确认每调用都传 `ctx.tenant_id` |

---

## 8. 完成后必做

```bash
# 1. commit + PR
git add src/api/routers/import_router.py src/api/routers/export_router.py \
       src/main.py tests/unit/test_import_router.py tests/unit/test_export_router.py \
       tests/integration/test_import_export_integration.py pyproject.toml
git commit -m "feat(platform): add import/export API routers (closes #677)"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(platform): add import/export API routers (#677)" \
  --body "Closes #677

## Summary
- POST /import/upload, /import/validate, /import/execute
- GET /import/jobs/{job_id}, GET /import/jobs/{job_id}/errors
- POST /export
- GET /export/jobs/{job_id}/download (HMAC-signed URL)

## Test plan
- [x] ruff check — 0 errors
- [x] unit tests ≥ 14 passed
- [x] integration tests passed
- [x] end-to-end curl smoke"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR 合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD - 待验证：`src/api/routers/` 下已有 Router 的认证注入与响应包装模式
- 父 issue / 关联：#34（父 Epic），#676（依赖：Job 模型与 Service 层），#677（本板块）
- 第三方文档：[FastAPI UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/), [SQLAlchemy 2.x async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
