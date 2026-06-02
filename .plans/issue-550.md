Now I have a thorough understanding of the codebase. Let me write the implementation plan.

---

# Implementation Plan — Issue #550

## Goal
Add client-side form validation to the `Login` component in `frontend/src/app/(auth)/login/page.tsx`: upgrade the `username` Zod schema to validate email format (`z.string().email()`), fix the `onError` handler to write server errors to `formState.errors.root.serverError` (not the `password` field), add a UI display for the root-level server error, and cover all three scenarios with tests.

## Source Contract
Dev-plan target: `docs/dev-plan/90-frontend/0550-add-form-validation-to-login-component.md`
Template depth: `deep`
Reading order followed:
1. `docs/dev-plan/README.md`
2. `docs/dev-plan/_template-deep.md`
3. `docs/dev-plan/90-frontend/0550-add-form-validation-to-login-component.md`

## Affected Files
- `frontend/src/app/(auth)/login/page.tsx` — upgrade `loginSchema` to `z.string().email()`, change `onError` from `setError("password", …)` to `setError("root.serverError", …)`, add `formState.errors.root?.serverError` UI below submit button
- `frontend/src/app/(auth)/login/page.test.tsx` — add 3 new test cases: empty-submit field errors, invalid-email format error, server-error root display; also add `vi.mock("@/lib/api/auth")` for the server-error test

## Implementation Steps

### Step 1: Upgrade `loginSchema` to validate email format

In `frontend/src/app/(auth)/login/page.tsx` lines 12–15, change `username` from `z.string().min(1, "Username is required")` to `z.string().min(1, "Username is required").email("Please enter a valid email address")`.

```tsx
const loginSchema = z.object({
  username: z.string().min(1, "Username is required").email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
```

**Verification**: `grep -n 'email' frontend/src/app/\(auth\)/login/page.tsx` returns the updated `.email()` call; `cd frontend && pnpm lint` passes.

### Step 2: Fix `onError` — write server errors to `root.serverError`

In `frontend/src/app/(auth)/login/page.tsx` lines 41–43, change `form.setError("password", { message: err.message })` to `form.setError("root.serverError", { message: err.message })`.

```tsx
onError: (err: Error) => {
  form.setError("root.serverError", { message: err.message });
},
```

**Verification**: `grep -n 'root.serverError' frontend/src/app/\(auth\)/login/page.tsx` returns at least 1 occurrence.

### Step 3: Add `root.serverError` UI below submit button

In `frontend/src/app/(auth)/login/page.tsx`, before the closing `</form>` tag (after line 81, before line 82), insert:

```tsx
{form.formState.errors.root?.serverError && (
  <p className="text-sm text-destructive">{form.formState.errors.root.serverError.message}</p>
)}
```

**Verification**: `grep -n 'root.serverError' frontend/src/app/\(auth\)/login/page.tsx` returns ≥ 2 occurrences (one write in `onError`, one in JSX).

### Step 4: Add 3 validation test cases to `page.test.tsx`

In `frontend/src/app/(auth)/login/page.test.tsx`, after the existing test block, add the following `describe("LoginForm validation", ...)` block. Also add `vi.mock("@/lib/api/auth")` at the top of the file (alongside existing mocks) so the `login` function is mockable in the server-error test.

New import additions (add near top of file):
```tsx
import * as auth from "@/lib/api/auth";
```

New mock (add alongside existing `vi.mock` blocks):
```tsx
// Mock @/lib/api/auth
vi.mock("@/lib/api/auth", () => ({
  login: vi.fn(),
  getMe: vi.fn().mockResolvedValue({ data: { id: 1, tenant_id: 1, username: "a", email: "a@b.com", role: "user", status: "active" } }),
}));
```

New test cases (append to file before final `});`):
```tsx
  describe("LoginForm validation", () => {
    it("shows required field errors on empty submit", async () => {
      const user = userEvent.setup();
      render(<LoginPage />);
      await user.click(screen.getByRole("button", { name: /sign in/i }));
      expect(await screen.findByText(/username is required/i)).toBeInTheDocument();
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });

    it("shows email format error for invalid email input", async () => {
      const user = userEvent.setup();
      render(<LoginPage />);
      await user.type(screen.getByPlaceholderText("username"), "not-an-email");
      await user.click(screen.getByRole("button", { name: /sign in/i }));
      expect(await screen.findByText(/please enter a valid email address/i)).toBeInTheDocument();
    });

    it("shows root.serverError message on invalid credentials", async () => {
      let capturedOnError: ((err: Error) => void) | undefined;
      vi.mocked(auth.login).mockImplementation(() => new Promise((_, reject) => {
        // capture the onError callback so the test can fire it manually
        capturedOnError = (err) => reject(err);
      }));

      // Override useMutation mock specifically for this test to call onError
      vi.mocked(useMutation).mockImplementation(({ onError }) => {
        const mutate = (...args: unknown[]) => {
          if (onError && capturedOnError) onError(new Error("Invalid credentials"));
        };
        return { mutate, isPending: false };
      });

      const user = userEvent.setup();
      render(<LoginPage />);
      await user.type(screen.getByPlaceholderText("username"), "user@example.com");
      await user.type(screen.getByPlaceholderText("••••••••"), "wrongpassword");
      await user.click(screen.getByRole("button", { name: /sign in/i }));
      expect(await screen.findByText("Invalid credentials")).toBeInTheDocument();
    });
  });
```

Also add `userEvent` import at top:
```tsx
import userEvent from "@testing-library/user-event";
```

**Verification**: `cd frontend && pnpm test` → ≥ 8 passed (original 3 + 3 new + 2 auth-store).

## Test Plan
- Unit tests in `frontend/src/app/(auth)/login/page.test.tsx`: add 3 new cases to the existing test suite covering empty submit (field errors), invalid email format (username field error), and server `Invalid credentials` (root serverError). Run via `cd frontend && pnpm test`.
- Dev-plan verification: `npm --prefix frontend run lint` → 0 errors; `npm --prefix frontend run test` → ≥ 8 passed.

## Acceptance Criteria
- Submitting the form with both fields empty shows "Username is required" and "Password is required" below their respective inputs, with no root error.
- Submitting with username "not-an-email" (no `@`) shows "Please enter a valid email address" below the username field and does not call the `login` API.
- Submitting with valid email format but wrong password shows "Invalid credentials" in the `formState.errors.root.serverError` display area (between the fields and the submit button), with no per-field error borders.
- `cd frontend && pnpm lint` exits 0; `cd frontend && pnpm test` exits 0 with all tests passing.

## Risks / Open Questions
- The existing `page.test.tsx` mocks `useMutation` globally to prevent real calls; the server-error test (Test 3) needs to make the mock's `mutate` fn actually invoke `onError`. This is addressed by overriding `vi.mocked(useMutation)` inside the specific test, which resets the mock for that test only.
- The dev-plan suggests creating `login.test.tsx` as a new file, but the existing `page.test.tsx` at `frontend/src/app/(auth)/login/page.test.tsx` is the project's established test location for this component — tests are added there to share the existing mock setup.
