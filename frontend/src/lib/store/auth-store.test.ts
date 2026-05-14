import { describe, it, expect, vi, beforeEach } from "vitest";
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

describe("auth-store", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null, isHydrated: true });
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
});