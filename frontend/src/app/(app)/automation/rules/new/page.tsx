"use client";
import { useRouter } from "next/navigation";
import { RuleBuilder } from "@/components/automation/rule-builder";
import type { RuleBuilderValues } from "@/components/automation/rule-builder";
import { useCreateAutomationRule } from "@/lib/api/queries";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function NewRulePage() {
  const router = useRouter();
  const createRule = useCreateAutomationRule();

  async function handleSubmit(values: RuleBuilderValues) {
    try {
      await createRule.mutateAsync({
        name: values.name,
        description: values.description,
        trigger_event: values.trigger_event,
        conditions: values.conditions,
        actions: values.actions.map((a) => ({
          type: a.type,
          params: a.params,
        })),
        enabled: values.enabled,
      });
      router.push("/automation/rules");
    } catch {
      // mutateAsync throws; callers can use createRule.isError / createRule.error
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/automation/rules"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to rules
        </Link>
      </div>
      <div>
        <h1 className="text-2xl font-bold">Create Automation Rule</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Define a trigger, conditions, and actions to automate your workflow.
        </p>
      </div>
      <RuleBuilder
        onSubmit={handleSubmit}
        onCancel={() => router.push("/automation/rules")}
        submitLabel="Create Rule"
        disabled={createRule.isPending}
      />
    </div>
  );
}