import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
});