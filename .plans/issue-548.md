Now I have all the information I need. The project uses Next.js App Router (file-based routing), a Login component already exists at `frontend/src/app/(auth)/login/page.tsx`, and the `AuthGuard` already redirects unauthenticated users to `/login`. The route is already functional via the Next.js directory convention. No code changes are needed — this is a verification task.

---

# Implementation Plan — Issue #548

## Goal

Verify that the `/login` route is correctly registered in the Next.js App Router and that navigating to `/login` renders the existing `LoginPage` component.

## Affected Files

- `frontend/src/app/(auth)/login/page.tsx` — already exists; contains the full `LoginPage` component
- `frontend/src/lib/components/auth-guard.tsx` — already redirects unauthenticated users to `/login`

## Implementation Steps

1. Confirm `frontend/src/app/(auth)/login/page.tsx` is at the correct path. In Next.js App Router, this directory structure automatically registers the `/login` route — no router configuration file or manual route registration is needed.
2. Verify the `AuthGuard` component at `frontend/src/lib/components/auth-guard.tsx` (line 12) uses the same path (`/login`) that the page file resolves to.
3. No code changes are required — the route and component already exist and are correctly wired.

## Test Plan

- Unit tests in `frontend/src/`: Add a Playwright or Vitest test that navigates to `/login` and asserts the sign-in form renders (heading "Sign In", username and password inputs, submit button). Target file: `frontend/src/app/(auth)/login/page.test.tsx` (or `*.spec.tsx` if Playwright is used).
- Integration tests: Not applicable — no new backend routes or database interactions are involved.

## Acceptance Criteria

- Navigating to `/login` renders the `LoginPage` component without errors.
- The sign-in form with username and password fields is visible on the page.
- The `AuthGuard` redirects unauthenticated users away from protected routes to `/login`.
- No new files need to be created; no router configuration changes are needed.

## Risks / Open Questions

- None — the route is already correctly registered via Next.js file-based routing conventions and all required files are in place.
