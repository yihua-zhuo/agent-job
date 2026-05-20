# Architecture & Project Structure

1. Clear project structure (`src/`, `tests/`, `docs/`, `scripts/`)
2. Separation of concerns (business logic vs IO vs API)
3. No circular imports
4. Modules have single responsibility
5. Avoid giant “utility.py” dumping grounds
6. Dependency direction is clean and intentional
7. Config separated from code
8. Environment-specific behavior isolated
9. Entry points are explicit (`main.py`, CLI, app factory)
10. Package boundaries are clear

---

# Readability & Maintainability

11. Variable names are meaningful
12. Function names describe behavior precisely
13. Classes represent real domain concepts
14. No misleading abbreviations
15. Code avoids unnecessary cleverness
16. Comments explain “why”, not “what”
17. Dead code removed
18. Large functions split into smaller units
19. Magic numbers/constants extracted
20. Consistent formatting/style across project

---

# Python-Specific Best Practices

21. Proper use of list/dict/set comprehensions
22. Avoid mutable default arguments
23. Correct context manager usage (`with`)
24. Proper exception hierarchy
25. Avoid bare `except:`
26. Use dataclasses where appropriate
27. Type hints are meaningful and complete
28. Avoid abusing global state
29. Correct async/await usage
30. Avoid unnecessary metaprogramming/reflection

---

# Performance & Scalability

31. No accidental O(N²) or worse loops
32. Database queries are optimized
33. Avoid loading huge files fully into memory
34. Streaming/generator usage where appropriate
35. Caching strategy is justified
36. No repeated expensive computations
37. Concurrency/threading handled safely
38. Async tasks do not block event loop
39. Batch processing used when suitable
40. Profiling evidence exists for “optimized” code

---

# Error Handling & Reliability

41. Errors are logged with useful context
42. Retry logic is bounded and safe
43. External API failures handled gracefully
44. Timeouts exist for network operations
45. Failure paths are tested
46. No silent exception swallowing
47. Cleanup logic exists for partial failures
48. Validation occurs at boundaries
49. Edge cases explicitly considered
50. Application startup failures are understandable

---

# Security

51. Secrets are never hardcoded
52. Input validation/sanitization exists
53. SQL injection protections used
54. Safe deserialization/parsing
55. Dependency vulnerabilities checked
56. Authentication/authorization enforced correctly
57. Sensitive data masked in logs
58. File handling prevents traversal attacks
59. Rate limiting or abuse prevention considered
60. Principle of least privilege followed

---

# Testing

61. Unit tests cover core logic
62. Integration tests exist for critical flows
63. Tests are deterministic
64. Edge cases are tested
65. Failure scenarios are tested
66. Mocking is not excessive
67. Test names clearly explain intent
68. CI automatically runs tests
69. Coverage is meaningful, not vanity metrics
70. Regression tests added for past bugs

---

# DevOps & Deployment

71. Reproducible environments (`requirements.txt`, `poetry.lock`, etc.)
72. Docker images are minimal and secure
73. CI/CD pipelines are stable
74. Health checks/readiness checks exist
75. Logging and monitoring integrated
76. Graceful shutdown supported
77. Configuration documented
78. Versioning/release process defined
79. Rollback strategy exists
80. Observability/tracing included

---

# Data & Database

81. Migrations are version-controlled
82. Schema changes are backward compatible
83. Transactions used correctly
84. Indexes exist for important queries
85. No N+1 query issues
86. Data models are normalized appropriately
87. Data retention policies considered
88. Large blobs/files handled externally when needed
89. Connection pooling configured correctly
90. ORM usage does not hide expensive behavior

---

# API Design

91. APIs are consistent
92. Proper HTTP status codes returned
93. Request/response schemas validated
94. Pagination exists for large datasets
95. API versioning strategy exists
96. Idempotency considered where needed
97. Error responses are structured
98. Backward compatibility maintained
99. Authentication tokens handled securely
100. OpenAPI/Swagger docs maintained

---

# Team & Engineering Quality

101. PR size is reasonable
102. Commit history is meaningful
103. Documentation exists for critical flows
104. Onboarding instructions work
105. Architectural decisions documented
106. Tech debt identified explicitly
107. Linters/type checkers enforced in CI
108. Ownership boundaries are clear
109. Dependencies justified and maintained
110. No copy-paste duplication across modules

---

# Advanced / Senior-Level Review Points

111. Domain model reflects business reality
112. Hidden coupling minimized
113. Failure isolation exists
114. Backpressure/load-shedding considered
115. Resource lifecycle is explicit
116. Eventual consistency issues understood
117. Concurrency hazards analyzed
118. Upgrade/migration paths considered
119. Long-term maintainability prioritized over shortcuts
120. Simplicity preferred unless complexity is justified

