"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useTickets, useDeleteTicket, useSlaBreaches, useUsers } from "@/lib/api/queries";
import { KanbanBoard, type KanbanTicketData } from "@/components/tickets/kanban-board";
import { SLATimer } from "@/components/tickets/sla-timer";
import { BulkActionsBar } from "@/components/tickets/bulk-actions-bar";
import { TicketFormDialog } from "@/components/tickets/ticket-form-dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, X, ChevronUp, ChevronDown, MoreHorizontal, LayoutGrid, List, Plus } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-800",
  urgent: "bg-red-100 text-red-800",
  medium: "bg-blue-100 text-blue-800",
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

type SortKey = "id" | "subject" | "status" | "priority" | "channel" | "created_at" | "response_deadline";
type SortDir = "asc" | "desc";
type ViewMode = "table" | "kanban";

function SortIconStatic({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey | null; sortDir: SortDir }) {
  if (sortKey !== col) {
    return <ChevronUp className="h-3 w-3 opacity-0 group-hover:opacity-40 transition-opacity inline ml-1" />;
  }
  return sortDir === "asc"
    ? <ChevronUp className="h-3 w-3 opacity-100 inline ml-1 text-primary" />
    : <ChevronDown className="h-3 w-3 opacity-100 inline ml-1 text-primary" />;
}

interface TicketRowData {
  id: number;
  subject: string;
  status: string;
  priority: string;
  channel: string;
  created_at: string;
  assigned_to: number | null;
  response_deadline: string | null;
  sla_level: string;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "numeric", day: "numeric", year: "numeric" });
}

function TicketRow({
  t,
  selected,
  onToggle,
  onDelete,
  onView,
}: {
  t: TicketRowData;
  selected: boolean;
  onToggle: (id: number) => void;
  onDelete: (id: number) => Promise<void>;
  onView: (id: number) => void;
}) {
  return (
    <tr
      className={cn(
        "border-b hover:bg-muted/40 transition-colors group",
        selected && "bg-primary/5"
      )}
    >
      <td className="px-3 py-2.5 w-10">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(t.id)}
          className="accent-primary h-4 w-4 cursor-pointer"
          onClick={(e) => e.stopPropagation()}
        />
      </td>
      <td className="px-3 py-2.5">
        <span
          className="font-mono text-xs text-muted-foreground truncate block max-w-[60px]"
          title={String(t.id)}
        >
          #{t.id}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <span
          className="font-medium truncate block max-w-[200px]"
          title={t.subject}
        >
          {t.subject || "—"}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <Badge colorClass={STATUS_COLORS[t.status] ?? "bg-gray-100 text-gray-600"}>
          {t.status || "—"}
        </Badge>
      </td>
      <td className="px-3 py-2.5">
        <span className={cn(
          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
          PRIORITY_COLORS[t.priority] ?? "bg-gray-100 text-gray-600"
        )}>
          {t.priority || "—"}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <span className="text-sm text-muted-foreground">{t.channel || "—"}</span>
      </td>
      <td className="px-3 py-2.5">
        <span className="text-sm text-muted-foreground">{t.assigned_to ? `Agent ${t.assigned_to}` : "—"}</span>
      </td>
      <td className="px-3 py-2.5">
        {t.response_deadline ? (
          <SLATimer
            responseDeadline={t.response_deadline}
            createdAt={t.created_at}
            slaLevel={t.sla_level}
          />
        ) : "—"}
      </td>
      <td className="px-3 py-2.5">
        <span className="text-sm text-muted-foreground">{formatDate(t.created_at)}</span>
      </td>
      <td className="px-3 py-2.5 w-10" onClick={(e) => e.stopPropagation()}>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100"
              aria-label="Row actions"
            >
              <MoreHorizontal className="h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onView(t.id)}>View details</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive" onClick={() => onDelete(t.id)}>Delete</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </td>
    </tr>
  );
}

