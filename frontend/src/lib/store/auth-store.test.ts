import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useAuthStore } from "./auth-store";

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

const mockLogin = vi.fn();
const mockGetMe = vi.fn();

vi.mock("@/lib/api/auth", () => ({
  login: (...args: unknown[]) => mockLogin(...args),
  getMe: (...args: unknown[]) => mockGetMe(...args),
}));

describe("auth-store", () => {
  beforeEach(() => {
    mockLogin.mockReset();
    mockGetMe.mockReset();
    useAuthStore.setState({
      token: null,
      user: null,
      isHydrated: true,
      error: null,
      isLoading: false,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const mockUser = {
    id: 1,
    tenant_id: 1,
    username: "testuser",
    email: "test@example.com",
    role: "admin",
    status: "active",
    full_name: "Test User",
  };

  describe("setAuth", () => {
    it("sets token and user", () => {
      useAuthStore.getState().setAuth("test-token-abc", mockUser);
      expect(useAuthStore.getState().token).toBe("test-token-abc");
      expect(useAuthStore.getState().user).toEqual(mockUser);
    });

    it("isAuthenticated returns true after setAuth", () => {
      const store = useAuthStore.getState();
      store.setAuth("test-token-abc", mockUser);
      expect(store.isAuthenticated()).toBe(true);
    });

    it("overwrites previous token and user", () => {
      const store = useAuthStore.getState();
      store.setAuth("token-1", mockUser);
      const newUser = { ...mockUser, id: 2, username: "other" };
      store.setAuth("token-2", newUser);
      expect(useAuthStore.getState().token).toBe("token-2");
      expect(useAuthStore.getState().user?.username).toBe("other");
    });

    it("clears any prior error", () => {
      useAuthStore.setState({ error: "old error" });
      useAuthStore.getState().setAuth("t", mockUser);
      expect(useAuthStore.getState().error).toBeNull();
    });
  });

  describe("clearAuth", () => {
    it("removes token and user", () => {
      const store = useAuthStore.getState();
      store.setAuth("test-token-abc", mockUser);
      store.clearAuth();
      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
    });

    it("isAuthenticated returns false after clearAuth", () => {
      const store = useAuthStore.getState();
      store.setAuth("test-token-abc", mockUser);
      store.clearAuth();
      expect(store.isAuthenticated()).toBe(false);
    });

    it("is idempotent - safe to call without prior setAuth", () => {
      const store = useAuthStore.getState();
      store.clearAuth(); // no prior setAuth
      expect(store.token).toBeNull();
      expect(store.user).toBeNull();
      expect(store.isAuthenticated()).toBe(false);
    });

    it("clears any prior error", () => {
      useAuthStore.setState({ error: "old error" });
      useAuthStore.getState().clearAuth();
      expect(useAuthStore.getState().error).toBeNull();
    });
  });

  describe("isAuthenticated", () => {
    it("returns false when token is null", () => {
      expect(useAuthStore.getState().isAuthenticated()).toBe(false);
    });

    it("returns false when token is empty string", () => {
      useAuthStore.setState({ token: "", user: null, isHydrated: true });
      expect(useAuthStore.getState().isAuthenticated()).toBe(false);
    });

    it("returns true when token is present", () => {
      useAuthStore.getState().setAuth("valid-token", mockUser);
      expect(useAuthStore.getState().isAuthenticated()).toBe(true);
    });
  });

  describe("login", () => {
    it("stores token and user on successful login", async () => {
      mockLogin.mockResolvedValue({ access_token: "new-token", token_type: "bearer" });
      mockGetMe.mockResolvedValue({ data: mockUser });

      await useAuthStore.getState().login({ username: "testuser", password: "secret" });

      expect(mockLogin).toHaveBeenCalledWith({ username: "testuser", password: "secret" });
      expect(mockGetMe).toHaveBeenCalledWith("new-token");
      expect(useAuthStore.getState().token).toBe("new-token");
      expect(useAuthStore.getState().user).toEqual(mockUser);
      expect(useAuthStore.getState().isAuthenticated()).toBe(true);
    });

    it("falls back to minimal user when getMe fails", async () => {
      mockLogin.mockResolvedValue({ access_token: "tok", token_type: "bearer" });
      mockGetMe.mockRejectedValue(new Error("network"));

      await useAuthStore.getState().login({ username: "testuser", password: "secret" });

      expect(useAuthStore.getState().token).toBe("tok");
      expect(useAuthStore.getState().user?.username).toBe("testuser");
    });

    it("sets error and throws on invalid credentials (no state change)", async () => {
      mockLogin.mockRejectedValue(new Error("Invalid credentials"));

      await expect(
        useAuthStore.getState().login({ username: "bad@example.com", password: "wrong" })
      ).rejects.toThrow("Invalid credentials");

      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
      expect(useAuthStore.getState().error).toBe("Invalid credentials");
      expect(useAuthStore.getState().isAuthenticated()).toBe(false);
    });

    it("sets error and throws on account locked (no state change)", async () => {
      mockLogin.mockRejectedValue(new Error("Account locked. Please contact your administrator."));

      await expect(
        useAuthStore.getState().login({ username: "locked@example.com", password: "any" })
      ).rejects.toThrow(/locked/);

      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
      expect(useAuthStore.getState().error).toMatch(/locked/);
    });

    it("sets isLoading back to false on success", async () => {
      mockLogin.mockResolvedValue({ access_token: "tok", token_type: "bearer" });
      mockGetMe.mockResolvedValue({ data: mockUser });

      await useAuthStore.getState().login({ username: "u", password: "p" });

      expect(useAuthStore.getState().isLoading).toBe(false);
      expect(useAuthStore.getState().error).toBeNull();
    });

    it("sets isLoading back to false on error path", async () => {
      mockLogin.mockRejectedValue(new Error("Invalid credentials"));

      await expect(
        useAuthStore.getState().login({ username: "u", password: "p" })
      ).rejects.toThrow();

      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it("clears prior error at the start of a new login attempt", async () => {
      useAuthStore.setState({ error: "old" });
      mockLogin.mockRejectedValue(new Error("Invalid credentials"));

      await expect(
        useAuthStore.getState().login({ username: "u", password: "p" })
      ).rejects.toThrow();

      // After failure, error is the new one, not the stale one
      expect(useAuthStore.getState().error).toBe("Invalid credentials");
    });
  });

  describe("logout", () => {
    it("clears auth state", () => {
      const store = useAuthStore.getState();
      store.setAuth("t", mockUser);
      store.logout();
      expect(useAuthStore.getState().token).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
      expect(useAuthStore.getState().isAuthenticated()).toBe(false);
    });
  });
});
