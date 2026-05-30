# src/services/enrichment_service.py
import os
from sqlalchemy.ext.asyncio import AsyncSession
from pkg.errors.app_exceptions import ValidationException

CLEARBIT_BASE = "https://company.clearbit.com/v2/companies/find"


class EnrichmentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lookup(self, domain: str, provider: str = "clearbit") -> dict:
        api_key = os.environ.get("CLEARBIT_API_KEY")
        if not api_key:
            raise ValidationException("CLEARBIT_API_KEY environment variable is not set")
        if provider != "clearbit":
            raise ValidationException(f"Unsupported enrichment provider: {provider}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{CLEARBIT_BASE}?domain={domain}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if not resp.is_success:
            raise ValidationException(f"Clearbit API error: {resp.status_code} {resp.text}")
        raw = resp.json()
        return {
            "name": raw.get("name"),
            "domain": raw.get("domain"),
            "industry": raw.get("category", {}).get("industry"),
            "employees": raw.get("metrics", {}).get("employees"),
            "logo": raw.get("logo"),
        }
```

**完成判定**：`ruff check src/services/enrichment_service.py` →0 errors

---

### Step 2: Add `POST /api/v1/enrichment/lookup` router

Create `src/api/routers/enrichment.py`. Use `from api.routers.enrichment import router as enrichment_router`. Implement `POST /lookup` that accepts a `BaseModel` body with optional `domain: str | None` and `company_name: str | None`. Require at least one of the two fields; raise `ValidationException` if neither is provided. Extract `domain` for the Clearbit call. Return `{"success": True, "data": result}`. Mount the router at `/api/v1/enrichment` in `src/main.py`.

在 `src/main.py` 中 mount：
```python
from src.api.routers import enrichment as enrichment_router
app.include_router(enrichment_router.router, prefix="/api/v1/enrichment", tags=["Enrichment"])
```

**完成判定**：`ruff check src/api/routers/enrichment.py` → 0 errors；grep确认 `main.py` 已添加 router

---

### Step 3: Write unit tests `tests/unit/test_enrichment_service.py`

Create `tests/unit/test_enrichment_service.py` using `pytest-asyncio`. Use `respx` or `httpx_mock` to mock responses. Test cases:

1. `test_lookup_success` — mocked 200 from Clearbit with full response shape; asserts returned dict has `name`, `domain`, `industry`, `employees`, `logo`.
2. `test_lookup_http_error` — mocked 401 from Clearbit; asserts `ValidationException` is raised.
3. `test_lookup_missing_api_key` — unset `CLEARBIT_API_KEY` env var before call; asserts `ValidationException` with message about missing key.
4. `test_lookup_unsupported_provider` — provider=`"apollo"`; asserts `ValidationException`.
5. `test_lookup_no_domain_or_company_name` — body with neither field; asserts `ValidationException` from router handler (test router + service integration via fixture).

Use `make_mock_session` helpers from `conftest.py` if the service needs a session bound.

**完成判定**：`PYTHONPATH=src pytest tests/unit/test_enrichment_service.py -v` → ≥ 5 passed

---

### Step 4: Verify router mounts cleanly

Confirm that `src/main.py` includes the `enrichment_router` and that the app starts without import errors:

`PYTHONPATH=src python -c "from src.main import app; print('OK')"` → `OK`

Run the full lint gate:

`ruff check src/services/enrichment_service.py src/api/routers/enrichment.py main.py` →0 errors

**完成判定**：`python -c "from src.main import app; print('OK')"` exits 0

---

## 6. 验收

- [ ] `ruff check src/services/enrichment_service.py src/api/routers/enrichment.py` → 0 errors
- [ ] `ruff check src/main.py` → 0 errors (only if `main.py` was touched)
- [ ] `PYTHONPATH=src pytest tests/unit/test_enrichment_service.py -v` → 全 passed (≥ 5 passed)
- [ ] `PYTHONPATH=src python -c "from src.main import app; print('OK')"` → OK (exit 0)
- [ ] EnrichmentService imports without error: `PYTHONPATH=src python -c "from src.services.enrichment_service import EnrichmentService; print('OK')"` → OK
- [ ] Router file imports without error: `PYTHONPATH=src python -c "from src.api.routers.enrichment import router; print('OK')"` → OK

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| Clearbit API key exposed in env var logs | 中 | 高 | Revert the env var read in service; store key in vault-backed secrets manager; `CLEARBIT_API_KEY` is not persisted to DB so no migration rollback needed |
| Clearbit pricing / rate-limit changes break enrichment | 低 | 中 | Wrap the provider in a `feature_flag` guard; when Clearbit fails, return `{"error": "enrichment temporarily unavailable"}` rather than 500, keeping downstream graceful |
| Unit test mocks diverge from live API schema | 中 | 低 | When Clearbit adds/removes fields, `test_enrichment_service.py` will fail before prod; update mocks and normalize dict shape — no DB migration required |

---

## 8. 完成后必做```bash
# 1. commit + PR
git add src/services/enrichment_service.py src/api/routers/enrichment.py tests/unit/test_enrichment_service.py src/main.py
git commit -m "feat(enrichment): add EnrichmentService with Clearbit provider and lookup endpointCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push -u origin "$(git branch --show-current)"
gh pr create --base master --title "feat(#511): EnrichmentService with Clearbit" --body "Closes #511

## What
- `EnrichmentService.lookup(domain, provider)` calls Clearbit API, normalizes response to dict
- `POST /api/v1/enrichment/lookup` accepts domain or company_name, returns enriched fields
- Unit tests with mocked HTTP responses covering success and error paths

## Test plan
- [ ] ruff check src/services/enrichment_service.py src/api/routers/enrichment.py → 0 errors
- [ ] PYTHONPATH=src pytest tests/unit/test_enrichment_service.py -v → ≥ 5 passed- [ ] PYTHONPATH=src python -c \"from src.main import app; print('OK')\" → OK"

# 2. 更新进度
# - 在本板块文档 §Changelog 表格新增一行
# - PR合并后 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块由 generator 自动更新
```

---

## 9. 参考

- 同类参考实现：TBD — 待验证：`src/services/<现有 external-API 调用 service>` — grep `httpx.AsyncClient` 在 services 中的使用模式
- 第三方文档：[Clearbit Company API](https://clearbit.com/docs#company-api) — v2 endpoint shape, auth header format, rate-limit notes
- 父 issue：#74- 关联依赖：#510 — Company domain schema and seed data (upstream prerequisite for domain availability)

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| YYYY-MM-DD | 创建 | TBD |
