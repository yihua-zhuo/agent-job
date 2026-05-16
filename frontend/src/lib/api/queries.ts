import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api-client";
import { useAuthStore } from "../store/auth-store";

export const qk = {
  me: () => ["me"] as const,
  customers: (page = 1) => ["customers", page] as const,
  customer: (id: number) => ["customer", id] as const,
  opportunities: (page = 1, pageSize = 20) => ["opportunities", page, pageSize] as const,
  pipelines: () => ["pipelines"] as const,
  tickets: (page = 1, status = "") => ["tickets", page, status] as const,
  ticket: (id: number) => ["ticket", id] as const,
  ticketReplies: (ticketId: number) => ["ticket", ticketId, "replies"] as const,
  ticketActivity: (ticketId: number) => ["ticket", ticketId, "activity"] as const,
  tasks: (page = 1, status = "") => ["tasks", page, status] as const,
  task: (id: number) => ["task", id] as const,
  users: (page = 1, page_size = 20) => ["users", page, page_size] as const,
  notifications: (page = 1, unreadOnly = false) => ["notifications", page, unreadOnly] as const,
  reminders: (upcomingOnly = false) => ["reminders", upcomingOnly] as const,
  activities: (page = 1, type = "") => ["activities", page, type] as const,
  slaBreaches: () => ["sla", "breaches"] as const,
  automationRules: (page = 1, pageSize = 20) => ["automation_rules", page, pageSize] as const,
  automationRule: (id: number) => ["automation_rules", "detail", id] as const,
  automationLogs: (page = 1, pageSize = 20, ruleId?: number, status?: string) => ["automation_logs", page, pageSize, ruleId ?? null, status ?? ""] as const,
} as const;

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

interface ApiEnvelope<T> {
  success: boolean;
  message?: string;
  data: PaginatedResponse<T>;
}

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
export function useCustomers(page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.customers(page),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/customers?page=${page}&page_size=${pageSize}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useCustomer(id: number) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.customer(id),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/customers/${id}`, token ?? undefined),
    enabled: id > 0,
  });
}

export function useSearchCustomers(keyword: string) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: ["customers", "search", keyword],
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/customers/search?keyword=${encodeURIComponent(keyword)}`, token ?? undefined),
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

export function useDeleteCustomer() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (id: number) =>
      apiClient.delete(`/api/v1/customers/${id}`, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

// ── Opportunities ─────────────────────────────────────────────────────────
export function useOpportunities(page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.opportunities(page, pageSize),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/sales/opportunities?page=${page}&page_size=${pageSize}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function usePipelines() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.pipelines(),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/sales/pipelines`, token ?? undefined),
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
export function useTickets(page = 1, pageSize = 20, status = "") {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (status) params.set("status", status);
  return useQuery({
    queryKey: qk.tickets(page, status),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/tickets?${params}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useDeleteTicket() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (id: number) =>
      apiClient.delete(`/api/v1/tickets/${id}`, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tickets"] }),
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

export function useTicket(id: number) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.ticket(id),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/tickets/${id}`, token ?? undefined),
    enabled: id > 0,
    staleTime: 30 * 1000,
  });
}

export function useTicketReplies(ticketId: number) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.ticketReplies(ticketId),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/tickets/${ticketId}/replies`, token ?? undefined),
    enabled: ticketId > 0,
    staleTime: 30 * 1000,
  });
}

export function useTicketActivity(ticketId: number) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.ticketActivity(ticketId),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/tickets/${ticketId}/activity`, token ?? undefined),
    enabled: ticketId > 0,
    staleTime: 30 * 1000,
  });
}

export function useAddReply() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: ({ ticketId, data }: { ticketId: number; data: Record<string, unknown> }) =>
      apiClient.post(`/api/v1/tickets/${ticketId}/replies`, data, token ?? undefined),
    onSuccess: (_res, vars) => {
      qc.invalidateQueries({ queryKey: qk.ticketReplies(vars.ticketId) });
      qc.invalidateQueries({ queryKey: qk.ticketActivity(vars.ticketId) });
    },
  });
}

export function useUpdateTicket() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      apiClient.put(`/api/v1/tickets/${id}`, data, token ?? undefined),
    onSuccess: (_res, vars) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: qk.ticket(vars.id) });
    },
  });
}

export function useChangeTicketStatus() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: ({ ticketId, newStatus }: { ticketId: number; newStatus: string }) =>
      apiClient.put(`/api/v1/tickets/${ticketId}/status`, { new_status: newStatus }, token ?? undefined),
    onSuccess: (_res, vars) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: qk.ticket(vars.ticketId) });
    },
  });
}

export function useBulkUpdateTickets() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: { ticket_ids: number[]; assigned_to?: number; status?: string }) =>
      apiClient.post("/api/v1/tickets/bulk-update", data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tickets"] }),
  });
}

