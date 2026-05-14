"use client";
import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useUsers, useSearchCustomers, useOpportunities } from "@/lib/api/queries";
import { Eye, Edit2 } from "lucide-react";

interface TaskModalProps {
  open: boolean;
  title: string;
  task?: Record<string, unknown>;
  onClose: () => void;
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
  onComplete?: () => Promise<void>;
  onDelete?: () => Promise<void>;
  isSubmitting?: boolean;
  initialStatus?: string;
}

export function TaskModal({
  open,
  title,
  task,
  onClose,
  onSubmit,
  onComplete,
  onDelete,
  isSubmitting,
  initialStatus,
}: TaskModalProps) {
  const [form, setForm] = useState({
    title: task ? String(task.title ?? "") : "",
    description: task ? String(task.description ?? "") : "",
    priority: task ? String(task.priority ?? "normal") : "normal",
    status: task ? String(task.status ?? "pending") : initialStatus ?? "pending",
    due_date: task && task.due_date ? String(task.due_date).slice(0, 10) : "",
    assigned_to: task ? String(task.assigned_to ?? "0") : "0",
    customer_id: task ? String(task.customer_id ?? "") : "",
    opportunity_id: task ? String(task.opportunity_id ?? "") : "",
  });
  const [previewDesc, setPreviewDesc] = useState(false);
  const [customerSearch, setCustomerSearch] = useState<string | undefined>(undefined);

  const { data: usersData } = useUsers(1);
  const { data: opportunitiesData } = useOpportunities(1);

  const [debouncedSearch, setDebouncedSearch] = useState<string | undefined>(undefined);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(customerSearch), 300);
    return () => clearTimeout(timer);
  }, [customerSearch]);

  const { data: customerData } = useSearchCustomers(debouncedSearch);

  const isEdit = !!task;

  function setFormField(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) return;
    const payload: Record<string, unknown> = {
      title: form.title.trim(),
      description: form.description.trim(),
      priority: form.priority,
      status: form.status,
    };
    if (form.due_date) payload.due_date = form.due_date;
    if (form.assigned_to && form.assigned_to !== "0") {
      payload.assigned_to = Number(form.assigned_to);
    }
    if (form.customer_id) payload.customer_id = Number(form.customer_id);
    if (form.opportunity_id) payload.opportunity_id = Number(form.opportunity_id);
    await onSubmit(payload);
  }

  async function handleDelete() {
    if (!onDelete) return;
    if (!window.confirm("Delete this task?")) return;
    await onDelete();
  }

  const users = (usersData?.data?.items ?? []) as Record<string, unknown>[];
  const customers = (customerData?.data?.items ?? []) as Record<string, unknown>[];
  const opportunities = (opportunitiesData?.data?.items ?? []) as Record<string, unknown>[];

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="task-title">Title *</label>
            <Input
              id="task-title"
              value={form.title}
              onChange={(e) => setFormField("title", e.target.value)}
              placeholder="Task title"
              required
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium" htmlFor="task-desc">Description</label>
              <button
                type="button"
                onClick={() => setPreviewDesc((p) => !p)}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                title={previewDesc ? "Edit description" : "Preview markdown"}
              >
                {previewDesc ? (
                  <><Edit2 className="h-3 w-3" /> Edit</>
                ) : (
                  <><Eye className="h-3 w-3" /> Preview</>
                )}
              </button>
            </div>
            {previewDesc ? (
              <div className="rounded-md border bg-muted/30 p-3 min-h-[80px] text-sm prose prose-sm dark:prose-invert max-w-none">
                {form.description ? (
                  <ReactMarkdown>{form.description}</ReactMarkdown>
                ) : (
                  <span className="text-muted-foreground italic">No description</span>
                )}
              </div>
            ) : (
              <Textarea
                id="task-desc"
                value={form.description}
                onChange={(e) => setFormField("description", e.target.value)}
                placeholder="Description (markdown supported)"
                rows={3}
              />
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="task-priority">Priority</label>
              <Select value={form.priority} onValueChange={(v) => setFormField("priority", v)}>
                <SelectTrigger id="task-priority">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="urgent">Urgent</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="task-status">Status</label>
              <Select value={form.status} onValueChange={(v) => setFormField("status", v)}>
                <SelectTrigger id="task-status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">To Do</SelectItem>
                  <SelectItem value="in_progress">In Progress</SelectItem>
                  <SelectItem value="completed">Done</SelectItem>
                  <SelectItem value="cancelled">Cancelled</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="task-assignee">Assignee</label>
            <Select value={form.assigned_to} onValueChange={(v) => setFormField("assigned_to", v)}>
              <SelectTrigger id="task-assignee">
                <SelectValue placeholder="Unassigned" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0">Unassigned</SelectItem>
                {users.map((u) => (
                  <SelectItem key={String(u.id)} value={String(u.id)}>
                    {String(u.full_name ?? u.username ?? u.email ?? u.id)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="task-due">Due Date</label>
            <Input
              id="task-due"
              type="date"
              value={form.due_date}
              onChange={(e) => setFormField("due_date", e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="task-customer">Customer</label>
              <Select
                value={form.customer_id || "__none__"}
                onValueChange={(v) => setFormField("customer_id", v === "__none__" ? "" : v)}
              >
                <SelectTrigger id="task-customer">
                  <SelectValue placeholder="Search customer..." />
                </SelectTrigger>
                <SelectContent>
                  <div className="px-2 py-1.5">
                    <Input
                      placeholder="Search customers..."
                      value={customerSearch ?? ""}
                      onChange={(e) => {
                        setCustomerSearch(e.target.value);
                      }}
                      className="h-8"
                    />
                  </div>
                  <SelectItem value="__none__">None</SelectItem>
                  {customers.map((c) => (
                    <SelectItem key={String(c.id)} value={String(c.id)}>
                      {String(c.name ?? c.company_name ?? c.id)}
                    </SelectItem>
                  ))}
                  {customerData && customers.length === 0 && (
                    <div className="px-2 py-1.5 text-xs text-muted-foreground">No customers found</div>
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="task-opportunity">Opportunity</label>
              <Select
                value={form.opportunity_id || "0"}
                onValueChange={(v) => setFormField("opportunity_id", v === "0" ? "" : v)}
              >
                <SelectTrigger id="task-opportunity">
                  <SelectValue placeholder="None" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">None</SelectItem>
                  {opportunities.map((o) => (
                    <SelectItem key={String(o.id)} value={String(o.id)}>
                      {String(o.title ?? o.id)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter className="flex flex-row justify-between gap-2 sm:justify-between">
            <div>
              {isEdit && onComplete && (
                <Button type="button" size="sm" onClick={onComplete} disabled={isSubmitting}>
                  Mark Complete
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              {isEdit && onDelete && (
                <Button type="button" variant="destructive" size="sm" onClick={handleDelete}>
                  Delete
                </Button>
              )}
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Saving…" : isEdit ? "Save" : "Create"}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}