export default function TicketsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState("all");
  const [assigneeFilter, setAssigneeFilter] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const deleteTicket = useDeleteTicket();
  const router = useRouter();

  const { data: usersData } = useUsers(1, 100);
  const users = (usersData?.data?.items ?? []) as Array<{ id: number; username: string; full_name?: string }>;

  const { data: slaBreachesData } = useSlaBreaches();
  const breachedTicketIds = new Set(
    ((slaBreachesData?.data ?? []) as Array<{ id: number }>).map((t) => t.id)
  );

  const { data, isLoading, isError } = useTickets(
    page,
    20,
    statusFilter === "all" ? "" : statusFilter
  );

  const rawItems = data?.data?.items ?? [];
  const info = data?.data;

  const items: TicketRowData[] = rawItems.map((t: Record<string, unknown>) => ({
    id: Number(t.id),
    subject: String(t.subject ?? ""),
    status: String(t.status ?? ""),
    priority: String(t.priority ?? ""),
    channel: String(t.channel ?? ""),
    created_at: String(t.created_at ?? ""),
    assigned_to: t.assigned_to != null ? Number(t.assigned_to) : null,
    response_deadline: t.response_deadline ? String(t.response_deadline) : null,
    sla_level: String(t.sla_level ?? "standard"),
  }));

  // Client-side filters
  const filtered = items.filter((t) => {
    if (debouncedKeyword) {
      const kw = debouncedKeyword.toLowerCase();
      if (!String(t.subject).toLowerCase().includes(kw) && !String(t.id).includes(kw)) return false;
    }
    if (priorityFilter !== "all" && t.priority !== priorityFilter) return false;
    if (channelFilter !== "all" && t.channel !== channelFilter) return false;
    if (assigneeFilter !== "all") {
      const assigneeId = Number(assigneeFilter);
      if (assigneeId === 0 && t.assigned_to != null) return false;
      if (assigneeId !== 0 && t.assigned_to !== assigneeId) return false;
    }
    return true;
  });

  // Client-side sort
  const sorted = [...filtered].sort((a, b) => {
    if (!sortKey) return 0;
    let av: string | number = a[sortKey] ?? "";
    let bv: string | number = b[sortKey] ?? "";
    if (sortKey === "response_deadline") {
      av = a.response_deadline ? new Date(a.response_deadline).getTime() : Infinity;
      bv = b.response_deadline ? new Date(b.response_deadline).getTime() : Infinity;
    }
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortDir === "asc" ? cmp : -cmp;
  });

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
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

  async function handleDeleteTicket(id: number) {
    if (window.confirm(`Delete ticket #${id}?`)) {
      await deleteTicket.mutateAsync(id);
      toast.success("Ticket deleted");
    }
  }

  function handleViewTicket(id: number) {
    if (breachedTicketIds.has(id)) {
      toast.error(`SLA breached on ticket #${id}`);
    }
    router.push(`/tickets/${id}`);
  }

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setKeyword(val);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedKeyword(val);
      setPage(1);
    }, 300);
  }, []);

  const clearSearch = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setKeyword("");
    setDebouncedKeyword("");
    setPage(1);
  }, []);

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  // SLA breach toasts on mount
  useEffect(() => {
    if (breachedTicketIds.size > 0 && !isLoading) {
      const ids = Array.from(breachedTicketIds).slice(0, 3);
      ids.forEach((id, i) => {
        setTimeout(() => toast.error(`SLA breached on ticket #${id}`), i * 500);
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading]);

  const totalShown = info?.total ?? 0;
  const startShown = info?.total === 0 ? 0 : ((page - 1) * (info?.page_size ?? 20)) + 1;
  const endShown = Math.min(page * (info?.page_size ?? 20), info?.total ?? 0);

  return (
    <div className="space-y-0">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-background pb-4 border-b border-border mb-0">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <h1 className="text-2xl font-bold">Tickets</h1>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => setCreateDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Create Ticket
            </Button>
            <div className="flex border rounded-md overflow-hidden">
              <button
                className={cn(
                  "px-3 py-1.5 text-xs font-medium transition-colors flex items-center gap-1",
                  viewMode === "table" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
                )}
                onClick={() => setViewMode("table")}
                aria-label="Table view"
              >
                <List className="h-3.5 w-3.5" />
                Table
              </button>
              <button
                className={cn(
                  "px-3 py-1.5 text-xs font-medium transition-colors flex items-center gap-1",
                  viewMode === "kanban" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
                )}
                onClick={() => setViewMode("kanban")}
                aria-label="Kanban view"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                Board
              </button>
            </div>
          </div>
        </div>

        <div className="flex gap-2 flex-wrap">
          <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="open">Open</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="resolved">Resolved</SelectItem>
              <SelectItem value="closed">Closed</SelectItem>
            </SelectContent>
          </Select>

          <Select value={priorityFilter} onValueChange={(v) => { setPriorityFilter(v); setPage(1); }}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="All Priorities" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Priorities</SelectItem>
              <SelectItem value="urgent">Urgent</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>

          <Select value={channelFilter} onValueChange={(v) => { setChannelFilter(v); setPage(1); }}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="All Channels" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Channels</SelectItem>
              <SelectItem value="email">Email</SelectItem>
              <SelectItem value="chat">Chat</SelectItem>
              <SelectItem value="whatsapp">WhatsApp</SelectItem>
              <SelectItem value="phone">Phone</SelectItem>
            </SelectContent>
          </Select>

          <Select value={assigneeFilter} onValueChange={(v) => { setAssigneeFilter(v); setPage(1); }}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="All Assignees" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Assignees</SelectItem>
              <SelectItem value="0">Unassigned</SelectItem>
              {users.map((u) => (
                <SelectItem key={u.id} value={String(u.id)}>
                  {u.full_name || u.username}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="relative flex-1 min-w-48 max-w-sm">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              type="text"
              value={keyword}
              onChange={handleChange}
              placeholder="Search tickets…"
              className="pl-8 pr-8 rounded-lg border-[1px] shadow-sm focus:ring-2 focus:ring-primary focus:ring-offset-1"
            />
            {keyword && (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Kanban view */}
      {viewMode === "kanban" && (
        <div className="mt-4">
          <KanbanBoard
            tickets={sorted}
            groupBy="status"
          />
        </div>
      )}

      {/* Table view */}
      {viewMode === "table" && (
        <>
          <div className="rounded-md border mt-4 overflow-auto">
            <table className="w-full text-sm min-w-[640px]">
              <thead className="sticky top-[calc(2.5rem+72px)] z-10 bg-muted/60 backdrop-blur-sm">
                <tr className="border-b border-border">
                  <th className="px-3 py-2.5 w-10">
                    <input
                      type="checkbox"
                      className="accent-primary h-4 w-4 cursor-pointer"
                      onChange={(e) => {
                        if (e.target.checked) setSelectedIds(new Set(sorted.map((t) => t.id)));
                        else setSelectedIds(new Set());
                      }}
                      checked={sorted.length > 0 && sorted.every((t) => selectedIds.has(t.id))}
                    />
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                    onClick={() => handleSort("id")}
                  >
                    ID<SortIconStatic col="id" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                    onClick={() => handleSort("subject")}
                  >
                    Subject<SortIconStatic col="subject" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                    onClick={() => handleSort("status")}
                  >
                    Status<SortIconStatic col="status" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                    onClick={() => handleSort("priority")}
                  >
                    Priority<SortIconStatic col="priority" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                    onClick={() => handleSort("channel")}
                  >
                    Channel<SortIconStatic col="channel" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                    onClick={() => handleSort("assignee")}
                  >
                    Assignee
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                    onClick={() => handleSort("response_deadline")}
                  >
                    SLA<SortIconStatic col="response_deadline" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th
                    className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                    onClick={() => handleSort("created_at")}
                  >
                    Created<SortIconStatic col="created_at" sortKey={sortKey} sortDir={sortDir} />
                  </th>
                  <th className="px-3 py-2.5 w-10" />
                </tr>
              </thead>
              <tbody>
                {isLoading && Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="border-b">
                    <td className="px-3 py-2.5"><div className="h-4 w-4 bg-muted rounded animate-pulse" /></td>
                    <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-10 animate-pulse" /></td>
                    <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-48 animate-pulse" /></td>
                    <td className="px-3 py-2.5"><div className="h-5 bg-muted rounded w-16 animate-pulse" /></td>
                    <td className="px-3 py-2.5"><div className="h-5 bg-muted rounded w-14 animate-pulse" /></td>
                    <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-20 animate-pulse" /></td>
                    <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-20 animate-pulse" /></td>
                    <td className="px-3 py-2.5"><div className="h-5 bg-muted rounded w-16 animate-pulse" /></td>
                    <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-20 animate-pulse" /></td>
                    <td className="px-3 py-2.5" />
                  </tr>
                ))}
                {isError && (
                  <tr>
                    <td colSpan={10} className="px-3 py-10 text-center text-destructive">
                      Failed to load tickets
                    </td>
                  </tr>
                )}
                {!isLoading && !isError && sorted.length === 0 && (
                  <tr>
                    <td colSpan={10} className="px-3 py-12 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <Search className="h-8 w-8 text-muted-foreground/50" />
                        <p className="font-medium text-muted-foreground">No tickets found</p>
                        {keyword && (
                          <p className="text-sm text-muted-foreground/70">
                            No results for &ldquo;{keyword}&rdquo;
                          </p>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
                {sorted.map((t) => (
                  <TicketRow
                    key={t.id}
                    t={t}
                    selected={selectedIds.has(t.id)}
                    onToggle={toggleSelect}
                    onDelete={handleDeleteTicket}
                    onView={handleViewTicket}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {info && !isError && (
            <div className="flex items-center justify-between text-xs text-muted-foreground py-3">
              <span>
                {selectedIds.size > 0
                  ? `${selectedIds.size} selected`
                  : `Showing ${startShown}–${endShown} of ${totalShown}`}
              </span>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</Button>
                <Button variant="outline" size="sm" disabled={!info.has_next} onClick={() => setPage(page + 1)}>Next →</Button>
              </div>
            </div>
          )}
        </>
      )}

      <BulkActionsBar selectedIds={selectedIds} onClear={() => setSelectedIds(new Set())} />
      <TicketFormDialog open={createDialogOpen} onOpenChange={setCreateDialogOpen} />
    </div>
  );
}