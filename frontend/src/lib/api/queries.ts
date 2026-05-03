import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api-client";
import { useAuthStore } from "../store/auth-store";

export const qk = {
  me: () => ["me"] as const,
  customers: (page = 1) => ["customers", page] as const,
  customer: (id: number) => ["customer", id] as const,
  opportunities: (page = 1) => ["opportunities", page] as const,
  pipelines: () => ["pipelines"] as const,
  tickets: (page = 1, status = "") => ["tickets", page, status] as const,
  tasks: (page = 1, status = "") => ["tasks", page, status] as const,
  task: (id: number) => ["task", id] as const,
  users: (page = 1) => ["users", page] as const,
} as const;

// ── Auth ──────────────────────────────────────────────────────────────────────
export function useCurrentUser() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.me(),
    queryFn: () => import("../api/auth").then((m) => m.getMe(token ?? "")),
    enabled: !!token,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

// ── Customers ──────────────────────────────────────────────────────────────
export function useCustomers(page = 1) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.customers(page),
    queryFn: () => apiClient.get(`/api/v1/customers?page=${page}&page_size=20`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useCustomer(id: number) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.customer(id),
    queryFn: () => apiClient.get(`/api/v1/customers/${id}`, token ?? undefined),
    enabled: id > 0,
  });
}

export function useSearchCustomers(keyword: string) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: ["customers", "search", keyword],
    queryFn: () => apiClient.get(`/api/v1/customers/search?keyword=${encodeURIComponent(keyword)}`, token ?? undefined),
    enabled: keyword.length > 0,
  });
}

export function useCreateCustomer() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient.post("/api/v1/customers", data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

// ── Opportunities ─────────────────────────────────────────────────────────
export function useOpportunities(page = 1) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.opportunities(page),
    queryFn: () => apiClient.get(`/api/v1/sales/opportunities?page=${page}&page_size=20`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function usePipelines() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.pipelines(),
    queryFn: () => apiClient.get("/api/v1/sales/pipelines", token ?? undefined),
    staleTime: 60 * 1000,
  });
}

export function useCreateOpportunity() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient.post("/api/v1/sales/opportunities", data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["opportunities"] }),
  });
}

// ── Tickets ─────────────────────────────────────────────────────────────────
export function useTickets(page = 1, status = "") {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (status) params.set("status", status);
  return useQuery({
    queryKey: qk.tickets(page, status),
    queryFn: () => apiClient.get(`/api/v1/tickets?${params}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useCreateTicket() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient.post("/api/v1/tickets", data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tickets"] }),
  });
}

// ── Users ───────────────────────────────────────────────────────────────────
export function useUsers(page = 1) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.users(page),
    queryFn: () => apiClient.get(`/api/v1/users?page=${page}&page_size=20`, token ?? undefined),
    staleTime: 60 * 1000,
  });
}
// ── Tasks ───────────────────────────────────────────────────────────────────

export function useTasks(page = 1, status = "") {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (status) params.set("status", status);
  return useQuery({
    queryKey: qk.tasks(page, status),
    queryFn: () => apiClient.get(`/api/v1/tasks?${params}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useTask(id: number) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.task(id),
    queryFn: () => apiClient.get(`/api/v1/tasks/${id}`, token ?? undefined),
    enabled: id > 0,
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient.post("/api/v1/tasks", data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      apiClient.patch(`/api/v1/tasks/${id}`, data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useCompleteTask() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (id: number) =>
      apiClient.post(`/api/v1/tasks/${id}/complete`, null, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (id: number) =>
      apiClient.delete(`/api/v1/tasks/${id}`, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}
