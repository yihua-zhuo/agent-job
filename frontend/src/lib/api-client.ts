const API_BASE =
  process.env.NODE_ENV === "production"
    ? (process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://agent-job-production.up.railway.app")
    : (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isUnauthorized() { return this.status === 401; }
  get isForbidden()    { return this.status === 403; }
  get isNotFound()     { return this.status === 404; }
  get isValidation()   { return this.status === 422; }
}

export const apiClient = {
  baseUrl: API_BASE,

  async request<T>(path: string, options: RequestInit & { token?: string } = {}): Promise<T> {
    const { token, ...fetchOptions } = options;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(fetchOptions.headers as Record<string, string> || {}),
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...fetchOptions,
      headers,
      credentials: "include",
    });

    if (!response.ok) {
      let message = response.statusText;
      let body: unknown;
      try { body = await response.json(); } catch { body = {}; }
      if (body && typeof body === "object" && "message" in body) {
        message = (body as { message: string }).message;
      }
      throw new ApiError(response.status, message, body);
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return response.text() as unknown as T;
    }
    return response.json() as Promise<T>;
  },

  get<T>(path: string, token?: string) {
    return this.request<T>(path, { method: "GET", token });
  },
  post<T>(path: string, body: unknown, token?: string) {
    return this.request<T>(path, { method: "POST", body: JSON.stringify(body), token });
  },
  put<T>(path: string, body: unknown, token?: string) {
    return this.request<T>(path, { method: "PUT", body: JSON.stringify(body), token });
  },
  patch<T>(path: string, body: unknown, token?: string) {
    return this.request<T>(path, { method: "PATCH", body: JSON.stringify(body), token });
  },
  delete<T>(path: string, token?: string) {
    return this.request<T>(path, { method: "DELETE", token });
  },
};
