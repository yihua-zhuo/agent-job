"use client";
import { useState } from "react";
import { useTasks, useCreateTask, useUpdateTask, useCompleteTask, useDeleteTask } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TaskModal } from "./task-modal";
import { cn } from "@/lib/utils";

const COLUMNS = [
  { id: "pending", label: "To Do", color: "text-blue-600", borderColor: "border-blue-400" },
  { id: "in_progress", label: "In Progress", color: "text-yellow-600", borderColor: "border-yellow-400" },
  { id: "completed", label: "Done", color: "text-green-600", borderColor: "border-green-400" },
];

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-800",
  urgent: "bg-red-100 text-red-800",
  normal: "bg-blue-100 text-blue-800",
  low: "bg-gray-100 text-gray-600",
};

function TaskCard({ task, onClick, onComplete }: {
  task: Record<string, unknown>;
  onClick: () => void;
  onComplete?: (id: number) => void;
}) {
  const due = task.due_date ? new Date(String(task.due_date)) : null;
  const isOverdue = due && due < new Date() && task.status !== "completed";
  const rawId = task.id;
  const taskId = typeof rawId === "number" && Number.isFinite(rawId)
    ? rawId
    : typeof rawId === "string" && /^\d+$/.test(rawId.trim())
    ? Number(rawId)
    : null;

  function handleComplete(e: React.MouseEvent) {
    e.stopPropagation();
    if (taskId === null) return;
    onComplete?.(taskId);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  }

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow group"
      onClick={onClick}
      tabIndex={0}
      role="button"
      onKeyDown={handleKeyDown}
      aria-label={String(task.title ?? "Task")}
    >
      <CardContent className="p-3 space-y-2">
        <div className="flex items-start gap-2">
          {task.status !== "completed" && onComplete && (
            <button
              type="button"
              onClick={handleComplete}
              className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border-2 border-muted-foreground/40 hover:border-green-500 hover:bg-green-500/10 transition-colors cursor-pointer"
              aria-label="Mark as complete"
              title="Mark complete"
            />
          )}
          {task.status === "completed" && (
            <div className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-green-500" aria-label="Completed">
              <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
          )}
          <div className={cn("font-medium text-sm leading-snug flex-1", task.status === "completed" && "line-through text-muted-foreground")}>
            {String(task.title ?? "")}
          </div>
        </div>
        {Boolean(task.description) && (
          <p className="text-xs text-muted-foreground line-clamp-2">{String(task.description)}</p>
        )}
        <div className="flex items-center justify-between">
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${PRIORITY_COLORS[String(task.priority)] ?? "bg-gray-100 text-gray-600"}`}>
            {String(task.priority ?? "normal")}
          </span>
          {due && (
            <span className={`text-xs ${isOverdue ? "text-red-500 font-semibold" : "text-muted-foreground"}`}>
              {isOverdue ? `⚠ ${due.toLocaleDateString()}` : due.toLocaleDateString()}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function TasksPage() {
  const [editTask, setEditTask] = useState<Record<string, unknown> | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createStatus, setCreateStatus] = useState("pending");

  const { data: allData, isLoading } = useTasks(1, "");
  const { data: pendingData } = useTasks(1, "pending");
  const { data: progressData } = useTasks(1, "in_progress");
  const { data: completedData } = useTasks(1, "completed");

  const create = useCreateTask();
  const update = useUpdateTask();
  const complete = useCompleteTask();
  const remove = useDeleteTask();

  const allTasks = (allData?.data?.items ?? []) as Record<string, unknown>[];

  function tasksByStatus(status: string) {
    return allTasks.filter((t) => t.status === status);
  }

  function countByStatus(status: string) {
    if (status === "pending") return pendingData?.data?.total ?? 0;
    if (status === "in_progress") return progressData?.data?.total ?? 0;
    if (status === "completed") return completedData?.data?.total ?? 0;
    return 0;
  }

  async function handleCreate(data: Record<string, unknown>) {
    await create.mutateAsync({ ...data, status: createStatus });
    setShowCreate(false);
  }

  async function handleUpdate(id: number, data: Record<string, unknown>) {
    await update.mutateAsync({ id, data });
    setEditTask(null);
  }

  async function handleComplete(id: number) {
    await complete.mutateAsync(id);
    setEditTask(null);
  }

  async function handleDelete(id: number) {
    await remove.mutateAsync(id);
    setEditTask(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <Button size="sm" onClick={() => { setCreateStatus("pending"); setShowCreate(true); }}>
          + Add Task
        </Button>
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
        {COLUMNS.map((col) => (
          <div key={col.id} className="flex flex-col gap-2">
            <div className={`flex items-center justify-between rounded-t-md border-x border-t px-3 py-2 ${col.borderColor} border-b-0 bg-muted/30`}>
              <span className={`font-semibold text-sm ${col.color}`}>{col.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground">{countByStatus(col.id)}</span>
                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => { setCreateStatus(col.id); setShowCreate(true); }} title="Add task">
                  +
                </Button>
              </div>
            </div>
            <div className={`flex-1 space-y-2 rounded-b-md border p-2 ${col.borderColor} overflow-y-auto`} style={{ maxHeight: "calc(100vh - 240px)" }}>
              {isLoading ? (
                <div className="py-8 text-center text-sm text-muted-foreground">Loading…</div>
              ) : tasksByStatus(col.id).length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">No tasks</div>
              ) : (
                tasksByStatus(col.id).map((t) => (
                  <TaskCard
                    key={String(t.id)}
                    task={t}
                    onClick={() => setEditTask(t)}
                    onComplete={handleComplete}
                  />
                ))
              )}
            </div>
          </div>
        ))}
      </div>

      <TaskModal
        open={showCreate}
        title="Create Task"
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
        isSubmitting={create.isPending}
        initialStatus={createStatus}
      />

      {editTask && (
        <TaskModal
          open
          title="Task Details"
          task={editTask}
          onClose={() => setEditTask(null)}
          onSubmit={(data) => handleUpdate(Number(editTask.id), data)}
          onComplete={editTask.status !== "completed" ? () => handleComplete(Number(editTask.id)) : undefined}
          onDelete={editTask.id ? () => handleDelete(Number(editTask.id)) : undefined}
          isSubmitting={update.isPending}
        />
      )}
    </div>
  );
}
