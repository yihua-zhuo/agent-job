"use client";
import { useState } from "react";
import { useTickets } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-800",
  urgent: "bg-red-100 text-red-800",
  normal: "bg-blue-100 text-blue-800",
  low: "bg-gray-100 text-gray-600",
};
const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  pending: "bg-yellow-100 text-yellow-800",
  resolved: "bg-green-100 text-green-800",
  closed: "bg-gray-100 text-gray-500",
};

export default function TicketsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const { data, isLoading, isError } = useTickets(page, statusFilter);
  const items = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tickets</h1>
        <div className="flex gap-2">
            <SelectTrigger className="w-36">
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="open">Open</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="resolved">Resolved</SelectItem>
              <SelectItem value="closed">Closed</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-3 py-2.5 text-left font-semibold">ID</th>
              <th className="px-3 py-2.5 text-left font-semibold">Subject</th>
              <th className="px-3 py-2.5 text-left font-semibold">Status</th>
              <th className="px-3 py-2.5 text-left font-semibold">Priority</th>
              <th className="px-3 py-2.5 text-left font-semibold">Channel</th>
              <th className="px-3 py-2.5 text-left font-semibold">Created</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">Loading…</td></tr>}
            {isError && <tr><td colSpan={6} className="px-3 py-8 text-center text-destructive">Failed to load tickets</td></tr>}
            {!isLoading && items.length === 0 && <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">No tickets found</td></tr>}
            {items.map((t) => (
              <tr key={String(t.id)} className="border-b hover:bg-muted/50 transition-colors">
                <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">{t.id}</td>
                <td className="px-3 py-2.5 font-medium">{String(t.subject ?? "")}</td>
                <td className="px-3 py-2.5 text-muted-foreground">{String(t.channel ?? "—")}</td>
                <td className="px-3 py-2.5 text-muted-foreground">{t.created_at ? new Date(String(t.created_at)).toLocaleDateString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {info && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Showing {info.total === 0 ? 0 : ((page - 1) * 20) + 1}–{Math.min(page * 20, info.total as number)} of {info.total as number}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</Button>
            <Button variant="outline" size="sm" disabled={!info.has_next} onClick={() => setPage(page + 1)}>Next →</Button>
          </div>
        </div>
      )}
    </div>
  );
}
