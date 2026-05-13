"use client";

import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { SLATimer } from "./sla-timer";
import { Badge } from "@/components/ui/badge";

export interface KanbanTicketData {
  id: number;
  subject: string;
  status: string;
  priority: string;
  channel: string;
  assigned_to: number | null;
  created_at: string;
  response_deadline: string | null;
  sla_level: string;
}

interface KanbanBoardProps {
  tickets: KanbanTicketData[];
  groupBy?: "status" | "priority" | "assignee";
}

const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  pending: "bg-yellow-100 text-yellow-800",
  resolved: "bg-green-100 text-green-800",
  closed: "bg-gray-100 text-gray-500",
};

const PRIORITY_COLORS: Record<string, string> = {
  urgent: "bg-red-100 text-red-800",
  high: "bg-red-100 text-red-800",
  medium: "bg-blue-100 text-blue-800",
  low: "bg-gray-100 text-gray-600",
};

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  pending: "Pending",
  resolved: "Resolved",
  closed: "Closed",
};

const PRIORITY_LABELS: Record<string, string> = {
  urgent: "Urgent",
  high: "High",
  medium: "Medium",
  low: "Low",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge colorClass={STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600"}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
        PRIORITY_COLORS[priority] ?? "bg-gray-100 text-gray-600"
      )}
    >
      {PRIORITY_LABELS[priority] ?? priority}
    </span>
  );
}

function TicketCard({
  ticket,
  onClick,
}: {
  ticket: KanbanTicketData;
  onClick: (id: number) => void;
}) {
  return (
    <div
      className="rounded-lg border bg-card p-3 cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => onClick(ticket.id)}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="font-mono text-xs text-muted-foreground">#{ticket.id}</span>
        <StatusBadge status={ticket.status} />
      </div>
      <p className="text-sm font-medium line-clamp-2 mb-2">{ticket.subject}</p>
      <div className="flex items-center justify-between gap-2">
        <PriorityBadge priority={ticket.priority} />
        {ticket.response_deadline && (
          <SLATimer
            responseDeadline={ticket.response_deadline}
            createdAt={ticket.created_at}
            slaLevel={ticket.sla_level}
          />
        )}
      </div>
    </div>
  );
}

function StatusColumn({
  title,
  tickets,
  colorClass,
  onTicketClick,
}: {
  title: string;
  tickets: KanbanTicketData[];
  colorClass: string;
  onTicketClick: (id: number) => void;
}) {
  return (
    <div className="flex flex-col min-w-[220px] w-full">
      <div className="flex items-center gap-2 mb-3 px-1">
        <span className={cn("w-2 h-2 rounded-full", colorClass)} />
        <h3 className="font-semibold text-sm">{title}</h3>
        <span className="text-xs text-muted-foreground ml-auto">{tickets.length}</span>
      </div>
      <div className="flex flex-col gap-2 overflow-y-auto max-h-[calc(100vh-14rem)]">
        {tickets.map((t) => (
          <TicketCard key={t.id} ticket={t} onClick={onTicketClick} />
        ))}
        {tickets.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">No tickets</p>
        )}
      </div>
    </div>
  );
}

export function KanbanBoard({ tickets, groupBy = "status" }: KanbanBoardProps) {
  const router = useRouter();

  function handleTicketClick(id: number) {
    router.push(`/tickets/${id}`);
  }

  if (groupBy === "status") {
    const groups: Record<string, { label: string; color: string }> = {
      open: { label: "Open", color: "bg-blue-500" },
      in_progress: { label: "In Progress", color: "bg-yellow-500" },
      pending: { label: "Pending", color: "bg-yellow-400" },
      resolved: { label: "Resolved", color: "bg-green-500" },
      closed: { label: "Closed", color: "bg-gray-400" },
    };
    const cols = Object.entries(groups).map(([key, { label, color }]) => ({
      key,
      label,
      color,
      tickets: tickets.filter((t) => t.status === key),
    }));
    return (
      <div className="flex gap-4 overflow-x-auto pb-4">
        {cols.map(({ key, label, color, tickets: colTickets }) => (
          <StatusColumn
            key={key}
            title={label}
            colorClass={color}
            tickets={colTickets}
            onTicketClick={handleTicketClick}
          />
        ))}
      </div>
    );
  }

  if (groupBy === "priority") {
    const groups: Record<string, string> = {
      urgent: "Urgent",
      high: "High",
      medium: "Medium",
      low: "Low",
    };
    const cols = Object.entries(groups).map(([key, label]) => ({
      key,
      label,
      color: key === "urgent" || key === "high" ? "bg-red-500" : key === "medium" ? "bg-blue-500" : "bg-gray-400",
      tickets: tickets.filter((t) => t.priority === key),
    }));
    return (
      <div className="flex gap-4 overflow-x-auto pb-4">
        {cols.map(({ key, label, color, tickets: colTickets }) => (
          <StatusColumn
            key={key}
            title={label}
            colorClass={color}
            tickets={colTickets}
            onTicketClick={handleTicketClick}
          />
        ))}
      </div>
    );
  }

  // groupBy === "assignee"
  const assigned = tickets.filter((t) => t.assigned_to != null);
  const unassigned = tickets.filter((t) => t.assigned_to == null);
  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      <StatusColumn
        title="Unassigned"
        colorClass="bg-gray-400"
        tickets={unassigned}
        onTicketClick={handleTicketClick}
      />
      {Array.from(new Set(assigned.map((t) => t.assigned_to))).map((aid) => (
        <StatusColumn
          key={aid}
          title={`Agent ${aid}`}
          colorClass="bg-purple-500"
          tickets={assigned.filter((t) => t.assigned_to === aid)}
          onTicketClick={handleTicketClick}
        />
      ))}
    </div>
  );
}