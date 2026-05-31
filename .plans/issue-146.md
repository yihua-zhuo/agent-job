Now I have a thorough picture of both files. Let me write the plan.

---

# Implementation Plan — Issue #146

## Goal
Complete `tests/unit/test_import_export_service.py` by adding missing assertions in an existing test, adding new validation tests, export tests, and error-path tests that align with the actual behavior of `src/services/import_export_service.py`.

## Affected Files
- `tests/unit/test_import_export_service.py` — add assertion, add 8 new test methods
- `tests/unit/conftest.py` — no changes needed (PYTHONPATH already configured at line 32–35)

## Implementation Steps

1. **Fix `test_generate_pdf_report`** (line 93–104): after existing two assertions (`assert isinstance(result, bytes)` and `assert len(result) > 0`), append a combined assertion: `assert isinstance(result, bytes) and len(result) > 0`.

2. **Add `test_validate_import_data_success`** inside `TestImportExportServiceNormal`: call `validate_import_data(sample_customer_data, "customer")`, assert `result["valid_count"] == 2` (or `len(data) - len(result["errors"]) == 2`) and `result["invalid_count"] == 0`. Fall back to asserting `len(result["errors"]) == 0` if `valid_count`/`invalid_count` are not part of the return dict — check `validate_import_data` return shape first (it returns `{"errors": [...]}`). Use `sample_customer_data` fixture.

3. **Add `test_validate_import_data_with_invalid_rows`** inside `TestImportExportServiceNormal`: construct a list with one valid row and one row missing the "email" required field, call `validate_import_data(mixed_data, "customer")`, assert `result["invalid_count"] > 0` (or `len(result["errors"]) > 0`).

4. **Add `test_validate_import_data_empty`** inside `TestImportExportServiceNormal`: call `validate_import_data([], "customer")`, assert `result["errors"][0]` contains `"数据为空"`.

5. **Add `test_export_customers_with_filters`** inside `TestImportExportServiceNormal`: call `export_customers({"source": "web"}, "json")`, assert result is non-empty bytes and `json.loads(result)` parses without error.

6. **Add `test_export_opportunities_csv`** inside `TestImportExportServiceNormal`: call `export_opportunities({}, "csv")`, assert result is non-empty bytes and the CSV contains expected headers (e.g., `name`, `customer_id`).

7. **Add `test_generate_pdf_report_empty_details`** inside `TestImportExportServiceNormal`: call `generate_pdf_report({"summary": {}, "details": []}, "空报表")`, assert non-empty bytes are returned (covers the `_generate_simple_pdf` fallback path when `report_data["details"]` is empty).

8. **Add `test_import_customers_malformed_csv`** inside `TestImportExportServiceError`: construct CSV bytes missing the required "name" column header, pass to `import_customers(csv_bytes, "csv")`, assert `result["error_count"] > 0`.

9. **Add `test_import_opportunities_invalid_json`** inside `TestImportExportServiceError`: pass `b"not json at all"` to `import_opportunities(..., "json")`, assert `result["error_count"] > 0`.

10. **Add `test_export_customers_invalid_format`** inside `TestImportExportServiceError`: call `export_customers({}, "xml")`, expect `ValueError` raised (wraps through `_export_data`).

## Test Plan
- Unit tests in `tests/unit/`: modify `tests/unit/test_import_export_service.py` — add 9 new test methods (3 validation, 3 export, 4 error) and one assertion fix, bringing total to 14+ collectible items.

## Acceptance Criteria
- `pytest tests/unit/test_import_export_service.py --collect-only` — 14+ items, 0 collection errors
- `pytest tests/unit/test_import_export_service.py -v` — all tests pass
- `pytest tests/unit/ -q` — full unit suite remains green
