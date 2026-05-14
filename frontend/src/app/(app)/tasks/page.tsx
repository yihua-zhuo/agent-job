"use client";
import { useState, useMemo } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
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

interface TaskData {
  id: string | number;
  title: string | null;
  description?: string | null;
  status: string;
  priority?: string | null;
  due_date?: string | null;
  [key: string]: unknown;
}

function TaskCard({
  task,
  onClick,
  onComplete,
  isDragging = false,
}: {
  task: TaskData;
  onClick: () => void;
  onComplete?: (id: number) => void;
  isDragging?: boolean;
}) {
  const due = task.due_date ? new Date(String(task.due_date)) : null;
  const isOverdue = due && due < new Date() && task.status !== "completed";
  const rawId = task.id;
  const taskId =
    typeof rawId === "number" && Number.isFinite(rawId)
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
      className={cn(
        "cursor-pointer hover:shadow-md transition-shadow group",
        isDragging && "opacity-50 ring-2 ring-primary"
      )}
      onClick={onClick}
      tabIndex={0}
      role="button"
      onKeyDown={handleKeyDown}
      aria-label={String(task.title ?? "Task")}
    >
      <CardContent className="p-3 space-y-2">
        <div className="flex items-start gap-2">
          {task.status !== "completed" && onComplete ? (
            <button
              type="button"
              onClick={handleComplete}
              className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border-2 border-muted-foreground/40 hover:border-green-500 hover:bg-green-500/10 transition-colors cursor-pointer"
              aria-label="Mark as complete"
              title="Mark complete"
            />
          ) : task.status === "completed" ? (
            <div
              className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-green-500"
              aria-label="Completed"
            >
              <svg
                className="h-2.5 w-2.5 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={3}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
          ) : (
            <div className="mt-0.5 flex h-4 w-4 flex-shrink-0" />
          )}
          <div
            className={cn(
              "font-medium text-sm leading-snug flex-1",
              task.status === "completed" && "line-through text-muted-foreground"
            )}
          >
            {String(task.title ?? "")}
          </div>
        </div>
        {task.description && (
          <p className="text-xs text-muted-foreground line-clamp-2">
            {String(task.description)}
          </p>
        )}
        <div className="flex items-center justify-between">
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
              PRIORITY_COLORS[String(task.priority)] ?? "bg-gray-100 text-gray-600"
            )}
          >
            {String(task.priority ?? "normal")}
          </span>
          {due && (
            <span
              className={cn(
                "text-xs",
                isOverdue ? "text-red-500 font-semibold" : "text-muted-foreground"
              )}
            >
              {isOverdue ? `⚠ ${due.toLocaleDateString()}` : due.toLocaleDateString()}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function DraggableTaskCard({
  task,
  onClick,
  onComplete,
}: {
  task: TaskData;
  onClick: () => void;
  onComplete?: (id: number) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: String(task.id) });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <TaskCard
        task={task}
        onClick={onClick}
        onComplete={onComplete}
        isDragging={isDragging}
      />
    </div>
  );
}

export default function TasksPage() {
  const [editTask, setEditTask] = useState<TaskData | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createStatus, setCreateStatus] = useState("pending");
  const [activeTaskId, setActiveTaskId] = useState<string | number | null>(null);

  const { data: allData, isLoading } = useTasks(1, "");

  const create = useCreateTask();
  const update = useUpdateTask();
  const complete = useCompleteTask();
  const remove = useDeleteTask();

  const allTasks = (allData?.data?.items ?? []) as TaskData[];

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const t of allTasks) {
      counts[t.status] = (counts[t.status] ?? 0) + 1;
    }
    return counts;
  }, [allTasks]);

  const tasksByStatus = useMemo(() => {
    const m: Record<string, TaskData[]> = {};
    for (const col of COLUMNS) m[col.id] = allTasks.filter((t) => t.status === col.id);
    return m;
  }, [allTasks]);

  function countByStatus(status: string) {
    return statusCounts[status] ?? 0;
  }

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    })
  );

  function handleDragStart(event: DragStartEvent) {
    setActiveTaskId(event.active.id);
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const taskId = Number(active.id);
    const newStatus = over.id as string;
    await update.mutateAsync({ id: taskId, data: { status: newStatus } });
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

  const activeTask =
    activeTaskId !== null
      ? allTasks.find((t) => String(t.id) === String(activeTaskId))
      : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <Button
          size="sm"
          onClick={() => {
            setCreateStatus("pending");
            setShowCreate(true);
          }}
        >
          + Add Task
        </Button>
      </div>

      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}
        >
          {COLUMNS.map((col) => (
            <div key={col.id} className="flex flex-col gap-2">
              <div
                className={cn(
                  "flex items-center justify-between rounded-t-md border-x border-t px-3 py-2",
                  col.borderColor,
                  "border-b-0 bg-muted/30"
                )}
              >
                <span className={cn("font-semibold text-sm", col.color)}>
                  {col.label}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-muted-foreground">
                    {countByStatus(col.id)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => {
                      setCreateStatus(col.id);
                      setShowCreate(true);
                    }}
                    aria-label="Add task"
                    title="Add task"
                  >
                    +
                  </Button>
                </div>
              </div>
              <SortableContext
                items={tasksByStatus[col.id].map((t) => String(t.id))}
                strategy={verticalListSortingStrategy}
              >
                <div
                  data-column={col.id}
                  className={cn(
                    "flex-1 space-y-2 rounded-b-md border p-2 overflow-y-auto",
                    col.borderColor
                  )}
                  style={{ maxHeight: "calc(100vh - 240px)" }}
                >
                  {isLoading ? (
                    <div className="py-8 text-center text-sm text-muted-foreground">
                      Loading…
                    </div>
                  ) : tasksByStatus[col.id].length === 0 ? (
                    <div className="py-8 text-center text-sm text-muted-foreground">
                      No tasks
                    </div>
                  ) : (
                    tasksByStatus[col.id].map((t) => (
                      <DraggableTaskCard
                        key={String(t.id)}
                        task={t}
                        onClick={() => setEditTask(t)}
                        onComplete={handleComplete}
                      />
                    ))
                  )}
                </div>
              </SortableContext>
            </div>
          ))}
        </div>

        <DragOverlay>
          {activeTask && (
            <TaskCard
              task={activeTask}
              onClick={() => {}}
              isDragging
            />
          )}
        </DragOverlay>
      </DndContext>

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
          onComplete={
            editTask.status !== "completed"
              ? () => handleComplete(Number(editTask.id))
              : undefined
          }
          onDelete={editTask.id ? () => handleDelete(Number(editTask.id)) : undefined}
          isSubmitting={update.isPending}
        />
      )}
    </div>
  );
}