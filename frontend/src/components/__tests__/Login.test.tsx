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
    expect(
      screen.getByRole("checkbox", { name: /remember me/i })
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: /forgot password/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeTruthy();
  });

  it("calls onSubmit with correct data on form submit", async () => {
    render(<Login onSubmit={mockSubmit} />);
    fireEvent.change(screen.getByPlaceholderText("username"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), {
      target: { value: "secret123" },
    });
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
      expect(
        screen.getByRole("button", { name: /signing in…/i }).disabled
      ).toBe(true);
      expect(screen.getByPlaceholderText("username").disabled).toBe(true);
      expect(screen.getByPlaceholderText("••••••••").disabled).toBe(true);
    });
    release!();
  });
});
