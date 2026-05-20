# Implementation Plan — Issue #142

## Goal
Create `tests/unit/test_auth_service.py` with unit tests for JWT token operations in `AuthService` (`generate_token`, `verify_token`, `refresh_token`) and the module-level `is_valid_email` function. No database is required — all token methods are pure Python/JWT with no I/O.

## Affected Files
- `tests/unit/test_auth_service.py` — **new file** covering JWT token operations and email validation

## Implementation Steps
1. Create `tests/unit/test_auth_service.py` with an `auth_service` fixture that passes a `MagicMock` session and an explicit `secret_key="test-secret"` to `AuthService` (avoiding any `JWT_SECRET_KEY` env var dependency).
2. Add a `TestGenerateToken` class with:
   - `test_generate_token_returns_string` — calls `generate_token(1, "alice", "admin", 10)` and asserts it returns a non-empty `str`.
   - `test_generate_token_without_tenant` — calls with no `tenant_id`, asserts a string is returned and decoding it reveals no `tenant_id` key.
3. Add a `TestVerifyToken` class with:
   - `test_verify_token_valid` — generate a token via `auth_service.generate_token`, pass it to `verify_token`, assert the returned dict contains `user_id`, `username`, `role`.
   - `test_verify_token_invalid` — pass a random nonsense string to `verify_token`, assert it returns `None`.
   - `test_verify_token_tampered` — create a second `AuthService` with a different secret, generate a token with it, then try to verify it with the first service; assert `None`.
4. Add a `TestRefreshToken` class with:
   - `test_refresh_token_valid` — call `generate_token` to get a token, pass it to `refresh_token` (async), assert the result is a new non-empty `str` different from the original.
   - `test_refresh_token_invalid` — pass a malformed token to `refresh_token` (async), assert it raises `UnauthorizedException`.
5. Add a `TestIsValidEmail` class with `test_is_valid_email` covering at least one valid and one invalid address — this is a module-level function imported from `auth_service`.

## Test Plan
- Unit tests in `tests/unit/`: `tests/unit/test_auth_service.py` — all tests are synchronous except `refresh_token` (marked `@pytest.mark.asyncio`), using only `MagicMock` for the session; no database is used.

## Acceptance Criteria
- `pytest tests/unit/test_auth_service.py --collect-only` reports >= 7 collected items with 0 errors.
- `pytest tests/unit/test_auth_service.py -v` passes with all 7 tests green.
- No `JWT_SECRET_KEY` env var is required at test time — secret is passed via `secret_key=` constructor argument.
