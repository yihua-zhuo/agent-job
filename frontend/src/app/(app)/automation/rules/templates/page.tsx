"use client";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Zap } from "lucide-react";
import Link from "next/link";
import { useCreateAutomationRule } from "@/lib/api/queries";

const TEMPLATES = [
  {
    name: "High-Value Ticket Alert",
    description: "Notify the team whenever a high-priority ticket is created.",
    trigger: "ticket.created",
    conditions: [{ field: { key: "priority", label: "Priority" }, operator: "eq", value: "high" }],
    actions: [
      { type: "notification.send", params: { message: "High-priority ticket created — please review immediately." } },
    ],
  },
  {
    name: "Win-Back Campaign",
    description: "Create a task and send an email when a customer's churn risk becomes high.",
    trigger: "customer.updated",
    conditions: [{ field: { key: "churn_risk", label: "Churn Risk" }, operator: "eq", value: "high" }],
    actions: [
      { type: "task.create", params: { title: "Reach out to at-risk customer" } },
      { type: "email.send", params: { subject: "We'd love your feedback" } },
    ],
  },
  {
    name: "New Opportunity Notification",
    description: "Alert the sales team immediately when a new opportunity is created.",
    trigger: "opportunity.created",
    conditions: [],
    actions: [
      { type: "notification.send", params: { message: "New opportunity created — check the pipeline." } },
    ],
  },
  {
    name: "Ticket SLA Breach Warning",
    description: "Send a notification when a ticket's SLA is about to be breached.",
    trigger: "ticket.updated",
    conditions: [{ field: { key: "sla_breached", label: "SLA Breached" }, operator: "eq", value: "true" }],
    actions: [
      { type: "notification.send", params: { message: "Ticket SLA has been breached — immediate attention required." } },
    ],
  },
  {
    name: "Lead Follow-Up",
    description: "Automatically create a follow-up task when a new lead is created.",
    trigger: "lead.created",
    conditions: [],
    actions: [
      { type: "task.create", params: { title: "Follow up with new lead" } },
    ],
  },
];

const TRIGGER_LABELS: Record<string, string> = {
  "ticket.created": "Ticket Created",
  "ticket.updated": "Ticket Updated",
  "customer.updated": "Customer Updated",
  "opportunity.created": "Opportunity Created",
  "lead.created": "Lead Created",
};

interface TemplateCardProps {
  template: (typeof TEMPLATES)[number];
  onActivate: (template: (typeof TEMPLATES)[number]) => void;
  activating: boolean;
  disabled: boolean;
}

function TemplateCard({ template, onActivate, activating, disabled }: TemplateCardProps) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">{template.name}</CardTitle>
          </div>
          <Badge variant="blue">
            {TRIGGER_LABELS[template.trigger] ?? template.trigger}
          </Badge>
        </div>
        <CardDescription className="mt-1">{template.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 flex-1">
        <div className="space-y-1">
          {template.conditions.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Conditions</p>
              <div className="mt-1 space-y-0.5">
                {template.conditions.map((c, i) => (
                  <p key={i} className="text-xs text-muted-foreground font-mono">
                    {typeof c.field === "object" ? c.field.key : c.field} {c.operator} {c.value}
                  </p>
                ))}
              </div>
            </div>
          )}
          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Actions</p>
            <div className="mt-1 space-y-0.5">
              {template.actions.map((a, i) => (
                <p key={i} className="text-xs text-muted-foreground font-mono">
                  {a.type}
                </p>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-auto">
          <Button
            size="sm"
            className="w-full"
            onClick={() => onActivate(template)}
            disabled={disabled}
          >
            {activating ? "Activating…" : "Activate"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function TemplatesPage() {
  const router = useRouter();
  const createRule = useCreateAutomationRule();
  const [activatingTemplate, setActivatingTemplate] = useState<string | null>(null);

  async function handleActivate(template: (typeof TEMPLATES)[number]) {
    if (activatingTemplate !== null) return;
    setActivatingTemplate(template.name);
    try {
      await createRule.mutateAsync({
        name: template.name,
        description: template.description,
        trigger_event: template.trigger,
        conditions: template.conditions,
        actions: template.actions,
        enabled: true,
      });
      router.push("/automation/rules");
    } finally {
      setActivatingTemplate(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/automation/rules" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Back to rules
        </Link>
      </div>
      <div>
        <h1 className="text-2xl font-bold">Rule Templates</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Start with a pre-built template and customize it to your needs.
        </p>
      </div>

      {createRule.isError && (
        <div
          role="alert"
          aria-live="polite"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {String(createRule.error?.message ?? "Failed to activate template. Please try again.")}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {TEMPLATES.map((template) => (
          <TemplateCard
            key={template.name}
            template={template}
            onActivate={handleActivate}
            activating={activatingTemplate === template.name}
            disabled={activatingTemplate !== null}
          />
        ))}
      </div>
    </div>
  );
}