---

# Project-Specific Rules

121. **Transaction boundary lives at the router layer.** The `get_db` /
     `get_db_session` dependency in `src/db/connection.py` commits on normal
     exit and rolls back on exception. Service-layer code must NOT call
     `session.commit()` or `session.rollback()` — those calls fight the
     dependency's transaction lifecycle and corrupt the request-scoped unit
     of work.
122. **Service layer may flush, never commit.** Use `await self.session.flush()`
     when you need auto-generated IDs to be populated, an integrity error
     to surface for translation (e.g. `IntegrityError` → `ConflictException`),
     or to make pending changes visible to subsequent queries within the
     same transaction. Flushing is local to the in-progress transaction;
     committing ends it and breaks router-owned semantics.
123. **No `flush()` + `refresh()` + `commit()` triple in services.** That
     pattern indicates the service is trying to own the transaction.
     Rewrite to `flush() → refresh()` and let the router commit.
124. **Integration tests must not mock the database.** Tests under
     `tests/integration/` must use the real Postgres test DB via the
     `async_session`, `db_schema`, and `tenant_id` fixtures from
     `tests/integration/conftest.py`. `unittest.mock.MagicMock` /
     `AsyncMock` / `monkeypatch`-of-DB are forbidden in this directory.
     If a method genuinely doesn't touch the DB, still construct the
     service with the real `async_session` fixture — or move the test
     to `tests/unit/` where mocking is the convention. The point of an
     integration test is to exercise the actual SQL, type coercion, and
     constraint behavior; mocks defeat the purpose.
     (`monkeypatch.setenv` for environment variables is exempt — that's
     not a DB mock.)
125. **Feature domains own their registration points.** Routine domain
     additions must not edit central registry files such as
     `src/api/__init__.py`, `src/db/models/__init__.py`,
     `tests/unit/conftest.py`, or `tests/integration/conftest.py`.
     Add domain-owned files instead:
     `src/api/routers/<domain>.py` exporting an `APIRouter`,
     `src/db/models/<domain>.py` exporting `Base` subclasses,
     `tests/unit/domain_handlers/<domain>.py` exposing
     `get_handlers(state)`, and
     `tests/integration/domain_fixtures/<domain>.py` for seed helpers.
     Reviewers should flag PRs that update central inventories for normal
     feature work unless the PR is explicitly changing the discovery
     mechanism itself.
126. **Tenant isolation is mandatory on every data path.** Service methods
     that read, update, delete, count, search, or aggregate tenant-owned data
     must accept a `tenant_id` and include it in the database predicate.
     Reviewers should treat missing tenant filters as a security bug, not a
     style issue. Cross-tenant negative tests are required for new or changed
     multi-tenant behavior.
127. **Routers serialize; services return domain objects.** Services should
     return ORM/domain objects or `(items, total)` tuples and raise
     `AppException` subclasses for errors. Routers own HTTP concerns:
     request validation, auth dependencies, `.to_dict()` serialization,
     response envelopes, and HTTP status codes. A service returning
     FastAPI responses, `ApiResponse`, or already-serialized envelopes is a
     layering violation.
128. **Routers do not catch service exceptions.** Do not add broad
     `try`/`except` blocks in routers to convert known business failures.
     Raise `AppException` subclasses from the service and let the global
     exception handlers in `src/main.py` shape the response. Router-local
     exception handling is only acceptable when it adds endpoint-specific
     context and preserves the standard error envelope.
129. **Alembic migrations must match model intent.** Schema-changing PRs must
     include a reviewed migration under `alembic/versions/` unless the PR is
     explicitly model-only and documented as such. Autogenerated migrations
     must be inspected for missing constraints, indexes, enum changes,
     server defaults, JSON indexes, and reversible `downgrade()` behavior.
130. **Do not use `Base.metadata.create_all()` in runtime application code.**
     `create_all()` is acceptable in controlled test setup only. Production
     and development schema changes must flow through Alembic migrations so
     drift is visible and reversible.
131. **Async code must not hide blocking work.** FastAPI endpoints and
     services are async-first. Avoid synchronous database clients, blocking
     filesystem/network calls, CPU-heavy loops, or subprocess calls in the
     request path unless they are moved to a worker/threadpool and bounded
     with clear timeouts.
132. **SQL construction must stay structured.** Prefer SQLAlchemy Core/ORM
     expressions and bound parameters. Raw SQL is allowed only when it is
     clearer or required by PostgreSQL-specific behavior; table/column names
     must not be interpolated from untrusted input, and values must be bound
     parameters, never f-strings.
