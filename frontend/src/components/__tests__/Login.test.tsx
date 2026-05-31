import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Login, type LoginFormData } from "../Login";

describe("Login component", () => {
  const mockSubmit = vi.fn<[LoginFormData], Promise<void>>();

  beforeEach(() => {
    vi.clearAllMocks();
    mockSubmit.mockReset();
    mockSubmit.mockResolvedValue(undefined);
  });

  it("renders all required form fields", () => {
    render(<Login onSubmit={mockSubmit} />);
    expect(screen.getByPlaceholderText("name@example.com")).toBeTruthy();
    expect(screen.getByPlaceholderText("••••••••")).toBeTruthy();
    expect(
      screen.getByRole("checkbox", { name: /remember me/i })
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: /forgot password/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeTruthy();
  });

  it("calls onSubmit with correct data on form submit", async () => {
    render(<Login onSubmit={mockSubmit} />);
    fireEvent.change(screen.getByPlaceholderText("name@example.com"), {
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

  it("calls onSubmit with rememberMe: false when checkbox is not checked", async () => {
    render(<Login onSubmit={mockSubmit} />);
    fireEvent.change(screen.getByPlaceholderText("name@example.com"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), {
      target: { value: "secret123" },
    });
    // intentionally do NOT click the "remember me" checkbox
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(mockSubmit).toHaveBeenCalledWith({
        email: "test@example.com",
        password: "secret123",
        rememberMe: false,
      })
    );
  });

  it("shows loading indicator and disables fields while submitting", async () => {
    let resolve: () => void = () => {};
    mockSubmit.mockImplementation(
      () => new Promise<void>((r) => { resolve = r; })
    );
    render(<Login onSubmit={mockSubmit} />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(
      () => {
        expect(
          screen.getByRole("button", { name: /signing in…/i }).disabled
        ).toBe(true);
        expect(screen.getByPlaceholderText("········").disabled).toBe(true);
      },
      { timeout: 1000 }
    );
    // Release the mock so the component resets for subsequent tests.
    resolve();
  });

  it("disables fields and shows loading when external isLoading is true", async () => {
    render(<Login onSubmit={mockSubmit} isLoading={true} />);
    expect(screen.getByRole("button", { name: /signing in…/i }).disabled).toBe(true);
    expect(screen.getByPlaceholderText("name@example.com").disabled).toBe(true);
    expect(screen.getByPlaceholderText("········").disabled).toBe(true);
    expect(mockSubmit).not.toHaveBeenCalled();
  });
});
