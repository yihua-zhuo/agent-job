"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { useCustomers, useCreateTicket, useUpdateTicket } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface TicketFormData {
  subject: string;
  description: string;
  customer_id: number;
  channel: string;
  priority: string;
  sla_level: string;
}

interface TicketFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialData?: Partial<TicketFormData> & { id?: number };
}

export function TicketFormDialog({ open, onOpenChange, initialData }: TicketFormDialogProps) {
  const isEditing = !!initialData?.id;
  const { data: customersData } = useCustomers(undefined, 20);
  const createTicket = useCreateTicket();
  const updateTicket = useUpdateTicket();

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<TicketFormData>({
    defaultValues: {
      subject: initialData?.subject ?? "",
      description: initialData?.description ?? "",
      customer_id: initialData?.customer_id ?? undefined,
      channel: initialData?.channel ?? "email",
      priority: initialData?.priority ?? "medium",
      sla_level: initialData?.sla_level ?? "standard",
    },
  });

  useEffect(() => {
    reset({
      subject: initialData?.subject ?? "",
      description: initialData?.description ?? "",
      customer_id: initialData?.customer_id ?? undefined,
      channel: initialData?.channel ?? "email",
      priority: initialData?.priority ?? "medium",
      sla_level: initialData?.sla_level ?? "standard",
    });
  }, [initialData, reset]);

  const customers = (customersData?.data?.items ?? []) as Array<{ id: number; name: string }>;

  async function onSubmit(data: TicketFormData) {
    try {
      if (isEditing && initialData?.id) {
        await updateTicket.mutateAsync({
          id: initialData.id,
          data: {
            subject: data.subject,
            description: data.description,
            channel: data.channel,
            priority: data.priority,
          },
        });
        toast.success("Ticket updated successfully");
      } else {
        await createTicket.mutateAsync({
          subject: data.subject,
          description: data.description,
          customer_id: Number(data.customer_id),
          channel: data.channel,
          priority: data.priority,
          sla_level: data.sla_level,
        });
        toast.success("Ticket created successfully");
      }
      onOpenChange(false);
      reset();
    } catch (e) {
      console.error("Ticket submit error:", e);
      toast.error(isEditing ? "Failed to update ticket" : "Failed to create ticket");
    }
  }

  function handleClose(open: boolean) {
    if (!open) reset();
    onOpenChange(open);
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit Ticket" : "Create Ticket"}</DialogTitle>
          <DialogDescription>
            {isEditing ? "Update the ticket details below." : "Fill in the ticket details below."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="subject" className="text-sm font-medium">
              Subject <span className="text-destructive">*</span>
            </label>
            <Input
              id="subject"
              placeholder="Brief summary of the issue"
              {...register("subject", { required: "Subject is required" })}
              aria-invalid={!!errors.subject}
            />
            {errors.subject && (
              <p className="text-xs text-destructive">{errors.subject.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="description" className="text-sm font-medium">
              Description
            </label>
            <Textarea
              id="description"
              placeholder="Detailed description of the issue..."
              rows={4}
              {...register("description")}
            />
          </div>

          {!isEditing && (
            <>
              <div className="space-y-1.5">
                <label htmlFor="customer_id" className="text-sm font-medium">
                  Customer <span className="text-destructive">*</span>
                </label>
                <Select
                  onValueChange={(v) => setValue("customer_id", Number(v), { shouldValidate: true })}
                  defaultValue={String(initialData?.customer_id ?? "")}
                >
                  <SelectTrigger id="customer_id">
                    <SelectValue placeholder="Select a customer" />
                  </SelectTrigger>
                  <SelectContent>
                    {customers.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <input
                  type="hidden"
                  {...register("customer_id", {
                    validate: (v) => v > 0 || "Customer is required",
                  })}
                />
                {errors.customer_id && (
                  <p className="text-xs text-destructive">Customer is required</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="channel" className="text-sm font-medium">
                    Channel
                  </label>
                  <Select
                    onValueChange={(v) => setValue("channel", v)}
                    defaultValue={initialData?.channel ?? "email"}
                  >
                    <SelectTrigger id="channel">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="email">Email</SelectItem>
                      <SelectItem value="chat">Chat</SelectItem>
                      <SelectItem value="whatsapp">WhatsApp</SelectItem>
                      <SelectItem value="phone">Phone</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="priority" className="text-sm font-medium">
                    Priority
                  </label>
                  <Select
                    onValueChange={(v) => setValue("priority", v)}
                    defaultValue={initialData?.priority ?? "medium"}
                  >
                    <SelectTrigger id="priority">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="urgent">Urgent</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="sla_level" className="text-sm font-medium">
                  SLA Level
                </label>
                <Select
                  onValueChange={(v) => setValue("sla_level", v)}
                  defaultValue={initialData?.sla_level ?? "standard"}
                >
                  <SelectTrigger id="sla_level">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="basic">Basic (24h)</SelectItem>
                    <SelectItem value="standard">Standard (8h)</SelectItem>
                    <SelectItem value="premium">Premium (4h)</SelectItem>
                    <SelectItem value="enterprise">Enterprise (1h)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => handleClose(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : isEditing ? "Save Changes" : "Create Ticket"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}