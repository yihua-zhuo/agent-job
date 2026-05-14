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

const ACTION_TYPES = [
  { value: "notification.send", label: "Send Notification" },
  { value: "ticket.assign", label: "Assign Ticket" },
  { value: "ticket.update_priority", label: "Update Ticket Priority" },
  { value: "opportunity.add_note", label: "Add Note to Opportunity" },
  { value: "task.create", label: "Create Task" },
  { value: "email.send", label: "Send Email" },
  { value: "webhook.call", label: "Call Webhook" },
  { value: "tag.add", label: "Add Tag" },
];

export interface ActionRowValue {
  type: string;
  params: Record<string, string>;
}

interface ActionRowProps {
  value: ActionRowValue;
  onChange: (value: ActionRowValue) => void;
  onRemove: () => void;
  disabled?: boolean;
}

function ParamsForm({ value, onChange, disabled }: { value: ActionRowValue; onChange: (params: Record<string, string>) => void; disabled?: boolean }) {
  function updateParam(key: string, val: string) {
    onChange({ ...value.params, [key]: val });
  }

  switch (value.type) {
    case "notification.send":
      return (
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="user_id"
            value={value.params.user_id ?? ""}
            onChange={(e) => updateParam("user_id", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
          <Input
            placeholder="message"
            value={value.params.message ?? ""}
            onChange={(e) => updateParam("message", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
        </div>
      );
    case "ticket.assign":
      return (
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="assignee_id"
            value={value.params.assignee_id ?? ""}
            onChange={(e) => updateParam("assignee_id", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
        </div>
      );
    case "ticket.update_priority":
      return (
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="priority (low/normal/high/urgent)"
            value={value.params.priority ?? ""}
            onChange={(e) => updateParam("priority", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
        </div>
      );
    case "task.create":
      return (
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="title"
            value={value.params.title ?? ""}
            onChange={(e) => updateParam("title", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
          <Input
            placeholder="assignee_id (optional)"
            value={value.params.assignee_id ?? ""}
            onChange={(e) => updateParam("assignee_id", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
        </div>
      );
    case "email.send":
      return (
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="to"
            value={value.params.to ?? ""}
            onChange={(e) => updateParam("to", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
          <Input
            placeholder="subject"
            value={value.params.subject ?? ""}
            onChange={(e) => updateParam("subject", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
        </div>
      );
    case "webhook.call":
      return (
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="url"
            value={value.params.url ?? ""}
            onChange={(e) => updateParam("url", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
        </div>
      );
    case "tag.add":
      return (
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="tag name"
            value={value.params.tag ?? ""}
            onChange={(e) => updateParam("tag", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
        </div>
      );
    case "opportunity.add_note":
      return (
        <div className="flex gap-2 mt-2">
          <Input
            placeholder="note"
            value={value.params.note ?? ""}
            onChange={(e) => updateParam("note", e.target.value)}
            disabled={disabled}
            className="flex-1"
          />
        </div>
      );
    default:
      return null;
  }
}

export function ActionRow({ value, onChange, onRemove, disabled }: ActionRowProps) {
  function updateType(type: string) {
    onChange({ type, params: {} });
  }
  function updateParams(params: Record<string, string>) {
    onChange({ ...value, params });
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border p-3 bg-muted/20">
      <div className="flex items-center gap-2">
        <Select value={value.type || ""} onValueChange={updateType} disabled={disabled}>
          <SelectTrigger className="flex-shrink-0 w-56">
            <SelectValue placeholder="Select action type…" />
          </SelectTrigger>
          <SelectContent>
            {ACTION_TYPES.map((at) => (
              <SelectItem key={at.value} value={at.value}>
                {at.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex-1" />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onRemove}
          disabled={disabled}
          aria-label="Remove action"
          className="flex-shrink-0 text-muted-foreground hover:text-destructive"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      {value.type && <ParamsForm value={value} onChange={updateParams} disabled={disabled} />}
    </div>
  );
}