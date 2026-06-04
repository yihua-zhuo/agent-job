Now I have the full picture. The auth store currently has `setAuth`/`clearAuth` but no `login()` method, and the Login page directly calls the auth API service instead of going through the store. The redirect goes to `/customers` but the dev-plan requires `/dashboard`.

# Implementation Plan — Issue #551

## Goal
Wire the Login page component to the auth store by adding a `login()` action method to the store that encapsulates the API call, token persistence, and redirect logic, then update the Login page to call `authStore.login()` instead of calling the auth API service directly. On success, redirect to `/dashboard`; on "invalid credentials" or "account locked" responses, display an inline error.

## Source Contract
Dev-plan target: `/home/runner/work/agent-job/agent-job/docs/dev-plan/90-frontend/0551-wire-login-component-to-auth-store-service.md`
Template depth: `deep`
Reading order followed:
1. `/home/runner/work/agent-job/agent-job/docs/dev-plan/README.md`
2. `/home/runner/work/agent-job/agent-job/docs/dev-plan/_template-deep.md`
3. `/home/runner/work/agent-job/agent-job/docs/dev-plan/90-frontend/0551-wire-login-component-to-auth-store-service.md`

## Affected Files
- `frontend/src/lib/store/auth-store.ts` — add `login(credentials)` method, `logout()` method, and `error`/`isLoading` state fields; update `AuthState` interface
- `frontend/src/app/(auth)/login/page.tsx` — replace direct `useMutation` with call to `authStore.login()`; change redirect from `/customers` to `/dashboard`; read `error` and `isLoading` from the store
- `frontend/src/lib/store/auth-store.test.ts` — add tests for `login()` and `logout()` methods (success, invalid credentials, account locked)
- `frontend/src/app/(auth)/login/page.test.tsx` — update existing tests; add tests for wiring to auth store (correct creds → /dashboard redirect, wrong creds → inline error, locked account → inline error)

## Implementation Steps

### Step 1: Extend `AuthState` interface in `auth-store.ts`
Add `error: string | null` and `isLoading: boolean` fields to the `AuthState` interface (L31-38). Add `login(credentials: { username: string; password: string }): Promise<void>` and `logout(): void` method signatures.

### Step 2: Add `login()` and `logout()` methods to the store body (L51-58)
Implement `login()`:
- Set `error = null` and `isLoading = true` at start
- Call `authService.login()` with form-encoded credentials (`{ username, password }`)
- On success: call `getMe(token)`, then `setAuth(token, userData)`, then `router.push('/dashboard')`
- On `getMe` failure: fall back to `setAuth()` with minimal user data (same fallback as current L33-37), then redirect
- On API error: set `error` to `err.message`, set `isLoading = false`, throw
- Use `finally` to set `isLoading = false` on success path

Implement `logout()`:
- Call `clearAuth()`
- No redirect (this is done by the caller/component, e.g. auth-guard already handles redirect to `/login` on guard failure)

### Step 3: Update Login page to use `authStore.login()` (`page.tsx` L18-44)
- Remove the `useMutation` wrapper around `login`
- Import `useAuthStore` selector for `login`, `error`, `isLoading`
- In `form.handleSubmit`, call `authStore.login({ username, password })` inside a try/catch
- On catch: `form.setError("root.serverError", { message: authStore.error })` — or read `authStore.error` directly in render
- Change `router.push("/customers")` logic: remove the inline redirect (store handles it). If store does not redirect, push to `/dashboard` in the Login page's onSuccess
- Change `disabled={mutation.isPending}` to `disabled={authStore.isLoading}`

### Step 4: Add tests for `authStore.login()` in `auth-store.test.ts`
- Mock `@/lib/api/auth` `login` and `getMe` functions
- Mock `next/navigation` `useRouter`
- Test: correct credentials → `setAuth` called, `isAuthenticated` returns true
- Test: wrong credentials → `error` set, no auth state change, method throws
- Test: locked account response (401 with "Account locked" message) → `error` contains "locked", no auth state change

### Step 5: Update Login page tests in `page.test.tsx`
- Update existing mocks to include `useAuthStore` returning a mock with `login`, `error`, `isLoading`
- Add test: submit valid form → `authStore.login` called once, redirect to `/dashboard` attempted
- Add test: `authStore.error` set → inline error text rendered in DOM
- Add test: locked account error message → inline error text rendered

### Step 6: Run lint and tests
- `cd frontend && npx vitest run src/lib/store/auth-store.test.ts src/app/\(auth\)/login/page.test.tsx` — all pass
- `cd frontend && npx next build` — typecheck and build pass

## Test Plan
- Unit tests in `frontend/src/lib/store/auth-store.test.ts`: Extend with 3 new test cases — `login()` success path (credentials correct → token stored, `isAuthenticated` true), `login()` invalid credentials (`error` set, no state mutation, throws), `login()` account locked (`error` contains "locked", no state mutation). Mock `@/lib/api/auth` and `next/navigation`.
- Unit tests in `frontend/src/app/(auth)/login/page.test.tsx`: Update existing mocks to include `useAuthStore`. Add 2 new test cases — form submit calls `authStore.login` once with correct args; when `authStore.error` is non-null, the inline error `<p>` element appears. Existing "Invalid credentials" test already covers the error rendering path but needs updated mocking to account for store-based error propagation.
- No integration tests needed (pure frontend wiring change, no DB or API changes).
- Dev-plan verification: The dev-plan §6 lists only the test commands above plus `ruff check` (not applicable to TypeScript). The vitest commands in Steps 4-6 are the machine-checkable verification.

## Acceptance Criteria
- Submitting valid credentials calls `authStore.login()` and triggers `router.push('/dashboard')`
- Submitting invalid credentials displays the API error message as inline text in the form; no redirect occurs
- Submitting credentials for a locked account displays an "account locked" inline error; no redirect occurs
- `authStore.login()` sets `isLoading = true` during the API call and `isLoading = false` on completion (both success and error paths)
- The submit button is disabled while `authStore.isLoading` is true
- `frontend/src/lib/store/auth-store.test.ts` and `frontend/src/app/(auth)/login/page.test.tsx` pass with all new and existing test cases green
- `cd frontend && npx next build` completes with no type or build errors

## Risks / Open Questions
- The current Login page redirects to `/customers` (not `/dashboard`) — this is a deliberate change per the dev-plan acceptance criteria. If the dashboard route does not exist yet, the redirect will produce a 404 until the dashboard page is built. This is expected and within scope of #551.
- The dev-plan says token storage should use sessionStorage, but the current implementation uses encrypted localStorage. The existing `auth-store.ts` persists via `localStorage`. This issue should not change the storage mechanism — only wire the login flow through the store. The sessionStorage vs localStorage concern is already settled by #550's foundation.
