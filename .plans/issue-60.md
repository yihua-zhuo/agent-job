# Implementation Plan — Issue #60

## Goal

Validate and complete the existing frontend scaffold at `frontend/` — currently running Next.js 16.2.4 (newer than the specified Next.js 15.x — acceptable given CVE-2025-66478 affects both 15 and 16, and 16.2.4 ships after the patch), React 19, Tailwind v4, shadcn-ui v4, and TanStack Query v5 — by adding Prettier, integrating it with ESLint, creating an `.env.local.example`, and ensuring the API rewrite proxy targets the backend at `:8000`.

## Affected Files

- `frontend/` — entire existing Next.js scaffold (already functional; audit and complete)
- `frontend/eslint.config.mjs` — add Prettier plugin integration
- `frontend/.prettierrc*` — **new file** — Prettier configuration (currently absent)
- `frontend/.env.local.example` — **new file** — environment variable documentation
- `frontend/next.config.ts` — update API rewrite destination for local dev (`http://localhost:8000`)
- `frontend/package.json` — add Prettier scripts and dependency
- `frontend/src/components/layout/app-sidebar.tsx` — existing sidebar; verify nav coverage for issue-specified routes
- `frontend/src/app/(auth)/login/page.tsx` — existing auth flow; confirm complete
- `frontend/src/app/(app)/customers/page.tsx` — existing; verify
- `frontend/src/app/(app)/sales/page.tsx` — existing; verify
- `frontend/src/app/(app)/tickets/page.tsx` — existing; verify
- `frontend/src/app/(app)/analytics/page.tsx` — existing; verify
- `frontend/src/app/(app)/ai/page.tsx` — existing; verify

## Implementation Steps

1. **Audit current scaffold completeness.** Confirm all issue-specified routes exist at `frontend/src/app/(app)/` — `customers/`, `sales/`, `tickets/`, `analytics/`, `ai/` — and that `globals.css` defines CSS variables for shadcn-ui's `new-york` style. Confirm `components.json` aliases (`@/components`, `@/lib/utils`, `@/components/ui`) match the issue spec.

2. **Add Prettier.** Install `prettier` and `@IANVS/prettier` (shadcn-ui's official Prettier plugin for Tailwind v4 class sorting) as dev dependencies. Create `frontend/.prettierrc` with `printWidth: 100`, `singleQuote: true`, and `@IANVS/prettier` as plugin. Create `frontend/.prettierignore` ignoring `.next/`, `node_modules/`, `build/`, `out/`.

3. **Integrate Prettier with ESLint.** Install `eslint-config-prettier` as a dev dependency. Update `frontend/eslint.config.mjs` to import and merge `eslintConfigPrettier` so it overrides conflicting ESLint formatting rules.

4. **Add Prettier to package.json scripts.** Update `format` script to `"prettier --write ."`. Add a `"format:check"` script as `"prettier --check ."` for CI. Update the existing `lint` script to run both ESLint and Prettier check: `"eslint . && prettier --check ."`.

5. **Create `frontend/.env.local.example`.** Document the three required environment variables:
   ```
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
   NEXT_PUBLIC_AUTH_SECRET=<random 32-char hex string for AES encryption>
   ```
   Add a comment noting that `NEXT_PUBLIC_API_BASE_URL` is only needed in development; in production the `next.config.ts` rewrite handles routing.

6. **Update `frontend/next.config.ts` API rewrite.** Replace the hardcoded production destination (`https://agent-job-production.up.railway.app`) with conditional logic: use `http://localhost:8000` when `process.env.NODE_ENV === 'development'`, otherwise fall back to the production URL. This ensures `npm run dev` proxies to local backend while CI/production still route to the deployed API.

7. **Verify shadcn-ui component coverage.** Cross-check the existing shadcn-ui components in `frontend/src/components/ui/` against the issue's acceptance criteria. The issue specifies a base layout with sidebar — confirm `app-sidebar.tsx` covers all navigation links for the five CRM modules. Add any missing navigation links if a route directory exists but has no sidebar entry.

8. **Document setup in `frontend/README.md`.** Append a "Getting Started" section to the existing `frontend/README.md` covering: `npm install`, copying `.env.local.example` to `.env.local`, running the dev server with `npm run dev`, and the lint/format commands.

9. **Verify the auth flow scaffold.** Confirm the `(auth)/login/page.tsx` login form posts to `/api/v1/auth/login`, the Zustand auth store (`frontend/src/lib/store/auth-store.ts`) persists the token, and the `(app)/layout.tsx` `AuthGuard` redirects unauthenticated users. No changes needed — this is confirmation only.

10. **Install and record the shadcn-ui `register` component.** The issue acceptance criteria include auth flow scaffolding. Register is typically a shadcn-ui form element. Run `npx shadcn@latest add register` (or verify it exists in `components/ui/`); if not available, document in `frontend/README.md` that the login form uses native `<input>` and a `<form>` wrapper.

## Test Plan

- Unit tests in `frontend/src/__tests__/` (or `frontend/src/**/*.test.tsx`): Add unit tests for the auth store (`frontend/src/lib/store/auth-store.test.ts`) covering `setAuth`, `clearAuth`, and `isAuthenticated`. Add tests for the `ApiError` class in `frontend/src/lib/api-client.test.ts` covering `.isUnauthorized`, `.isForbidden`, `.isNotFound`, and `.isValidation`. No DB or HTTP layer tests needed — mocking is handled within the components.
- Integration tests: Frontend integration tests are covered by Playwright component tests (out of scope for this issue). Manual verification steps are documented in the acceptance criteria below.

## Acceptance Criteria

- `npm install` succeeds without errors and all dependencies resolve
- `npm run lint` exits 0 with no errors (ESLint)
- `npm run format:check` exits 0 with no files changed (Prettier)
- `npm run dev` starts the Next.js dev server and proxies `/api/*` to `http://localhost:8000`
- Visiting `/login` shows the sign-in form; submitting valid credentials redirects to `/customers`
- Visiting any `/customers`, `/sales`, `/tickets`, `/analytics`, `/ai` route while unauthenticated redirects to `/login`
- The sidebar shows navigation links for all five CRM modules
- `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_AUTH_SECRET` are documented in `frontend/.env.local.example`
- `components.json` aliases (`@/components`, `@/lib/utils`, `@/components/ui`) are present and correct
- TypeScript compiles with `strict: true` and no type errors

## Risks / Open Questions

- **Next.js version**: Issue specifies Next.js 15.x to avoid CVE-2025-66478, but the repository already has Next.js 16.2.4. The CVE affects both 15.x and 16.x (CVSS 10.0); 16.2.4 ships after the security patch window. Downgrading to 15.x would reintroduce the vulnerability. Recommend keeping 16.2.4 and monitoring `nextjs.org/blog/security-update-2025-12-11` for future advisories.
- **shadcn-ui `register` component**: The `register` shadcn-ui component may not exist in the current shadcn-ui v4.x package — the login form uses native `<input>`. If a register page is later required, run `npx shadcn@latest add form` to scaffold it.
- **API rewrite production target**: The hardcoded production rewrite URL (`agent-job-production.up.railway.app`) is environment-specific. Consider adding `NEXT_PUBLIC_API_BASE_URL` as a build-time env var to avoid hardcoding the production destination in `next.config.ts`.
