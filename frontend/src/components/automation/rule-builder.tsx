"use client";
import { useState, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { TriggerSelector } from "./trigger-selector";
import { ConditionRow, type ConditionRowValue } from "./condition-row";
import { ActionRow, type ActionRowValue } from "./action-row";
import { Plus } from "lucide-react";

export interface RuleBuilderValues {
  name: string;
  description: string;
  trigger_event: string;
  conditions: ConditionRowValue[];
  actions: ActionRowValue[];
}

interface RuleBuilderProps {
  initialValues?: Partial<RuleBuilderValues>;
  onSubmit: (values: RuleBuilderValues) => Promise<void>;
  onCancel?: () => void;
  submitLabel?: string;
  disabled?: boolean;
}

function makeCondition(): ConditionRowValue {
  return { field: "", operator: "eq", value: "" };
}

function makeAction(): ActionRowValue {
  return { type: "", params: {} };
}

export function RuleBuilder({
  initialValues,
  onSubmit,
  onCancel,
  submitLabel = "Save Rule",
  disabled = false,
}: RuleBuilderProps) {
  const [name, setName] = useState(initialValues?.name ?? "");
  const [description, setDescription] = useState(initialValues?.description ?? "");
  const [trigger, setTrigger] = useState(initialValues?.trigger_event ?? "");
  const [conditions, setConditions] = useState<ConditionRowValue[]>(
    initialValues?.conditions?.length ? initialValues.conditions : []
  );
  const [actions, setActions] = useState<ActionRowValue[]>(
    initialValues?.actions?.length ? initialValues.actions : [makeAction()]
  );
  const [validationError, setValidationError] = useState("");

  const addCondition = useCallback(() => {
    setConditions((prev) => [...prev, makeCondition()]);
  }, []);

  const removeCondition = useCallback((index: number) => {
    setConditions((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const updateCondition = useCallback((index: number, val: ConditionRowValue) => {
    setConditions((prev) => prev.map((c, i) => (i === index ? val : c)));
  }, []);

  const addAction = useCallback(() => {
    setActions((prev) => [...prev, makeAction()]);
  }, []);

  const removeAction = useCallback((index: number) => {
    setActions((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const updateAction = useCallback((index: number, val: ActionRowValue) => {
    setActions((prev) => prev.map((a, i) => (i === index ? val : a)));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError("");

    const filledActions = actions.filter((a) => a.type.trim() !== "");
    if (filledActions.length === 0) {
      setValidationError("At least one action is required.");
      return;
    }
    if (!name.trim()) {
      setValidationError("Rule name is required.");
      return;
    }
    if (!trigger) {
      setValidationError("A trigger event is required.");
      return;
    }

    const payload: RuleBuilderValues = {
      name: name.trim(),
      description: description.trim(),
      trigger_event: trigger,
      conditions: conditions.filter((c) => c.field.trim() !== ""),
      actions: filledActions,
    };

    await onSubmit(payload);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {validationError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {validationError}
        </div>
      )}

      {/* Basic info */}
      <div className="space-y-4">
        <div>
          <label htmlFor="rule-name" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Rule Name *</label>
          <Input
            id="rule-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. High-priority ticket alert"
            disabled={disabled}
            className="mt-1"
          />
        </div>
        <div>
          <label htmlFor="rule-description" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Description</label>
          <Textarea
            id="rule-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description…"
            disabled={disabled}
            className="mt-1"
            rows={2}
          />
        </div>
      </div>

      {/* Trigger */}
      <div className="space-y-2">
        <span className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">When this event occurs *</span>
        <TriggerSelector value={trigger} onChange={setTrigger} disabled={disabled} />
        {trigger && (
          <p className="text-xs text-muted-foreground">
            Trigger: <span className="font-mono">{trigger}</span>
          </p>
        )}
      </div>

      {/* Conditions */}
      <div className="space-y-3">
        <span className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">IF all of the following conditions are met (optional)</span>
        {conditions.length === 0 && (
          <p className="text-sm text-muted-foreground">No conditions — rule runs on every trigger event.</p>
        )}
        <div className="space-y-2">
          {conditions.map((cond, i) => (
            <ConditionRow
              key={i}
              value={cond}
              onChange={(val) => updateCondition(i, val)}
              onRemove={() => removeCondition(i)}
              disabled={disabled}
            />
          ))}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addCondition}
          disabled={disabled}
        >
          <Plus className="h-4 w-4 mr-1" />
          Add condition
        </Button>
      </div>

      {/* Actions */}
      <div className="space-y-3">
        <span className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">THEN perform these actions *</span>
        <div className="space-y-2">
          {actions.map((action, i) => (
            <ActionRow
              key={i}
              value={action}
              onChange={(val) => updateAction(i, val)}
              onRemove={() => removeAction(i)}
              disabled={disabled}
            />
          ))}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addAction}
          disabled={disabled}
        >
          <Plus className="h-4 w-4 mr-1" />
          Add action
        </Button>
      </div>

      {/* Footer */}
      <div className="flex gap-3 pt-2 border-t">
        <Button type="submit" disabled={disabled}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={disabled}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}