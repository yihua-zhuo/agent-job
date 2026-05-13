"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { RuleBuilder } from "@/components/automation/rule-builder";
import type { RuleBuilderValues } from "@/components/automation/rule-builder";
import { useCreateAutomationRule } from "@/lib/api/queries";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function NewRulePage() {
  const router = useRouter();
  const createRule = useCreateAutomationRule();
  const [submitError, setSubmitError] = useState("");

  async function handleSubmit(values: RuleBuilderValues) {
    setSubmitError("");
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
        enabled: true,
      });
      router.push("/automation/rules");
    } catch {
      setSubmitError("Failed to create rule. Please try again.");
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
      {submitError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {submitError}
        </div>
      )}
      <RuleBuilder
        onSubmit={handleSubmit}
        onCancel={() => router.push("/automation/rules")}
        submitLabel="Create Rule"
        disabled={createRule.isPending}
      />
    </div>
  );
}