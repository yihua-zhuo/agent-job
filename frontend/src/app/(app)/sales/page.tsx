"use client";
import { useState } from "react";
import { useOpportunities } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LayoutGrid, List, RefreshCw } from "lucide-react";

const STAGE_COLORS: Record<string, string> = {
  lead: "bg-blue-100 text-blue-800",
  qualified: "bg-cyan-100 text-cyan-800",
  proposal: "bg-purple-100 text-purple-800",
  negotiation: "bg-yellow-100 text-yellow-800",
  closed_won: "bg-green-100 text-green-800",
  closed_lost: "bg-red-100 text-red-800",
};

const KANBAN_COLUMNS = ["lead", "qualified", "proposal", "negotiation", "closed_won", "closed_lost"];

function fmtAmt(v: unknown) {
  if (!v && v !== 0) return "—";
  return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function ListView({ items }: { items: Record<string, unknown>[] }) {
  return (
    <div className="rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
            <th className="px-3 py-2.5 text-left font-semibold">Name</th>
            <th className="px-3 py-2.5 text-left font-semibold">Stage</th>
            <th className="px-3 py-2.5 text-left font-semibold text-right">Amount</th>
            <th className="px-3 py-2.5 text-left font-semibold">Probability</th>
            <th className="px-3 py-2.5 text-left font-semibold">Customer</th>
            <th className="px-3 py-2.5 text-left font-semibold">Close Date</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">No opportunities found</td></tr>
          )}
          {items.map((o) => (
            <tr key={String(o.id)} className="border-b hover:bg-muted/50 transition-colors">
              <td className="px-3 py-2.5 font-medium">{String(o.name ?? "")}</td>
              <td className="px-3 py-2.5"><Badge colorClass={STAGE_COLORS[String(o.stage)] ?? "bg-gray-100 text-gray-600"}>{String(o.stage ?? "—")}</Badge></td>
              <td className="px-3 py-2.5 text-right font-semibold text-green-700">{fmtAmt(o.amount)}</td>
              <td className="px-3 py-2.5 text-muted-foreground">{o.probability != null ? `${o.probability}%` : "—"}</td>
              <td className="px-3 py-2.5 font-mono text-muted-foreground text-xs">{String(o.customer_id ?? "—")}</td>
              <td className="px-3 py-2.5 text-muted-foreground">{o.expected_close_date ? new Date(String(o.expected_close_date)).toLocaleDateString() : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function KanbanColumn({ stage, items }: { stage: string; items: Record<string, unknown>[] }) {
  return (
    <div className="flex flex-col min-w-[200px] flex-1">
      <div className="mb-2 flex items-center gap-2">
        <Badge colorClass={STAGE_COLORS[stage] ?? "bg-gray-100 text-gray-600"}>
          {stage.replace(/_/g, " ")}
        </Badge>
        <span className="text-xs text-muted-foreground font-medium">{items.length}</span>
      </div>
      <div className="space-y-2">
        {items.map((o) => (
          <div
            key={String(o.id)}
            className="rounded-md border bg-background p-3 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
          >
            <div className="text-sm font-medium mb-1">{String(o.name ?? "")}</div>
            <div className="text-xs text-muted-foreground mb-2">{String(o.customer_id ?? "—")}</div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-green-700">{fmtAmt(o.amount)}</span>
              <span className="text-xs text-muted-foreground">{o.probability != null ? `${o.probability}%` : "—"}</span>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <div className="rounded-md border border-dashed p-4 text-center text-xs text-muted-foreground">
            No deals
          </div>
        )}
      </div>
    </div>
  );
}

export default function SalesPage() {
  const [page, setPage] = useState(1);
  const [view, setView] = useState<"list" | "kanban">("list");
  const { data, isLoading, isError, refetch, isFetching } = useOpportunities(page);
  const items = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;

  const byStage = KANBAN_COLUMNS.reduce<Record<string, Record<string, unknown>[]>>((acc, stage) => {
    acc[stage] = items.filter((o) => o.stage === stage);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Opportunities</h1>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <div className="flex border rounded-md overflow-hidden">
            <Button
              variant={view === "list" ? "secondary" : "ghost"}
              size="sm"
              className="rounded-none"
              onClick={() => setView("list")}
              aria-label="List view"
            >
              <List className="h-4 w-4" />
            </Button>
            <Button
              variant={view === "kanban" ? "secondary" : "ghost"}
              size="sm"
              className="rounded-none"
              onClick={() => setView("kanban")}
              aria-label="Kanban view"
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {isLoading && <div className="py-8 text-center text-muted-foreground">Loading…</div>}
      {isError && <div className="py-8 text-center text-destructive">Failed to load opportunities</div>}

      {!isLoading && !isError && view === "kanban" && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {KANBAN_COLUMNS.map((stage) => (
            <KanbanColumn key={stage} stage={stage} items={byStage[stage] ?? []} />
          ))}
        </div>
      )}

      {!isLoading && !isError && view === "list" && <ListView items={items} />}

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
