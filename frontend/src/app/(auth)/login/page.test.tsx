import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "./page";

// Mock crypto-js
vi.mock("crypto-js", () => ({
  default: {
    AES: {
      encrypt: (data: string, _key: string) => ({
        toString: () =>
          btoa(JSON.stringify({ encrypted: true, data })),
      }),
      decrypt: (ciphertext: string, _key: string) => ({
        toString: () => {
          try {
            const decoded = JSON.parse(atob(ciphertext));
            return decoded.data ?? "";
          } catch {
            return "";
          }
        },
      }),
    },
    enc: {
      Utf8: {},
    },
  },
}));

// Mock next/navigation — useRouter().push is now called from the page, not the store
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Polyfill matchMedia for jsdom (Providers uses it for system theme detection)
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

// Mock the auth store
const mockLogin = vi.fn();
const mockAuthStore = {
  login: mockLogin,
  error: null as string | null,
  isLoading: false,
};

vi.mock("@/lib/store/auth-store", () => ({
  useAuthStore: (selector: (s: typeof mockAuthStore) => unknown) =>
    selector(mockAuthStore),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthStore.error = null;
    mockAuthStore.isLoading = false;
    mockLogin.mockReset();
    mockPush.mockReset();
  });

  it("renders the sign-in form with heading", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: "Sign In" })).toBeTruthy();
  });

  it("renders username and password inputs", () => {
    render(<LoginPage />);
    expect(screen.getByPlaceholderText("username")).toBeTruthy();
    expect(screen.getByPlaceholderText("••••••••")).toBeTruthy();
  });

  it("renders the submit button", () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: "Sign In" })).toBeTruthy();
  });

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
  });

  describe("auth store wiring", () => {
    it("calls authStore.login once with username and password on valid submit, then redirects to /", async () => {
      mockLogin.mockResolvedValue(undefined);

      const user = userEvent.setup();
      render(<LoginPage />);
      await user.type(screen.getByPlaceholderText("username"), "user@example.com");
      await user.type(screen.getByPlaceholderText("••••••••"), "correctpassword");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledTimes(1);
      });
      expect(mockLogin).toHaveBeenCalledWith({
        username: "user@example.com",
        password: "correctpassword",
      });
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith("/");
      });
    });

    it("does not redirect to / when login throws", async () => {
      mockLogin.mockRejectedValue(new Error("Invalid credentials"));

      const user = userEvent.setup();
      render(<LoginPage />);
      await user.type(screen.getByPlaceholderText("username"), "user@example.com");
      await user.type(screen.getByPlaceholderText("••••••••"), "wrongpassword");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalled();
      });
      expect(mockPush).not.toHaveBeenCalledWith("/");
    });

    it("renders the inline error text when authStore.error is set (invalid credentials)", () => {
      mockAuthStore.error = "Invalid credentials";

      render(<LoginPage />);
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });

    it("renders the inline error text when authStore.error indicates account locked", () => {
      mockAuthStore.error = "Account locked. Please contact your administrator.";

      render(<LoginPage />);
      expect(
        screen.getByText(/account locked/i)
      ).toBeInTheDocument();
    });

    it("disables the submit button while isLoading is true", () => {
      mockAuthStore.isLoading = true;

      render(<LoginPage />);
      const button = screen.getByRole("button", { name: /signing in/i });
      expect(button).toBeDisabled();
    });

    it("shows the signing-in label while isLoading is true", () => {
      mockAuthStore.isLoading = true;

      render(<LoginPage />);
      expect(screen.getByRole("button", { name: /signing in/i })).toBeTruthy();
    });
  });
});
