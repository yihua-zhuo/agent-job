"use client";
import { useRouter } from "next/navigation";
import { useAutomationRule } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Pencil, History } from "lucide-react";

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

export default function RuleDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const ruleId = Number(params.id);
  const { data, isLoading, isError } = useAutomationRule(ruleId);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Link href="/automation/rules" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Back to rules
        </Link>
        <div className="h-8 bg-muted rounded w-64 animate-pulse" />
      </div>
    );
  }

  if (isError || !data?.data) {
    return (
      <div className="space-y-4">
        <Link href="/automation/rules" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Back to rules
        </Link>
        <p className="text-destructive">Failed to load rule.</p>
        <Button variant="outline" onClick={() => router.push("/automation/rules")}>
          Back to list
        </Button>
      </div>
    );
  }

  const rule = data.data as Record<string, unknown>;
  const trigger = String(rule.trigger_event ?? "");
  const triggerLabel = TRIGGER_LABELS[trigger] ?? trigger;
  const conditions = (rule.conditions as Array<{ field: string; operator: string; value: string }>) ?? [];
  const actions = (rule.actions as Array<{ type: string; params: Record<string, string> }>) ?? [];

  return (
    <div className="space-y-6">
      <Link href="/automation/rules" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="h-4 w-4" />
        Back to rules
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{String(rule.name ?? "—")}</h1>
          {rule.description && (
            <p className="text-sm text-muted-foreground mt-1">{String(rule.description)}</p>
          )}
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/automation/rules/history/${ruleId}`)}
          >
            <History className="h-4 w-4 mr-1" />
            View history
          </Button>
          <Button
            size="sm"
            onClick={() => router.push(`/automation/rules/${ruleId}/edit`)}
          >
            <Pencil className="h-4 w-4 mr-1" />
            Edit
          </Button>
        </div>
      </div>

      {/* Status & trigger metadata */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Trigger:</span>
          <Badge colorClass="bg-blue-100 text-blue-800">{triggerLabel}</Badge>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Status:</span>
          <Badge colorClass={rule.enabled ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-500"}>
            {rule.enabled ? "Active" : "Disabled"}
          </Badge>
        </div>
      </div>

      {/* Conditions */}
      <div className="space-y-3 rounded-md border p-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          Conditions
        </h2>
        {conditions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No conditions — runs on every trigger event.</p>
        ) : (
          <div className="space-y-2">
            {conditions.map((cond, i) => (
              <div key={i} className="flex gap-3 text-sm">
                <span className="font-mono text-muted-foreground">{cond.field}</span>
                <span className="text-muted-foreground">{cond.operator}</span>
                <span className="font-medium">{cond.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="space-y-3 rounded-md border p-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          Actions
        </h2>
        {actions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No actions configured.</p>
        ) : (
          <div className="space-y-2">
            {actions.map((action, i) => (
              <div key={i} className="rounded-md border bg-muted/20 p-3">
                <span className="font-medium text-sm">{action.type}</span>
                {Object.keys(action.params ?? {}).length > 0 && (
                  <div className="mt-1 text-xs text-muted-foreground font-mono">
                    {Object.entries(action.params).map(([k, v]) => `${k}: ${v}`).join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}