import { create } from "zustand";
import { persist } from "zustand/middleware";
import CryptoJS from "crypto-js";

const STORAGE_KEY = "crm_auth";
const ENCRYPT_KEY = (() => {
  const key = process.env.NEXT_PUBLIC_AUTH_KEY;
  if (!key) {
    throw new Error(
      "NEXT_PUBLIC_AUTH_KEY is not set. Set it in .env.local before starting the app."
    );
  }
  if (!/^[A-Fa-f0-9]{32}$/.test(key)) {
    throw new Error("NEXT_PUBLIC_AUTH_KEY must be a 32-character hexadecimal string.");
  }
  return key;
})();

export interface AuthUser {
  id: number;
  tenant_id: number;
  username: string;
  email: string;
  role: string;
  status: string;
  full_name?: string;
  bio?: string;
  created_at?: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isHydrated: boolean;
  setAuth: (token: string, user: AuthUser) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

function encrypt(data: string): string {
  return CryptoJS.AES.encrypt(data, ENCRYPT_KEY).toString();
}

function decrypt(encrypted: string): string {
  const bytes = CryptoJS.AES.decrypt(encrypted, ENCRYPT_KEY);
  return bytes.toString(CryptoJS.enc.Utf8);
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isHydrated: true,
      setAuth: (token, user) => set({ token, user }),
      clearAuth: () => set({ token: null, user: null }),
      isAuthenticated: () => !!get().token,
    }),
    {
      name: STORAGE_KEY,
      storage: {
        getItem: (name) => {
          try {
            const raw = localStorage.getItem(name);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (parsed.encrypted && typeof parsed.ciphertext === "string") {
              const decrypted = decrypt(parsed.ciphertext);
              if (!decrypted) return null;
              return { state: JSON.parse(decrypted) };
            }
            return null;
          } catch {
            return null;
          }
        },
        setItem: (name, value) => {
          try {
            const json = JSON.stringify(value.state);
            const ciphertext = encrypt(json);
            localStorage.setItem(name, JSON.stringify({ encrypted: true, ciphertext }));
          } catch {
            // storage full or unavailable — fail silently
          }
        },
        removeItem: (name) => localStorage.removeItem(name),
      },
    }
  )
);
