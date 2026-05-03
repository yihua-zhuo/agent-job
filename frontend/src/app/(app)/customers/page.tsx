"use client";
import { useState } from "react";
import { useCustomers, useSearchCustomers } from "@/lib/api/queries";

const STATUS_COLORS: Record<string, string> = {
  lead: "bg-blue-100 text-blue-800",
  customer: "bg-green-100 text-green-800",
  partner: "bg-purple-100 text-purple-800",
  prospect: "bg-yellow-100 text-yellow-800",
  active: "bg-green-100 text-green-800",
  inactive: "bg-gray-100 text-gray-500",
  blocked: "bg-red-100 text-red-800",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status ?? "—"}
    </span>
  );
}

function CustomerRow({ c }: { c: Record<string, unknown> }) {
  return (
    <tr className="border-b hover:bg-muted/50 cursor-pointer transition-colors">
      <td className="px-3 py-2.5 font-medium">{String(c.name ?? "")}</td>
      <td className="px-3 py-2.5 text-sm text-muted-foreground">{String(c.email ?? "—")}</td>
      <td className="px-3 py-2.5 text-sm font-mono text-muted-foreground">{String(c.phone ?? "—")}</td>
      <td className="px-3 py-2.5"><StatusBadge status={String(c.status ?? "")} /></td>
      <td className="px-3 py-2.5 text-sm text-muted-foreground">{String(c.company ?? "—")}</td>
      <td className="px-3 py-2.5 text-sm text-muted-foreground">{c.created_at ? new Date(String(c.created_at)).toLocaleDateString() : "—"}</td>
    </tr>
  );
}

function useCustomersData(page: number, keyword: string) {
  const search = useSearchCustomers(keyword);
  const list = useCustomers(page);
  if (keyword) return search;
  return list;
}

export default function CustomersPage() {
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const { data, isLoading, isError } = useCustomersData(
    keyword ? 1 : page,
    keyword
  );
  const items = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Customers</h1>
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Search customers…"
          className="flex h-9 w-64 rounded-md border border-input bg-background px-3 py-1 text-sm"
        />
      </div>

      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-3 py-2.5 text-left font-semibold">Name</th>
              <th className="px-3 py-2.5 text-left font-semibold">Email</th>
              <th className="px-3 py-2.5 text-left font-semibold">Phone</th>
              <th className="px-3 py-2.5 text-left font-semibold">Status</th>
              <th className="px-3 py-2.5 text-left font-semibold">Company</th>
              <th className="px-3 py-2.5 text-left font-semibold">Created</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">Loading…</td></tr>
            )}
            {isError && (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-destructive">Failed to load customers</td></tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">No customers found</td></tr>
            )}
            {items.map((c) => <CustomerRow key={String(c.id)} c={c} />)}
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
