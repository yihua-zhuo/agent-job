# MyPy Error Report - 2026-03-24

Total errors: 21

## Summary by file

| File | Error Count |
|------|------------|
| src/db/repositories/base.py | 9 |
| src/services/import_export_service.py | 4 |
| src/db/connection.py | 3 |
| src/services/workflow_service.py | 1 |
| src/services/marketing_service.py | 1 |
| src/db/models/pipeline_stage.py | 1 |
| src/middleware/auth.py | 1 |
| src/internal/middleware/auth.py | 1 |

## Full mypy output

```
src/middleware/tenant.py:13: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
src/services/churn_prediction.py:44: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
src/services/sales_recommendation.py:42: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
src/services/workflow_service.py:261: error: Unsupported operand types for in ("Any | None" and "str")  [operator]
src/services/marketing_service.py:88: error: Item "None" of "Any | None" has no attribute "value"  [union-attr]
src/internal/db/engine.py:51: note: By default the bodies of untyped functions are not checked, consider using --check-untyped-defs  [annotation-unchecked]
src/db/connection.py:12: error: Incompatible types in assignment (expression has type "None", variable has type "AsyncSession")  [assignment]
src/db/connection.py:13: error: Incompatible types in assignment (expression has type "None", variable has type "async_sessionmaker[Any]")  [assignment]
src/db/connection.py:29: error: No overload variant of "async_sessionmaker" matches argument types "AsyncSession", "type[AsyncSession]", "bool", "bool", "bool"  [call-overload]
src/db/repositories/base.py:37: error: "type[T]" has no attribute "__table__"  [attr-defined]
src/db/repositories/base.py:38: error: "type[T]" has no attribute "__table__"  [attr-defined]
src/db/repositories/base.py:48: error: "type[T]" has no attribute "__table__"  [attr-defined]
src/db/repositories/base.py:57: error: "type[T]" has no attribute "__table__"  [attr-defined]
src/db/repositories/base.py:69: error: "type[T]" has no attribute "__table__"  [attr-defined]
src/db/repositories/base.py:70: error: "type[T]" has no attribute "__table__"  [attr-defined]
src/db/repositories/base.py:84: error: "type[T]" has no attribute "__table__"  [attr-defined]
src/db/repositories/base.py:85: error: "type[T]" has no attribute "__table__"  [attr-defined]
src/db/repositories/base.py:89: error: "Result[Any]" has no attribute "rowcount"  [attr-defined]
src/db/models/pipeline_stage.py:25: error: Name "PipelineModel" is not defined  [name-defined]
src/middleware/auth.py:32: error: Argument 2 has incompatible type "str | None"; expected "RSAPublicKey | EllipticCurvePublicKey | Ed25519PublicKey | Ed448PublicKey | PyJWK | str | bytes"  [arg-type]
src/internal/middleware/auth.py:29: error: Argument 2 has incompatible type "str | None"; expected "RSAPublicKey | EllipticCurvePublicKey | Ed25519PublicKey | Ed448PublicKey | PyJWK | str | bytes"  [arg-type]
src/services/import_export_service.py:120: error: Argument 1 to "insert" has incompatible type "str"; expected "TableClause | Join | Alias | CTE | type[Any] | Inspectable[_HasClauseElement[Any]] | _HasClauseElement[Any]"  [arg-type]
src/services/import_export_service.py:196: error: Argument 1 to "insert" has incompatible type "str"; expected "TableClause | Join | Alias | CTE | type[Any] | Inspectable[_HasClauseElement[Any]] | _HasClauseElement[Any]"  [arg-type]
src/services/import_export_service.py:264: error: Argument 1 to "insert" has incompatible type "str"; expected "TableClause | Join | Alias | CTE | type[Any] | Inspectable[_HasClauseElement[Any]] | _HasClauseElement[Any]"  [arg-type]
src/services/import_export_service.py:559: error: "bytes" has no attribute "encode"; maybe "decode"?  [attr-defined]
Found 21 errors in 8 files (checked 84 source files)
```