133. **Unit SQL mocks must validate bind parameter names.** Mock handlers in
     `tests/unit/domain_handlers/` and file-local `mock_db_session` fixtures
     must read the same bind keys used by the SQL under test. If the query
     filters on `:id`, the test must pass `{"id": ...}` and the handler must
     inspect `params["id"]`, not a nearby domain key such as `tenant_id`.
     Reviewers should flag tests that can pass while exercising the wrong
     placeholder.
134. **Unit mocks must preserve tenant isolation semantics.** Mock handlers for
     tenant-owned data must enforce `tenant_id` on reads, updates, deletes,
     counts, and aggregates. A unit mock that returns or mutates rows without
     checking tenant scope hides cross-tenant bugs and is not an acceptable
     simplification.
135. **Prefer composable mock state over ad-hoc mocks.** For service tests, use
     the shared `MockState`, `MockRow`, `MockResult`, and domain handler
     pattern where available. File-local fixtures are fine, but inline
     `MagicMock()` / `AsyncMock()` sessions should be limited to tests whose
     behavior cannot reasonably be represented by the handler framework.
136. **DTO validators must match declared schemas.** `from_dict`,
     `model_validator`, and manual coercion logic must agree with field
     optionality and types. Optional fields must not be silently treated as
     required, and enum/string fields must reject unrelated truthy values
     instead of propagating them.
137. **Serialization must explicitly exclude sensitive fields.** `to_dict()`,
     response schemas, logging payloads, and debug helpers must never include
     credential material such as `password_hash`, tokens, secrets, API keys, or
     recovery codes. Use allow-lists for identity/auth models rather than
     mechanically dumping all attributes.
138. **Tenant-owned ORM models need real tenant constraints.** New tenant-owned
     tables must use a proper foreign key to `tenants.id` unless the PR
     documents why the row is intentionally tenant-agnostic. A bare
     `tenant_id: int = 0` column is not enough for data integrity.
139. **Audit and lifecycle fields must be applied consistently.** When a domain
     model family uses soft-delete, timestamps, or actor audit fields, new
     related models must follow the same lifecycle contract or explicitly
     document why they are append-only/stateless.
140. **Plan files must be re-checked against the issue and implementation.**
     Review `.plans/issue-*.md` changes for stale file paths, contradictory
     requirements, incorrect test counts, broken grep patterns, and missing
     issue objectives. Acceptance criteria should name commands that actually
     apply to the files involved; for example, do not ask Ruff to lint YAML.
141. **CI workflows must be fork-aware.** PR workflows cannot assume secrets are
     available for forked pull requests. Diff calculations should prefer commit
     SHAs or GitHub-provided merge/base SHAs over branch names so forks,
     deleted branches, and zero-SHA edge cases do not break review jobs.
142. **CI artifacts must be real outputs.** Upload test reports, coverage files,
     logs, screenshots, or other useful diagnostics. Do not upload internal
     tool caches such as `.pytest_cache/` as if they were test results.
143. **Async tests must not block the event loop.** In `async def` tests, use
     `await asyncio.sleep(...)` or controllable clocks instead of
     `time.sleep(...)`. Blocking sleeps make tests slower and can hide
     scheduling bugs.
144. **Validation tests should assert both acceptance and rejection details.**
     Tests that only assert "there are errors" are weak for import/export and
     batch validation flows. Also assert counters such as `valid_count`,
     `invalid_count`, affected IDs, and representative error records.
145. **Markdown examples need explicit code fence languages.** Use `text`,
     `bash`, `python`, `yaml`, or another accurate language tag on fenced
     blocks in docs, plans, and skills so markdown linting catches real issues
     instead of style churn.
146. **Auto-discovered modules must be import-safe.** Router, model, unit
     handler, and integration fixture modules may be imported during app
     startup, Alembic autogenerate, or test collection. Module import must
     not open network connections, start background tasks, read large files,
     mutate the database, or depend on request-specific state.
147. **Frontend query keys must include every variable that changes fetched
     data.** React Query hooks under `frontend/src/lib/api/queries.ts` must
     include page, page size, filters, IDs, status, and other request-shaping
     values in their query keys. Mutations must invalidate every affected
     list/detail key so stale UI state does not survive writes.
148. **Frontend API calls must use the shared client and auth store.** New
     frontend data access should go through `apiClient` and `useAuthStore`
     rather than ad hoc `fetch` calls. Response handling should preserve the
     backend envelope shape and avoid duplicating token/header logic across
     components.

---
