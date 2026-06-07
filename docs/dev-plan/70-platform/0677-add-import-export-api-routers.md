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
- [ ] 端到端：`curl -s http://localhost:8000/export/jobs/1/download` 返回 `{"success": true, "data": {"url": "..."}}`

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
