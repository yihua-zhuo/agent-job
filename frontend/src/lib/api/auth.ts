import { apiClient } from "../api-client";

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface MeResponse {
  success: boolean;
  message: string;
  data: {
    id: number;
    tenant_id: number;
    username: string;
    email: string;
    role: string;
    status: string;
    full_name?: string;
    bio?: string;
    created_at?: string;
    updated_at?: string;
  };
}

export async function login(credentials: LoginCredentials): Promise<LoginResponse> {
  const form = new URLSearchParams({
    username: credentials.username,
    password: credentials.password,
  });
  const response = await fetch(`${apiClient.baseUrl}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
    credentials: "include",
  });
  if (!response.ok) {
    let message = response.statusText;
    try { const b = await response.json(); if (b?.detail) message = b.detail; } catch { /* ignore */ }
    throw new Error(message);
  }
  return response.json() as Promise<LoginResponse>;
}

export async function getMe(token: string): Promise<MeResponse> {
  return apiClient.get<MeResponse>("/api/v1/users/me", token);
}
