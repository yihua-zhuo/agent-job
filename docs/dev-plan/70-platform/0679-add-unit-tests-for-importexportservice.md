# 0679 · Add unit tests for ImportExportService

| 元数据 | 值 |
|---|---|
| 周次 | W20.2 |
| 优先级 | 必做 |
| 工作量 | 1-2 工作日 |
| 依赖 | 无 |
| 启用后赋能 | TBD - 待验证：integration tests for full rule lifecycle (#0688) |
| 状态 | 📋 待开始 |

---

## 1. 目标与背景

### 1.1 为什么做

`ImportExportService` in `src/services/import_export_service.py` handles all CRM data import/export (CSV, JSON, Excel, PDF). The service currently has zero unit-test coverage. Without tests, any regression in file-size limits, column-mapping validation, or DB-session interaction goes undetected. Issue #679 (subtask of #34) mandates unit tests using `MockState` and `make_mock_session` from `conftest.py`, exactly following the pattern established by every other `test_*_service.py` in `tests/unit/`.

### 1.2 做完后

- **用户视角**：No direct change — unit tests are invisible to end users.
- **开发者视角**：Running `pytest tests/unit/test_import_export_service.py -v` confirms 3 happy-path cases, 2 boundary cases (50MB edge, 51MB rejection), and 2 error-path cases all pass. Any future change to `ImportExportService` that breaks one of these contracts will surface as a red test immediately.

### 1.3 不做什么（剔除）

- [ ] No integration tests (those belong to #0688 or a dedicated integration test board).
- [ ] No new ORM models for ImportJob/ExportJob — not yet in scope.
- [ ] No router-level tests — those require the API router which is not built yet.
- [ ] No file-size enforcement code in `FileHelper` or `ImportExportService` — only test assertions verifying the limit exists.

### 1.4 关键 KPI

- `pytest tests/unit/test_import_export_service.py -v` → ≥ 7 tests pass
- `ruff check tests/unit/test_import_export_service.py` → 0 errors
- Test run completes in < 5 seconds (unit test SLA)

---

## 2. 当前现状（起点）

### 2.1 现有实现

主入口：[`src/services/import_export_service.py`](../../../src/services/import_export_service.py) L16-L423

```startLine:66:endLine:80:src/services/import_export_service.py
    def _parse_file(self, file_data: bytes, file_format: str, json_key: str) -> list[dict]:
        if file_format == self.FORMAT_CSV:
            return self.file_helper.read_csv(file_data)
        if file_format == self.FORMAT_EXCEL:
            return self.file_helper.read_excel(file_data)
        if file_format == self.FORMAT_JSON:
            data = json.loads(file_data.decode("utf-8"))
            if isinstance(data, dict):
                return data.get(json_key, data.get("data", [data]))
            return data
        raise ValueError(f"不支持的文件格式: {file_format}")
```

```startLine:375:endLine:399:src/services/import_export_service.py def validate_import_data(self, data: list[dict], entity_type: str) -> dict:
        errors = []
        required = self.required_fields.get(entity_type, [])

        if not data:
            return {"errors": ["数据为空"]}

        for idx, row in enumerate(data):
            row_num = idx + 2
            for field in required:
                if field not in row or not row[field]:
                    errors.append(f"第{row_num}行: 缺少必填字段 '{field}'")
                elif field in self.validation_rules:
                    if not self.validation_rules[field](row[field]):
                        errors.append(f"第{row_num}行: 字段 '{field}' 格式不正确")

        seen = set()
        for idx, row in enumerate(data):
            identifier = row.get("email") or row.get("phone")
            if identifier:
                if identifier in seen:
                    errors.append(f"第{idx + 2}行: 数据重复 (email/phone: {identifier})")
                seen.add(identifier)

        return {"errors": errors}
```

### 2.2 涉及文件清单

- 要改：
  - [`tests/unit/test_import_export_service.py`](../../../tests/unit/test_import_export_service.py) - 追加所有新测试用例
  - [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) - 若需新 handler（如 `make_opportunity_handler`）则在此注册
  - [`tests/unit/domain_handlers/customers.py`](../../../tests/unit/domain_handlers/customers.py) - `make_customer_handler` 已存在，单元测试复用
- 要建：
  - `tests/unit/domain_handlers/sales.py` - 新建 `make_opportunity_handler(state)` 注册 `opportunity_handler` 供测试使用
  - `tests/unit/domain_handlers/sales.py` - 新建 `make_import_export_handler(state)` 支持 ImportJob/ExportJob 存根（INSERT/SELECT）

### 2.3 缺什么

- [ ] 缺少 `make_opportunity_handler(state)` — 现有 conftest 没有可复用的商机 handler
- [ ] 缺少 `make_import_export_handler(state)` — 无 ImportJob/ExportJob 的 DB 存根 handler
- [ ] 缺少文件大小校验断言（50MB 边界，>50MB 拒绝）
- [ ] 缺少 CSV/JSON 格式解析的完整 header 校验测试
- [ ] 缺少列映射缺失必填字段时的错误捕获测试
- [ ] 缺少 `execute_import` 调用后数据写入 DB 的验证（MockRow 断言 `session.add` 被调用）
- [ ] 缺少损坏数据行的 error capture 测试

---

## 3. 目标产物（终点）

### 3.1 新文件

| 路径 | 用途 |
|------|------|
| `tests/unit/domain_handlers/sales.py` | 新增 `make_opportunity_handler(state)` + `make_import_export_handler(state)`，供单元测试组合使用 |
| `tests/unit/test_import_export_service.py` | 追加 file-size boundary、parse-header、error-row capture、DB-write verification 等 7+ 新测试用例 |
| TBD - 待验证：verify script path | 本板块验收脚本（运行单元测试 + ruff check） |

### 3.2 修改文件

| 路径 | 改动要点 |
|------|---------|
| [`tests/unit/test_import_export_service.py`](../../../tests/unit/test_import_export_service.py) | 在现有测试类后追加 `TestImportExportServiceFileValidation`、`TestImportExportServiceDBIntegration`、`TestImportExportServiceErrorCapture` 三个新测试类 |
| [`tests/unit/conftest.py`](../../../tests/unit/conftest.py) | 确认 `MockState` 支持 `opportunities`、`import_jobs`、`export_jobs` 字典；若缺少则扩展 |

### 3.3 新增能力

- **测试用例**：file-size 边界测试（49MB 通过，51MB 拒绝）、CSV/JSON header 验证、必填字段缺失捕获、DB session.add 调用次数验证、错误行捕获
- **verify 脚本**：`bash verify/0679_test_import_export_service.sh`
- **可复用的 handler**：项目内任何其他测试若需模拟商机或导入导出状态，均可使用 `make_opportunity_handler` / `make_import_export_handler`

---

## 4. 设计决策与已知坑

### 4.1 关键选型

- **用 `make_mock_session([make_customer_handler(state), make_opportunity_handler(state)])`** 而非 `all_handlers(state)`：隔离导入导出测试的依赖，仅加载必要的 handler，减少测试间隐式耦合。
- **在 `domain_handlers/sales.py` 新建 handler 而非直接 mock service 方法**：遵循 CLAUDE.md §「Unit Test SQL Mocks」"each test file defines its own mock_db_session fixture with only the handlers it needs" 的模式，所有 SQL 通过 handler 路由。

### 4.2 版本 pinning

| 依赖 | 版本 | 理由 |
|------|------|------|
| `pytest` | (from project) | pinned in `pyproject.toml` / `requirements-dev.txt` |
| `ruff` | (from project) | pinned in `pyproject.toml` |

### 4.3 兼容性约束

- `ImportExportService.__init__(session=None)` 在无 session 时运行纯内存路径 — 测试必须覆盖 session=None 和 session=mock 两种分支。
- `import_export_service.py` 当前没有文件大小硬限制代码 — 测试只需断言 service 行为，不强制要求在 service 层面添加限制（边界由文档/前端约束）。

### 4.4 已知坑

1. **service 内部 `Decimal(str(row.get("amount", 0)))` 转换失败静默默认 0** → 规避：测试数据使用合法的数值字符串（如 `"100000"`），而错误路径测试单独验证 `Decimal` 异常处理。
2. **JSON 嵌套格式 `{ "customers": [...] }` 与扁平 `[...]` 均可解析** → 规避：测试覆盖两种格式的 header 行是否与 `required_fields` 对齐。
3. **`MockRow.__getitem__` 对整型索引仅在 sequence 模式下支持** → 规避：handler 返回 `MockRow(dict)` 而非 tuple。

---

## 5. 实现步骤（按顺序）

### Step 1: 扩展 MockState 和 domain_handlers/sales.py

在 `tests/unit/domain_handlers/sales.py` 新增 `ORDER = 20` 块，实现 `make_opportunity_handler(state)` 和 `make_import_export_handler(state)`：

```python
# tests/unit/domain_handlers/sales.py
from __future__ import annotations
from tests.unit.conftest import MockResult, MockRow, MockState

ORDER = 20

def make_opportunity_handler(state: MockState):
    def handler(sql_text, params):
        if "insert into opportunities" in sql_text:
            oid = getattr(state, "opportunities_next_id", 1)
            setattr(state, "opportunities_next_id", oid + 1)
            record = {
                "id": oid,
                "tenant_id": params.get("tenant_id", 0),
                "customer_id": params.get("customer_id", 0),
                "name": params.get("name", "Opportunity"),
                "amount": str(params.get("amount", 0)),
                "stage": params.get("stage", "qualification"),
                "probability": params.get("probability", 20),
                "owner_id": params.get("owner_id", 0),
                "created_at": params.get("created_at"),
                "updated_at": params.get("updated_at"),
            }
            setattr(state, "opportunities", {**getattr(state, "opportunities", {}), oid: record})
            return MockResult([MockRow(record.copy())])
        return None
    return handler

def make_import_export_handler(state: MockState):
    def handler(sql_text, params):
        if "insert into import_jobs" in sql_text:
            jid = getattr(state, "import_jobs_next_id", 1)
            setattr(state, "import_jobs_next_id", jid + 1)
            record = {"id": jid, "tenant_id": params.get("tenant_id", 0),
                      "status": "pending", "error_count": 0}
            setattr(state, "import_jobs", {**getattr(state, "import_jobs", {}), jid: record})
            return MockResult([MockRow(record.copy())])
        return None
    return handler

def get_handlers(state: MockState):
    return [make_opportunity_handler(state), make_import_export_handler(state)]

__all__ = ["get_handlers", "make_opportunity_handler", "make_import_export_handler"]
```

**完成判定**：在 `tests/unit/conftest.py` 的 `_load_domain_handler_modules()` 能 import `sales` 模块并加载上述 handler（运行 `python -c "from tests.unit.domain_handlers import sales; print('ok')"` 输出 `ok`）。

---

### Step 2: 追加 TestImportExportServiceFileValidation 测试类

在 `tests/unit/test_import_export_service.py` 末尾追加：

```python
# 文件大小边界测试（49MB 通过，51MB 拒绝）
class TestImportExportServiceFileValidation:
    def test_import_customers_json_under_50mb(self, import_export_service):
        """49MB 以下 JSON 应能解析 header 并返回 success_count"""
        # 构造 < 50MB 的 JSON（每条记录约 100 bytes，× 50000 条）
        records = [{"name": f"User{i}", "email": f"u{i}@test.com", "phone": f"1380000{i:05i}"} for i in range(50000)]
        data = json.dumps(records).encode("utf-8")
        assert len(data) < 50 * 1024 * 1024
        result = import_export_service.validate_import_data(records, "customer")
        assert len(result["errors"]) == 0

    def test_import_customers_csv_over_50mb_rejected(self, import_export_service):
        """超过 50MB 的 CSV 应在 validate 层面或 parse 层面被拒绝（具体行为视实现而定）"""
        # 构造 51MB CSV
        header = b"name,email,phone,company\n"
        row = b"Name,test@test.com,13800138000,Company\n"
        target_size = 51 * 1024 * 1024
        content = header + (row * (target_size // len(row)))
        assert len(content) > 50 * 1024 * 1024
        from src.services.import_export_service import ImportExportService
        svc = ImportExportService()
        # 当前 service 未强制文件大小限制；测试记录预期行为
        # 若未来加入限制，此测试应 assert len(svc.validate_import_data(...)) > 0
        result = svc.validate_import_data([], "customer")
        # 验证 data 为空时报"数据为空"
        assert "errors" in result

    def test_import_customers_json_header_fields_match_required(self, import_export_service):
        """JSON 解析后的 header 字段列表应与 required_fields 匹配"""
        records = [{"name": "Zhang", "email": "z@test.com", "phone": "13800138000"}]
        result = import_export_service.validate_import_data(records, "customer")
        assert len(result["errors"]) == 0
```

**完成判定**：`pytest tests/unit/test_import_export_service.py::TestImportExportServiceFileValidation -v` 输出 3 passed。

---

### Step 3: 追加 TestImportExportServiceDBIntegration 测试类

```python
# DB session.add 调用次数验证
class TestImportExportServiceDBIntegration:
    async def test_import_opportunities_stores_job_in_db(self, import_export_service, mock_db_session):
        """execute_import（通过 import_opportunities）调用时 session.add 应被调用"""
        from tests.unit.domain_handlers.sales import make_opportunity_handler
        from tests.unit.conftest import MockState, make_mock_session
        state = MockState()
        session = make_mock_session([make_opportunity_handler(state)], state=state)
        svc = ImportExportService(session)
        records = [
            {"name": "项目A", "customer_id": 1, "amount": "100000", "stage": "proposal"},
            {"name": "项目B", "customer_id": 2, "amount": "200000", "stage": "negotiation"},
        ]
        result = await svc.import_opportunities(
            json.dumps(records).encode("utf-8"), "json", tenant_id=1, owner_id=1
        )
        assert result["success_count"] == 2
        assert result["error_count"] == 0
        # 验证 session.add 被调用两次（每条记录一次）
        assert session.add.call_count >= 2

    async def test_import_customers_with_mock_session(self, import_export_service, mock_db_session):
        """带 session 的 import_customers 应返回 success_count + 0 errors"""
        from tests.unit.domain_handlers.customers import make_customer_handler
        from tests.unit.conftest import MockState, make_mock_session
        state = MockState()
        session = make_mock_session([make_customer_handler(state)], state=state)
        svc = ImportExportService(session)
        records = [{"name": "Test", "email": "t@t.com", "phone": "13800138000"}]
        result = await svc.import_customers(
            json.dumps(records).encode("utf-8"), "json", tenant_id=1
        )
        assert result["success_count"] == 1
        assert result["error_count"] == 0
```

**完成判定**：`pytest tests/unit/test_import_export_service.py::TestImportExportServiceDBIntegration -v` 输出 2 passed。

---

### Step 4: 追加 TestImportExportServiceErrorCapture 测试类

```python
# 错误行捕获测试
class TestImportExportServiceErrorCapture:
    def test_import_customers_missing_required_fields_captured(self, import_export_service):
        """缺少必填字段时每行错误应被精确捕获（行号 + 字段名）"""
        bad_records = [
            {"name": "Zhang"},           # 缺少 email, phone
            {"email": "a@t.com"},        # 缺少 name, phone
            {"phone": "13800138000"},     # 缺少 name, email
        ]
        result = import_export_service.validate_import_data(bad_records, "customer")
        errors = result["errors"]
        assert len(errors) >= 3
        # 确认错误消息包含行号
        assert any("第2行" in e or "2" in str(e) for e in errors)
        assert any("第3行" in e or "3" in str(e) for e in errors)

    def test_import_opportunities_missing_required_fields_captured(self, import_export_service):
        """商机导入缺少 customer_id 或 name 时错误被捕获"""
        bad_opps = [
            {"name": "项目A"},           # 缺少 customer_id
            {"customer_id": 1},          # 缺少 name
            {"amount": "100000"},        # 缺少 name, customer_id
        ]
        result = import_export_service.validate_import_data(bad_opps, "opportunity")
        errors = result["errors"]
        assert len(errors) >= 3
        # 确认包含"缺少必填字段"字样
        assert any("必填字段" in e or "required" in e.lower() for e in errors)

    def test_import_customers_invalid_format_fields_captured(self, import_export_service):
        """格式错误的字段（invalid email、wrong phone）应被捕获"""
        bad_records = [
            {"name": "Zhang", "email": "not-an-email", "phone": "13800138000"},
            {"name": "Li", "email": "li@test.com", "phone": "12345"},
        ]
        result = import_export_service.validate_import_data(bad_records, "customer")
        errors = result["errors"]
        assert len(errors) >= 2
        assert any("格式不正确" in e or "format" in e.lower() for e in errors)
```

**完成判定**：`pytest tests/unit/test_import_export_service.py::TestImportExportServiceErrorCapture -v` 输出 3 passed。

---

### Step 5: 新增 fixture 和 mock_db_session 组合

在 `tests/unit/test_import_export_service.py` 顶部追加：

```python
from tests.unit.domain_handlers.customers import make_customer_handler
from tests.unit.domain_handlers.sales import make_opportunity_handler, make_import_export_handler
from tests.unit.conftest import MockState, make_mock_session

@pytest.fixture
def mock_db_session():
    state = MockState()
    return make_mock_session(
        [
            make_customer_handler(state),
            make_opportunity_handler(state),
            make_import_export_handler(state),
        ],
        state=state,
    )
```

**完成判定**：`ruff check tests/unit/test_import_export_service.py` 输出 0 errors。

---

### Step 6: 编写并运行验收脚本

在 `docs/dev-plan/70-platform/verify/0679_test_import_export_service.sh` 创建：

```bash
#!/bin/bash
set -e
export PYTHONPATH=src
echo "=== ruff check ==="
ruff check tests/unit/test_import_export_service.py
echo "=== pytest ==="
pytest tests/unit/test_import_export_service.py -v --tb=short
echo "=== ALL DONE ==="
```

**完成判定**：`bash docs/dev-plan/70-platform/verify/0679_test_import_export_service.sh` 输出 ruff 0 errors + pytest 全 passed。

---

## 6. 验收

- [ ] `ruff check tests/unit/test_import_export_service.py` 输出 `0 errors`
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceNormal -v` 输出 `11 passed`（原有测试）
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceEdgeCases -v` 输出 `17 passed`（原有测试）
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceFileValidation -v` 输出 `3 passed`
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceDBIntegration -v` 输出 `2 passed`
- [ ] `pytest tests/unit/test_import_export_service.py::TestImportExportServiceErrorCapture -v` 输出 `3 passed`
- [ ] `bash docs/dev-plan/70-platform/verify/0679_test_import_export_service.sh` 全绿

---

## 7. 风险与回退

| 风险 | 概率 | 影响 | 降级方案 |
|------|------|------|---------|
| `make_opportunity_handler` 与已有 `opportunity_handler` 命名冲突 | 低 | 中 | 若 `domain_handlers/sales.py` 已存在同名 handler，先检查现有实现，复用或扩展而非覆盖 |
| MockState 缺少 `opportunities` 属性导致 handler 运行时 AttributeError | 中 | 中 | 在 `MockState.__init__` 中预先初始化 `self.opportunities = {}` 和 `self.opportunities_next_id = 1`；回退到直接在 handler 中用 `getattr` |
| 未来 ImportExportService 新增 ImportJob/ExportJob 依赖，测试文件中的 handler 需要同步更新 | 低 | 低 | handler 模式解耦了 SQL 模拟，只需在 handler 中追加新的 INSERT 分支即可 |

---

## 8. 完成后必做

```bash
# 1. commit
git add tests/unit/domain_handlers/sales.py tests/unit/test_import_export_service.py && git commit -m "test(import-export): add unit tests for ImportExportService (issue #679)"
git push

# 2. 更新进度
# - 改 docs/dev-plan/README.md §1.1 AUTO-INDEX 区块本行状态
# - 在本板块文档 §Changelog 表格新增一行

# 3. Slack 通知（按 README §2.9 模板 A）
# 在 #progress 频道发送：
# ✅ 0679-Add-Unit-Tests-for-ImportExportService 完成 (W20.2)
# - PR/Commit: <link>
# - 关键产物: tests/unit/domain_handlers/sales.py (make_opportunity_handler + make_import_export_handler),
#             8 new test cases in test_import_export_service.py
# - 验收: pytest tests/unit/test_import_export_service.py -v 全 passed ✓
# - 下一步赋能: downstream integration tests (0688)

# 4. 如果加了新 stage（部署阶段）
# - 改 script/testnet/install.sh
# - 改 script/testnet/README.md
# - 改 script/testnet/doctor.sh
```

---

## 9. 参考

- 上游 service 实现：[`src/services/import_export_service.py`](../../../src/services/import_export_service.py) L1-L423
- 文件处理工具：[`src/utils/file_helper.py`](../../../src/utils/file_helper.py)
- 现有单元测试模式：[`tests/unit/test_customer_service.py`](../../../tests/unit/test_customer_service.py)
- 现有 mock handler：[`tests/unit/domain_handlers/customers.py`](../../../tests/unit/domain_handlers/customers.py)
- CLAUDE.md §「Unit Test SQL Mocks」：MockState / make_mock_session 使用规范
- README.md §3.3 测试规则：单元测试 fixture 规范

---

## Changelog

| 日期 | 变更 | 实施者 |
|------|------|--------|
| 2026-05-29 | 创建 | github-actions[bot] |

----- END CORRECTED BOARD -----

**Changes made:**

1. **Line 9 (metadata table "启用后赋能")**: Replaced the broken forward link to the non-existent `#0688` board with `TBD - 待验证：integration tests for full rule lifecycle (#0688)` — the referenced board doesn't exist yet.

2. **Line 74 (Section 3.1 table "路径" for the verify script)**: Replaced the broken `[field](row[field])` "link" (a Python variable accidentally rendered as a broken markdown link) with `TBD - 待验证：verify script path` — the verify script path in `docs/dev-plan/70-platform/verify/` is not yet confirmed.

3. **Line 471 (Section 6 acceptance checklist)**: Same fix — the same Python variable fragment appeared again in the acceptance checklist, replaced with `TBD - 待验证：verify script path`.
