"use client";
import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useAutomationLogs } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, History } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const STATUS_COLORS: Record<string, string> = {
  success: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  skipped: "bg-yellow-100 text-yellow-800",
};

function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface LogRow {
  id: number;
  rule_id: number;
  rule_name: string;
  trigger_event: string;
  status: string;
  executed_at: string;
  error_message?: string;
}

function PerRuleHistoryContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const ruleIdParam = searchParams.get("rule_id");
  const ruleId = ruleIdParam ? Number(ruleIdParam) : null;

  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useAutomationLogs(page, 20, ruleId ?? undefined);

  const rawItems = data?.data?.items ?? [];
  const info = data?.data;
  const logs: LogRow[] = rawItems.map((l) => ({
    id: Number(l.id),
    rule_id: Number(l.rule_id ?? 0),
    rule_name: String(l.rule_name ?? l.rule_id ?? ""),
    trigger_event: String(l.trigger_event ?? ""),
    status: String(l.status ?? ""),
    executed_at: String(l.executed_at ?? ""),
    error_message: l.error_message ? String(l.error_message) : undefined,
  }));

  const total = info?.total ?? 0;
  const pageSize = info?.page_size ?? 20;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-0">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-background pb-4 border-b border-border mb-0">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <h1 className="text-2xl font-bold">
            Execution History
            {ruleId && <span className="text-base font-normal text-muted-foreground ml-2">— Rule #{ruleId}</span>}
          </h1>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Link href="/automation/rules" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-4 w-4" />
            Back to rules
          </Link>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border mt-4 overflow-auto">
        {isLoading && (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-12 bg-muted rounded animate-pulse" />
            ))}
          </div>
        )}
        {isError && (
          <div className="px-3 py-10 text-center text-destructive">Failed to load execution history</div>
        )}
        {!isLoading && !isError && logs.length === 0 && (
          <div className="px-3 py-12 text-center">
            <p className="font-medium text-muted-foreground">No execution logs for this rule</p>
          </div>
        )}
        {!isLoading && !isError && logs.length > 0 && (
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-border">
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold">Event</th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold">Status</th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold">Executed</th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold">Error</th>
                <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold" />
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b hover:bg-muted/40 transition-colors">
                  <td className="px-3 py-3">
                    <span className="text-xs font-mono text-muted-foreground">{log.trigger_event}</span>
                  </td>
                  <td className="px-3 py-3">
                    <Badge colorClass={STATUS_COLORS[log.status] ?? "bg-gray-100 text-gray-600"}>
                      {log.status}
                    </Badge>
                  </td>
                  <td className="px-3 py-3">
                    <span className="text-xs text-muted-foreground">{formatDate(log.executed_at)}</span>
                  </td>
                  <td className="px-3 py-3">
                    <span className="text-xs text-red-600 truncate block max-w-[200px]" title={log.error_message}>
                      {log.error_message || "—"}
                    </span>
                  </td>
                  <td className="px-3 py-3" />
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {info && !isError && total > 0 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground py-3">
          <span>
            Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, total)} of {total}
          </span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              ← Prev
            </Button>
            <span className="flex items-center px-2 text-xs">{page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              Next →
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PerRuleHistoryPage() {
  return (
    <div className="space-y-6">
      <Suspense fallback={<div className="space-y-4">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-12 bg-muted rounded animate-pulse" />)}</div>}>
        <PerRuleHistoryContent />
      </Suspense>
    </div>
  );
}