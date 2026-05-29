"use client";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const TRIGGER_EVENTS = [
  { value: "ticket.created", label: "Ticket Created" },
  { value: "ticket.updated", label: "Ticket Updated" },
  { value: "ticket.assigned", label: "Ticket Assigned" },
  { value: "opportunity.stage_changed", label: "Opportunity Stage Changed" },
  { value: "opportunity.created", label: "Opportunity Created" },
  { value: "customer.created", label: "Customer Created" },
  { value: "customer.updated", label: "Customer Updated" },
  { value: "user.login", label: "User Login" },
  { value: "lead.created", label: "Lead Created" },
];

interface TriggerSelectorProps {
  value?: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function TriggerSelector({ value, onChange, disabled }: TriggerSelectorProps) {
  return (
    <Select value={value ?? ""} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder="Select a trigger event…" />
      </SelectTrigger>
      <SelectContent>
        {TRIGGER_EVENTS.map((e) => (
          <SelectItem key={e.value} value={e.value}>
            {e.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}