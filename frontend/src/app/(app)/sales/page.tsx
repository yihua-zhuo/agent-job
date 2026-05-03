"use client";
import { useState } from "react";
import { useOpportunities, useCreateOpportunity } from "@/lib/api/queries";
import { useMutation } from "@tanstack/react-query";

const STAGE_COLORS: Record<string, string> = {
  lead: "bg-blue-100 text-blue-800",
  qualified: "bg-cyan-100 text-cyan-800",
  proposal: "bg-purple-100 text-purple-800",
  negotiation: "bg-yellow-100 text-yellow-800",
  closed_won: "bg-green-100 text-green-800",
  closed_lost: "bg-red-100 text-red-800",
};

function StageBadge({ stage }: { stage: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${STAGE_COLORS[stage] ?? "bg-gray-100 text-gray-600"}`}>
      {stage ?? "—"}
    </span>
  );
}

function fmtAmt(v: unknown) {
  if (!v && v !== 0) return "—";
  return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export default function SalesPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError } = useOpportunities(page);
  const items = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Opportunities</h1>
      </div>

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
            {isLoading && <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">Loading…</td></tr>}
            {isError && <tr><td colSpan={6} className="px-3 py-8 text-center text-destructive">Failed to load opportunities</td></tr>}
            {!isLoading && items.length === 0 && <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">No opportunities found</td></tr>}
            {items.map((o) => (
              <tr key={String(o.id)} className="border-b hover:bg-muted/50 transition-colors">
                <td className="px-3 py-2.5 font-medium">{String(o.name ?? "")}</td>
                <td className="px-3 py-2.5"><StageBadge stage={String(o.stage ?? "")} /></td>
                <td className="px-3 py-2.5 text-right font-semibold text-green-700">{fmtAmt(o.amount)}</td>
                <td className="px-3 py-2.5 text-muted-foreground">{o.probability != null ? `${o.probability}%` : "—"}</td>
                <td className="px-3 py-2.5 font-mono text-muted-foreground text-xs">{o.customer_id ?? "—"}</td>
                <td className="px-3 py-2.5 text-muted-foreground">{o.expected_close_date ? new Date(String(o.expected_close_date)).toLocaleDateString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {info && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Showing {((page - 1) * 20) + 1}–{Math.min(page * 20, info.total as number)} of {info.total as number}</span>
          <div className="flex gap-1">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-40">← Prev</button>
            <button disabled={!info.has_next} onClick={() => setPage(page + 1)} className="rounded border px-2 py-1 hover:bg-muted disabled:opacity-40">Next →</button>
          </div>
        </div>
      )}
    </div>
  );
}
