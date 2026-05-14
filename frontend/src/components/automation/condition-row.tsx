"use client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { X } from "lucide-react";

const OPERATORS = [
  { value: "eq", label: "equals" },
  { value: "ne", label: "not equals" },
  { value: "gt", label: "greater than" },
  { value: "gte", label: "greater than or equal" },
  { value: "lt", label: "less than" },
  { value: "lte", label: "less than or equal" },
  { value: "contains", label: "contains" },
  { value: "startswith", label: "starts with" },
  { value: "endswith", label: "ends with" },
] as const;

export type OperatorValue = (typeof OPERATORS)[number]["value"];

const DEFAULT_OPERATOR: OperatorValue = "eq";

export interface ConditionRowValue {
  field: string;
  operator: string;
  value: string;
}

interface ConditionRowProps {
  value: ConditionRowValue;
  onChange: (value: ConditionRowValue) => void;
  onRemove: () => void;
  disabled?: boolean;
}

export function ConditionRow({ value, onChange, onRemove, disabled }: ConditionRowProps) {
  function updateField(field: string) {
    onChange({ ...value, field });
  }
  function updateOperator(operator: OperatorValue) {
    onChange({ ...value, operator });
  }
  function updateValue(newValue: string) {
    onChange({ ...value, value: newValue });
  }

  return (
    <div className="flex items-center gap-2">
      <Input
        placeholder="field_name"
        value={value.field}
        onChange={(e) => updateField(e.target.value.replace(/[^a-zA-Z0-9._-]/g, ""))}
        disabled={disabled}
        className="flex-shrink-0 w-40"
      />
      <Select value={value.operator || DEFAULT_OPERATOR} onValueChange={updateOperator} disabled={disabled}>
        <SelectTrigger className="flex-shrink-0 w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {OPERATORS.map((op) => (
            <SelectItem key={op.value} value={op.value}>
              {op.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Input
        placeholder="value"
        value={value.value}
        onChange={(e) => updateValue(e.target.value)}
        disabled={disabled}
        className="flex-1 min-w-0"
      />
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={onRemove}
        disabled={disabled}
        aria-label="Remove condition"
        className="flex-shrink-0 text-muted-foreground hover:text-destructive"
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}