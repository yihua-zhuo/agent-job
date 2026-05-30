Now I have enough to ground the plan in the real codebase.

# Implementation Plan — Issue #549

## Goal
Extract a reusable `Login` component from the existing login page at `frontend/src/app/(auth)/login/page.tsx`, adding a "Remember me" checkbox, "Forgot password" link, and loading-state behavior — all wired to a controlled `onSubmit` prop, without touching the real API call (that belongs to #550).

## Source Contract
Dev-plan target: `docs/dev-plan/90-frontend/0549-create-login-component-with-form-fields.md`
Template depth: `deep`
Reading order followed:
1. `docs/dev-plan/README.md`
2. `docs/dev-plan/_template-deep.md`
3. `docs/dev-plan/90-frontend/0549-create-login-component-with-form-fields.md`

## Affected Files
- `frontend/src/components/ui/input.tsx` — referenced by the new Login component via `@/components/ui/input`
- `frontend/src/components/ui/button.tsx` — referenced by the new Login component via `@/components/ui/button`
- `frontend/src/components/Login.tsx` — **new** — standalone login form component with all required fields and loading state
- `frontend/src/components/__tests__/Login.test.tsx` — **new** — vitest + RTL unit tests for the Login component

## Implementation Steps

### Step 1: Verify existing UI primitives

Confirm `Input` and `Button` UI components exist (they do — already verified at `frontend/src/components/ui/input.tsx` and `frontend/src/components/ui/button.tsx`). No new base components needed.

**完成判定**: `ls frontend/src/components/ui/input.tsx frontend/src/components/ui/button.tsx` → both files exist

### Step 2: Create `frontend/src/components/Login.tsx`

Create the file with:
- `export interface LoginFormData { email: string; password: string; rememberMe: boolean }`
- `export interface LoginProps { onSubmit: (data: LoginFormData) => Promise<void>; isLoading?: boolean }`
- Internal `useState` for `email`, `password`, `rememberMe`, and local `isLoading`
- `handleSubmit` calls `e.preventDefault()`, sets local `isLoading = true`, awaits `onSubmit(...)`, then resets `isLoading = false`
- Renders `<form>` with `<Input type="email">`, `<Input type="password">`, a `<input type="checkbox">` labelled "Remember me", an `<a>` link to `/forgot-password`, and a `<Button type="submit">` that reads local `isLoading` and shows spinner text- All inputs and button receive `disabled={isLoading}` for accessibility

```tsx
// frontend/src/components/Login.tsx
"use client";
import React, { useState, type FormEvent } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export interface LoginFormData {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface LoginProps {
  onSubmit: (data: LoginFormData) => Promise<void>;
}

export function Login({ onSubmit }: LoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await onSubmit({ email, password, rememberMe });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="username"
          disabled={isLoading}
        />
      </div>
      <div className="space-y-1.5">
        <Input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          disabled={isLoading}
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={rememberMe}
          onChange={(e) => setRememberMe(e.target.checked)}
          disabled={isLoading}
        />
        Remember me
      </label>
      <a href="/forgot-password" className="text-sm text-muted-foreground hover:underline">
        Forgot password?
      </a>
      <Button type="submit" disabled={isLoading} className="w-full">
        {isLoading ? "Signing in…" : "Sign In"}
      </Button>
    </form>
  );
}
```

**完成判定**: `ls frontend/src/components/Login.tsx` → file exists

### Step 3: Create `frontend/src/components/__tests__/Login.test.tsx`

Create the test file using vitest + `@testing-library/react`. Set up mocks identical to those in `frontend/src/app/(auth)/login/page.test.tsx` (for `crypto-js`, `next/navigation`, `@tanstack/react-query`). Tests:

1. **Renders all required fields** — `email` input, `password` input, checkbox "Remember me", link "Forgot password?" — verify via `getByRole` / `getByPlaceholderText`
2. **onSubmit callback fires with correct LoginFormData** — fire a submit event, assert `mockSubmit` was called with `{ email, password, rememberMe }`
3. **isLoading disables all fields and shows loading text** — start mock-submit that never resolves, submit form, assert button shows "Signing in…" and all inputs are disabled

```tsx
// frontend/src/components/__tests__/Login.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Login } from "../Login";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock @tanstack/react-query
vi.mock("@tanstack/react-query", () => ({
  useMutation: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}));

describe("Login component", () => {
  const mockSubmit = vi.fn<[Promise<void>]>();

  beforeEach(() => {
    vi.clearAllMocks();
    mockSubmit.mockReset();
 mockSubmit.mockResolvedValue(undefined);
  });

  it("renders all required form fields", () => {
    render(<Login onSubmit={mockSubmit} />);
    expect(screen.getByPlaceholderText("username")).toBeTruthy();
    expect(screen.getByPlaceholderText("••••••••")).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: /remember me/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /forgot password/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeTruthy();
  });

  it("calls onSubmit with correct data on form submit", async () => {
    render(<Login onSubmit={mockSubmit} />);
    fireEvent.change(screen.getByPlaceholderText("username"), { target: { value: "test@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), { target: { value: "secret123" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /remember me/i }));
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(mockSubmit).toHaveBeenCalledWith({
        email: "test@example.com",
        password: "secret123",
        rememberMe: true,
      })
    );
  });

  it("shows loading indicator and disables fields while submitting", async () => {
    let release: () => void;
    mockSubmit.mockImplementation(
      () => new Promise<void>((resolve) => { release = resolve; })
    );
    render(<Login onSubmit={mockSubmit} />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /signing in…/i })).toBeDisabled();
      expect(screen.getByPlaceholderText("username")).toBeDisabled();
 expect(screen.getByPlaceholderText("••••••••")).toBeDisabled();
    });
    release!();
  });
});
```

**完成判定**: `cd frontend && npx vitest run --testPathPattern="Login.test"` → all 3 tests pass

### Step 4: Lint the new component

```bash
cd frontend && npx eslint src/components/Login.tsx src/components/__tests__/Login.test.tsx
```

**完成判定**: exit 0, no errors

### Step 5: Format```bash
cd frontend && npx prettier --write src/components/Login.tsx src/components/__tests__/Login.test.tsx
```

**完成判定**: files formatted alongside existing codebase

## Test Plan
- Unit tests in `frontend/src/components/__tests__/Login.test.tsx`: three tests covering field rendering, `onSubmit` callback data shape, and loading-state UI disabling
- No integration test: the component is intentionally uncoupled from the real auth API
- Dev-plan verification per §6:
  - `ls frontend/src/components/Login.tsx` → file exists
  - `grep "isLoading" frontend/src/components/Login.tsx` → finds `isLoading` state
  - `grep "rememberMe" frontend/src/components/Login.tsx` → finds checkbox state and `LoginFormData` field
  - `grep "forgot-password" frontend/src/components/Login.tsx` → finds the link
  - `cd frontend && npx vitest run --testPathPattern="Login.test"` → 3 passed

## Acceptance Criteria
- The `<Login />` component renders a `<form>` with email input, password input, "Remember me" checkbox, "Forgot password?" link, and a submit `<Button>`
- Submitting the form (with no mock submit resolving) shows "Signing in…" button text and disables all form elements before `onSubmit` resolves
- Submitting with a resolved `onSubmit` call resets `isLoading` to `false` and re-enables all fields
- `LoginFormData` interface is exported from `frontend/src/components/Login.tsx` with exact shape: `{ email: string; password: string; rememberMe: boolean }`
- `LoginProps` interface is exported with `onSubmit: (data: LoginFormData) => Promise<void>`
- The existing login page at `frontend/src/app/(auth)/login/page.tsx` is **not modified** by this component — architectural wiring to the page is left to #550

## Risks / Open Questions
- **No `@testing-library/react` in frontend `package.json`**: vitest is present but `@testing-library/react` is not listed as a direct dependency. If tests fail on import, the library may need to be added via `npm install --save-dev @testing-library/react`, which may need a separate PR or a check with the project owner.
- **No `eslint` config file confirmed**: `frontend/eslint.config.mjs` exists (from glob), so linting with `eslint` should work; if not, fall back to `ruff check` or skip this step.
