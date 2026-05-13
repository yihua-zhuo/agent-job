"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  useAutomationRules,
  useDeleteAutomationRule,
  useToggleAutomationRule,
} from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  MoreHorizontal,
  Plus,
  History,
  Pencil,
  Trash2,
} from "lucide-react";

function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const TRIGGER_LABELS: Record<string, string> = {
  "ticket.created": "Ticket Created",
  "ticket.updated": "Ticket Updated",
  "ticket.assigned": "Ticket Assigned",
  "opportunity.stage_changed": "Opportunity Stage Changed",
  "opportunity.created": "Opportunity Created",
  "customer.created": "Customer Created",
  "customer.updated": "Customer Updated",
  "user.login": "User Login",
  "lead.created": "Lead Created",
};

function TriggerBadge({ trigger }: { trigger: string }) {
  const label = TRIGGER_LABELS[trigger] ?? trigger;
  return (
    <Badge colorClass="bg-blue-100 text-blue-800">
      {label}
    </Badge>
  );
}

interface RuleRow {
  id: number;
  name: string;
  trigger_event: string;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

function RuleRow({
  rule,
  onToggle,
  onEdit,
  onHistory,
  onDelete,
}: {
  rule: RuleRow;
  onToggle: (id: number) => void;
  onEdit: (id: number) => void;
  onHistory: (id: number) => void;
  onDelete: (id: number) => Promise<void>;
}) {
  return (
    <tr className="border-b hover:bg-muted/40 transition-colors group">
      <td className="px-3 py-3">
        <span className="font-medium truncate block max-w-[200px]" title={rule.name}>
          {rule.name || "—"}
        </span>
        <span className="text-xs text-muted-foreground font-mono">#{rule.id}</span>
      </td>
      <td className="px-3 py-3">
        <TriggerBadge trigger={rule.trigger_event} />
      </td>
      <td className="px-3 py-3">
        <button
          type="button"
          onClick={() => onToggle(rule.id)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer ${
            rule.enabled ? "bg-green-500" : "bg-gray-300"
          }`}
          aria-label={rule.enabled ? "Disable rule" : "Enable rule"}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
              rule.enabled ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </td>
      <td className="px-3 py-3">
        <span className="text-sm text-muted-foreground">
          {formatDate(rule.updated_at ?? rule.created_at)}
        </span>
      </td>
      <td className="px-3 py-3 w-10">
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
            <DropdownMenuItem onClick={() => onEdit(rule.id)}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onHistory(rule.id)}>
              <History className="h-4 w-4 mr-2" />
              View history
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive"
              onClick={() => {
                if (window.confirm(`Delete rule "${rule.name}"?`)) {
                  onDelete(rule.id);
                }
              }}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </td>
    </tr>
  );
}

export default function AutomationRulesPage() {
  const [page, setPage] = useState(1);
  const router = useRouter();
  const { data, isLoading, isError } = useAutomationRules(page);
  const deleteRule = useDeleteAutomationRule();
  const toggleRule = useToggleAutomationRule();

  const rawItems = data?.data?.items ?? [];
  const info = data?.data;
  const items: RuleRow[] = rawItems.map((r) => ({
    id: Number(r.id),
    name: String(r.name ?? ""),
    trigger_event: String(r.trigger_event ?? ""),
    enabled: Boolean(r.enabled),
    created_at: String(r.created_at ?? ""),
    updated_at: String(r.updated_at ?? ""),
  }));

  function handleToggle(id: number) {
    toggleRule.mutate(id);
  }
  function handleEdit(id: number) {
    router.push(`/automation/rules/${id}/edit`);
  }
  function handleHistory(id: number) {
    router.push(`/automation/rules/history?rule_id=${id}`);
  }
  async function handleDelete(id: number) {
    await deleteRule.mutateAsync(id);
  }

  const total = info?.total ?? 0;
  const pageSize = info?.page_size ?? 20;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-0">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-background pb-4 border-b border-border mb-0">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <h1 className="text-2xl font-bold">Automation Rules</h1>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push("/automation/rules/templates")}
            >
              Templates
            </Button>
            <Button
              size="sm"
              onClick={() => router.push("/automation/rules/new")}
            >
              <Plus className="h-4 w-4 mr-1" />
              Create Rule
            </Button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border mt-4 overflow-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="sticky top-[calc(2.5rem+72px)] z-10 bg-muted/60 backdrop-blur-sm">
            <tr className="border-b border-border">
              <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold">
                Name
              </th>
              <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold">
                Trigger
              </th>
              <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold">
                Status
              </th>
              <th className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold">
                Last Modified
              </th>
              <th className="px-3 py-2.5 w-10" />
            </tr>
          </thead>
          <tbody>
            {isLoading && Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="border-b">
                <td className="px-3 py-3"><div className="h-4 bg-muted rounded w-48 animate-pulse" /></td>
                <td className="px-3 py-3"><div className="h-5 bg-muted rounded w-28 animate-pulse" /></td>
                <td className="px-3 py-3"><div className="h-6 w-11 bg-muted rounded-full animate-pulse" /></td>
                <td className="px-3 py-3"><div className="h-4 bg-muted rounded w-20 animate-pulse" /></td>
                <td className="px-3 py-3" />
              </tr>
            ))}
            {isError && (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center text-destructive">
                  Failed to load rules
                </td>
              </tr>
            )}
            {!isLoading && !isError && items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-12 text-center">
                  <div className="flex flex-col items-center gap-2">
                    <p className="font-medium text-muted-foreground">No automation rules yet</p>
                    <Button
                      size="sm"
                      onClick={() => router.push("/automation/rules/new")}
                    >
                      Create your first rule
                    </Button>
                  </div>
                </td>
              </tr>
            )}
            {items.map((rule) => (
              <RuleRow
                key={rule.id}
                rule={rule}
                onToggle={handleToggle}
                onEdit={handleEdit}
                onHistory={handleHistory}
                onDelete={handleDelete}
              />
            ))}
          </tbody>
        </table>
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
            <span className="flex items-center px-2 text-xs">
              {page} / {totalPages}
            </span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              Next →
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}