export function useAutoAssignTicket() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (ticketId: number) =>
      apiClient.post(`/api/v1/tickets/${ticketId}/auto-assign`, {}, token ?? undefined),
    onSuccess: (_res, ticketId) => {
      qc.invalidateQueries({ queryKey: ["tickets"] });
      qc.invalidateQueries({ queryKey: qk.ticket(ticketId) });
    },
  });
}

// ── Users ───────────────────────────────────────────────────────────────────
export function useUsers(page = 1, page_size = 20) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.users(page, page_size),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/users?page=${page}&page_size=${page_size}`, token ?? undefined),
    staleTime: 60 * 1000,
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: { full_name?: string; email?: string; bio?: string }) =>
      apiClient.patch("/api/v1/users/me", data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me() }),
  });
}

export function useChangePassword() {
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: { old_password: string; new_password: string }) =>
      apiClient.post("/api/v1/auth/change-password", data, token ?? undefined),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      apiClient.put(`/api/v1/users/${id}`, data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (id: number) =>
      apiClient.delete(`/api/v1/users/${id}`, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient.post("/api/v1/users", data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}
// ── Tasks ───────────────────────────────────────────────────────────────────

export function useTasks(page = 1, status = "", priority = "", assigned_to = "", createdAfter = "", createdBefore = "") {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (status) params.set("status", status);
  if (priority) params.set("priority", priority);
  if (assigned_to) params.set("assigned_to", assigned_to);
  if (createdAfter) params.set("created_after", createdAfter);
  if (createdBefore) params.set("created_before", createdBefore);
  return useQuery({
    queryKey: qk.tasks(page, status),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/tasks?${params}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useTask(id: number) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.task(id),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/tasks/${id}`, token ?? undefined),
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

// ── Activities ───────────────────────────────────────────────────────────
export function useActivities(page = 1, type = "") {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (type) params.set("activity_type", type);
  return useQuery({
    queryKey: qk.activities(page, type),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/activities?${params}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useActivity(id: number) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: ["activity", id] as const,
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/activities/${id}`, token ?? undefined),
    enabled: id > 0,
  });
}

export function useSlaBreaches() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.slaBreaches(),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>("/api/v1/sla/breaches", token ?? undefined),
    staleTime: 30 * 1000,
  });
}

// ── Notifications ─────────────────────────────────────────────────────────
export function useNotifications(page = 1, unreadOnly = false) {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (unreadOnly) params.set("unread_only", "true");
  return useQuery({
    queryKey: qk.notifications(page, unreadOnly),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/notifications?${params}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: () => apiClient.post("/api/v1/notifications/mark-all-read", {}, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (id: number) =>
      apiClient.put(`/api/v1/notifications/${id}/read`, {}, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

// ── Reminders ─────────────────────────────────────────────────────────────
export function useReminders(upcomingOnly = false) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.reminders(upcomingOnly),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>(`/api/v1/reminders?upcoming_only=${upcomingOnly}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useCreateReminder() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient.post("/api/v1/reminders", data, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reminders"] }),
  });
}

export function useDeleteReminder() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (id: number) =>
      apiClient.delete(`/api/v1/reminders/${id}`, token ?? undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reminders"] }),
  });
}

// ── Automation Rules ───────────────────────────────────────────────────────

export function useAutomationRules(page = 1, pageSize = 20) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.automationRules(page, pageSize),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/automation/rules?page=${page}&page_size=${pageSize}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}

export function useAutomationRule(id: number) {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: qk.automationRule(id),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/automation/rules/${id}`, token ?? undefined),
    enabled: id > 0,
  });
}

export function useCreateAutomationRule() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient.post("/api/v1/automation/rules", data, token ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automation_rules"] });
      qc.invalidateQueries({ queryKey: ["automation_logs"] });
    },
  });
}

export function useUpdateAutomationRule() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Record<string, unknown> }) =>
      apiClient.put(`/api/v1/automation/rules/${id}`, data, token ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automation_rules"] });
      qc.invalidateQueries({ queryKey: ["automation_logs"] });
    },
  });
}

export function useDeleteAutomationRule() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (id: number) =>
      apiClient.delete(`/api/v1/automation/rules/${id}`, token ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automation_rules"] });
      qc.invalidateQueries({ queryKey: ["automation_logs"] });
    },
  });
}

export function useToggleAutomationRule() {
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.token);
  return useMutation({
    mutationFn: (id: number) =>
      apiClient.post(`/api/v1/automation/rules/${id}/toggle`, {}, token ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automation_rules"] });
      qc.invalidateQueries({ queryKey: ["automation_logs"] });
    },
  });
}

export function useAutomationLogs(page = 1, pageSize = 20, ruleId?: number, status?: string) {
  const token = useAuthStore((s) => s.token);
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (ruleId != null) params.set("rule_id", String(ruleId));
  if (status) params.set("status", status);
  return useQuery({
    queryKey: qk.automationLogs(page, pageSize, ruleId, status),
    queryFn: () => apiClient.get<ApiEnvelope<Record<string, unknown>>>(`/api/v1/automation/logs?${params}`, token ?? undefined),
    staleTime: 30 * 1000,
  });
}
