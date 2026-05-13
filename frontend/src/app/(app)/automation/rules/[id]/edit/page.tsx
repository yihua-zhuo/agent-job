"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAutomationRule } from "@/lib/api/queries";
import { RuleBuilder } from "@/components/automation/rule-builder";
import type { RuleBuilderValues } from "@/components/automation/rule-builder";
import { useUpdateAutomationRule } from "@/lib/api/queries";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import type { ConditionRowValue } from "@/components/automation/condition-row";
import type { ActionRowValue } from "@/components/automation/action-row";

export default function EditRulePage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const ruleId = Number(params.id);
  const { data, isLoading, isError } = useAutomationRule(ruleId);
  const updateRule = useUpdateAutomationRule();
  const [submitError, setSubmitError] = useState("");

  const raw = data?.data;

  function toRuleBuilderValues(raw: Record<string, unknown>): Partial<RuleBuilderValues> {
    return {
      name: String(raw.name ?? ""),
      description: String(raw.description ?? ""),
      trigger_event: String(raw.trigger_event ?? ""),
      conditions: ((raw.conditions as Array<Record<string, string>>) ?? []).map(
        (c: Record<string, string>): ConditionRowValue => ({
          field: String(c.field ?? ""),
          operator: String(c.operator ?? "eq"),
          value: String(c.value ?? ""),
        })
      ),
      actions: ((raw.actions as Array<{ type: string; params: Record<string, string> }>) ?? []).map(
        (a): ActionRowValue => ({
          type: String(a.type ?? ""),
          params: (a.params ?? {}) as Record<string, string>,
        })
      ),
    };
  }

  async function handleSubmit(values: RuleBuilderValues) {
    setSubmitError("");
    try {
      await updateRule.mutateAsync({
        id: ruleId,
        data: {
          name: values.name,
          description: values.description,
          trigger_event: values.trigger_event,
          conditions: values.conditions,
          actions: values.actions.map((a) => ({ type: a.type, params: a.params })),
        },
      });
      router.push("/automation/rules");
    } catch {
      setSubmitError("Failed to update rule. Please try again.");
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Link href="/automation/rules" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-4 w-4" />
            Back to rules
          </Link>
        </div>
        <div className="h-8 bg-muted rounded w-64 animate-pulse" />
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <div className="h-4 bg-muted rounded w-32 animate-pulse" />
              <div className="h-10 bg-muted rounded animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (isError || !raw) {
    return (
      <div className="space-y-4">
        <Link href="/automation/rules" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Back to rules
        </Link>
        <p className="text-destructive">Failed to load rule. It may have been deleted.</p>
        <Button variant="outline" onClick={() => router.push("/automation/rules")}>
          Back to list
        </Button>
      </div>
    );
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
        <h1 className="text-2xl font-bold">Edit Automation Rule</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Update this automation rule. Changes apply immediately.
        </p>
      </div>
      {submitError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {submitError}
        </div>
      )}
      <RuleBuilder
        initialValues={toRuleBuilderValues(raw)}
        onSubmit={handleSubmit}
        onCancel={() => router.push("/automation/rules")}
        submitLabel="Update Rule"
        disabled={updateRule.isPending}
      />
    </div>
  );
}