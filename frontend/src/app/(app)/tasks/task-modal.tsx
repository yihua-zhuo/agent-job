"use client";
import { useState } from "react";
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
  });

  const isEdit = !!task;

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
    await onSubmit(payload);
  }

  async function handleDelete() {
    if (!onDelete) return;
    if (!window.confirm("Delete this task?")) return;
    await onDelete();
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="task-title">Title *</label>
            <Input
              id="task-title"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Task title"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="task-desc">Description</label>
            <Textarea
              id="task-desc"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Description (optional)"
              rows={3}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="task-priority">Priority</label>
              <Select value={form.priority} onValueChange={(v) => setForm((f) => ({ ...f, priority: v }))}>
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
              <Select value={form.status} onValueChange={(v) => setForm((f) => ({ ...f, status: v }))}>
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
            <label className="text-sm font-medium" htmlFor="task-due">Due Date</label>
            <Input
              id="task-due"
              type="date"
              value={form.due_date}
              onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
            />
          </div>
          <DialogFooter className="flex-row! justify-between gap-2 sm:justify-between">
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
