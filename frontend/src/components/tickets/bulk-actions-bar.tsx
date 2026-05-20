"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useUsers, useBulkUpdateTickets } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { X } from "lucide-react";

interface BulkActionsBarProps {
  selectedIds: Set<number>;
  onClear: () => void;
}

export function BulkActionsBar({ selectedIds, onClear }: BulkActionsBarProps) {
  const [assigneeId, setAssigneeId] = useState<string>("");
  const [newStatus, setNewStatus] = useState<string>("");

  const { data: usersData } = useUsers(1, 100);
  const bulkUpdate = useBulkUpdateTickets();

  const users = usersData?.data?.items ?? [];

  if (selectedIds.size === 0) return null;

  async function handleApply() {
    if (!assigneeId && !newStatus) {
      toast.error("Select at least one action to apply");
      return;
    }
    try {
      const payload: { ticket_ids: number[]; assigned_to?: number | null; status?: string } = {
        ticket_ids: Array.from(selectedIds),
      };
      if (assigneeId) payload.assigned_to = assigneeId === "0" ? null : Number(assigneeId);
      if (newStatus) payload.status = newStatus;
      await bulkUpdate.mutateAsync(payload);
      toast.success(`${selectedIds.size} tickets updated`);
      setAssigneeId("");
      setNewStatus("");
      onClear();
    } catch (err) {
      console.error("Bulk update failed", err);
      toast.error("Bulk update failed");
    }
  }

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 bg-card border rounded-xl shadow-xl px-5 py-3">
      <span className="text-sm font-medium">
        {selectedIds.size} selected
      </span>

      <div className="w-px h-5 bg-border" />

      <Select onValueChange={setAssigneeId} value={assigneeId}>
        <SelectTrigger className="w-44">
          <SelectValue placeholder="Assign to..." />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="0">Unassign</SelectItem>
          {users.map((u) => (
            <SelectItem key={u.id} value={String(u.id)}>
              {u.full_name || u.username}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select onValueChange={setNewStatus} value={newStatus}>
        <SelectTrigger className="w-40">
          <SelectValue placeholder="Status..." />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="open">Open</SelectItem>
          <SelectItem value="in_progress">In Progress</SelectItem>
          <SelectItem value="pending">Pending</SelectItem>
          <SelectItem value="resolved">Resolved</SelectItem>
          <SelectItem value="closed">Closed</SelectItem>
        </SelectContent>
      </Select>

      <Button size="sm" onClick={handleApply} disabled={bulkUpdate.isPending}>
        {bulkUpdate.isPending ? "Applying..." : "Apply"}
      </Button>

      <button
        onClick={onClear}
        className="ml-1 text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Clear selection"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
