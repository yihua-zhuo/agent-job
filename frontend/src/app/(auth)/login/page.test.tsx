import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as auth from "@/lib/api/auth";
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

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

// Mock @tanstack/react-query
vi.mock("@tanstack/react-query", () => ({
  useMutation: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}));

// Mock @/lib/api/auth
vi.mock("@/lib/api/auth", () => ({
  login: vi.fn(),
  getMe: vi.fn().mockResolvedValue({ data: { id: 1, tenant_id: 1, username: "a", email: "a@b.com", role: "user", status: "active" } }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

    it("shows root.serverError message on invalid credentials", async () => {
      let capturedOnError: ((err: Error) => void) | undefined;
      vi.mocked(auth.login).mockImplementation(() => new Promise((_, reject) => {
        capturedOnError = (err) => reject(err);
      }));

      const { useMutation } = await import("@tanstack/react-query");
      vi.mocked(useMutation).mockImplementation(({ onError }) => {
        const mutate = (..._args: unknown[]) => {
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
});