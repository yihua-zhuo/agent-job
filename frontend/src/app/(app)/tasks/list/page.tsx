"use client";
import { useState } from "react";
import { useTasks, useDeleteTask, useCompleteTask, useUpdateTask } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { TaskModal } from "../task-modal";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

type SortKey = "created_at" | "due_date" | "priority" | "title";
type SortDir = "asc" | "desc";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-500",
};
const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-800",
  urgent: "bg-red-100 text-red-800",
  normal: "bg-blue-100 text-blue-800",
  low: "bg-gray-100 text-gray-600",
};
const PRIORITY_ORDER: Record<string, number> = { urgent: 0, high: 1, normal: 2, low: 3 };

function SortIconStatic() {
  return <span className="text-muted-foreground">↕</span>;
}

export default function TaskListPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [createdAfter, setCreatedAfter] = useState("");
  const [createdBefore, setCreatedBefore] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [editTask, setEditTask] = useState<Record<string, unknown> | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const { data, isLoading, isError } = useTasks(page, statusFilter);
  const items = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;

  const complete = useCompleteTask();
  const remove = useDeleteTask();
  const update = useUpdateTask();

  function filteredAndSorted() {
    let result = items;
    if (priorityFilter) {
      result = result.filter((t) => t.priority === priorityFilter);
    }
    if (assigneeFilter) {
      const aid = Number(assigneeFilter);
      result = result.filter((t) => Number(t.assigned_to) === aid);
    }
    if (createdAfter) {
      const afterMs = new Date(createdAfter).getTime();
      result = result.filter((t) => {
        if (!t.created_at) return false;
        return new Date(String(t.created_at)).getTime() >= afterMs;
      });
    }
    if (createdBefore) {
      const beforeMs = new Date(createdBefore).getTime() + 86400000;
      result = result.filter((t) => {
        if (!t.created_at) return false;
        return new Date(String(t.created_at)).getTime() <= beforeMs;
      });
    }
    return result.slice().sort((a, b) => {
      if (sortKey === "due_date") {
        const va = a.due_date ? new Date(String(a.due_date)).getTime() : Infinity;
        const vb = b.due_date ? new Date(String(b.due_date)).getTime() : Infinity;
        return sortDir === "asc" ? va - vb : vb - va;
      }
      if (sortKey === "priority") {
        const va = PRIORITY_ORDER[String(a.priority)] ?? 9;
        const vb = PRIORITY_ORDER[String(b.priority)] ?? 9;
        return sortDir === "asc" ? va - vb : vb - va;
      }
      if (sortKey === "title") {
        const va = String(a.title ?? "").toLowerCase();
        const vb = String(b.title ?? "").toLowerCase();
        return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      }
      const va = String(a.created_at ?? "");
      const vb = String(b.created_at ?? "");
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => d === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    const displayed = filteredAndSorted();
    if (selectedIds.size === displayed.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(displayed.map((t) => Number(t.id))));
    }
  }

  async function bulkComplete() {
    for (const id of selectedIds) {
      await complete.mutateAsync(id);
    }
    setSelectedIds(new Set());
  }

  async function bulkDelete() {
    if (!window.confirm(`Delete ${selectedIds.size} task(s)?`)) return;
    for (const id of selectedIds) {
      await remove.mutateAsync(id);
    }
    setSelectedIds(new Set());
  }

  const displayed = filteredAndSorted();
  const allSelected = displayed.length > 0 && displayed.every((t) => selectedIds.has(Number(t.id)));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Task List</h1>
        {selectedIds.size > 0 && (
          <div className="flex gap-2">
            <Button size="sm" variant="default" onClick={bulkComplete}>
              Complete ({selectedIds.size})
            </Button>
            <Button size="sm" variant="destructive" onClick={bulkDelete}>
              Delete ({selectedIds.size})
            </Button>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All Statuses</SelectItem>
            <SelectItem value="pending">To Do</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="completed">Done</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>
        <Select value={priorityFilter} onValueChange={(v) => { setPriorityFilter(v); setPage(1); }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="All Priorities" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All Priorities</SelectItem>
            <SelectItem value="urgent">Urgent</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="normal">Normal</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>
        <Select value={assigneeFilter || "__none__"} onValueChange={(v) => { setAssigneeFilter(v === "__none__" ? "" : v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All Assignees" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">All Assignees</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span>Created:</span>
          <input
            type="date"
            value={createdAfter}
            onChange={(e) => { setCreatedAfter(e.target.value); setPage(1); }}
            className="rounded border px-2 py-1 text-sm"
            placeholder="From"
          />
          <span>–</span>
          <input
            type="date"
            value={createdBefore}
            onChange={(e) => { setCreatedBefore(e.target.value); setPage(1); }}
            className="rounded border px-2 py-1 text-sm"
            placeholder="To"
          />
        </div>
      </div>

      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-3 py-2 text-left w-8">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  className="cursor-pointer"
                  aria-label="Select all"
                />
              </th>
              <th className="px-3 py-2.5 text-left font-semibold">Title</th>
              <th className="px-3 py-2.5 text-left font-semibold">Status</th>
              <th className="px-3 py-2.5 text-left font-semibold">Priority</th>
              <th className="px-3 py-2.5 cursor-pointer text-left font-semibold select-none" onClick={() => toggleSort("due_date")}>
                Due Date <SortIconStatic />
              </th>
              <th className="px-3 py-2.5 cursor-pointer text-left font-semibold select-none" onClick={() => toggleSort("created_at")}>
                Created <SortIconStatic />
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} className="px-3 py-8 text-center text-muted-foreground">Loading…</td></tr>}
            {isError && <tr><td colSpan={7} className="px-3 py-8 text-center text-destructive">Failed to load tasks</td></tr>}
            {!isLoading && displayed.length === 0 && <tr><td colSpan={7} className="px-3 py-8 text-center text-muted-foreground">No tasks found</td></tr>}
            {displayed.map((t) => {
              const taskId = Number(t.id);
              const isSelected = selectedIds.has(taskId);
              return (
                <tr key={String(t.id)} className={cn(
                  "border-b hover:bg-muted/50 cursor-pointer transition-colors",
                  isSelected && "bg-primary/5"
                )} onClick={() => setEditTask(t)}>
                  <td className="px-3 py-2.5" onClick={(e) => { e.stopPropagation(); toggleSelect(taskId); }}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(taskId)}
                      className="cursor-pointer"
                      aria-label={`Select task ${t.id}`}
                    />
                  </td>
                  <td className="px-3 py-2.5 font-medium">{String(t.title ?? "")}</td>
                  <td className="px-3 py-2.5">
                    <Badge colorClass={STATUS_COLORS[String(t.status)] ?? "bg-gray-100 text-gray-600"}>
                      {t.status === "pending" ? "To Do" : t.status === "in_progress" ? "In Progress" : String(t.status ?? "")}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5">
                    <Badge colorClass={PRIORITY_COLORS[String(t.priority)] ?? "bg-gray-100 text-gray-600"}>
                      {String(t.priority ?? "normal")}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {t.due_date ? new Date(String(t.due_date)).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {t.created_at ? new Date(String(t.created_at)).toLocaleDateString() : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {info && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Showing {info.total === 0 ? 0 : ((page - 1) * 20) + 1}–{Math.min(page * 20, info.total)} of {info.total}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</Button>
            <Button variant="outline" size="sm" disabled={!info.has_next} onClick={() => setPage(page + 1)}>Next →</Button>
          </div>
        </div>
      )}

      {editTask && (
        <TaskModal
          open
          title="Task Details"
          task={editTask}
          onClose={() => setEditTask(null)}
          onSubmit={async (data) => {
            await update.mutateAsync({ id: Number(editTask.id), data });
            setEditTask(null);
          }}
          onComplete={editTask.status !== "completed" ? async () => {
            await complete.mutateAsync(Number(editTask.id));
            setEditTask(null);
          } : undefined}
          onDelete={editTask.id ? async () => {
            await remove.mutateAsync(Number(editTask.id));
            setEditTask(null);
          } : undefined}
          isSubmitting={false}
        />
      )}
    </div>
  );
}