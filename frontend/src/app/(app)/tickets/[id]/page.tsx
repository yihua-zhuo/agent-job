"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { useTicket, useTicketReplies, useTicketActivity, useAddReply, useUpdateTicket, useDeleteTicket, useCustomers } from "@/lib/api/queries";
import { SLATimer } from "@/components/tickets/sla-timer";
import { TicketFormDialog } from "@/components/tickets/ticket-form-dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EditIcon, Trash2Icon, ArrowLeftIcon, LockIcon, MessageSquareIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  pending: "bg-yellow-100 text-yellow-800",
  resolved: "bg-green-100 text-green-800",
  closed: "bg-gray-100 text-gray-500",
};
const PRIORITY_COLORS: Record<string, string> = {
  urgent: "bg-red-100 text-red-800",
  high: "bg-red-100 text-red-800",
  medium: "bg-blue-100 text-blue-800",
  low: "bg-gray-100 text-gray-600",
};
const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  pending: "Pending",
  resolved: "Resolved",
  closed: "Closed",
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export default function TicketDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const { id } = use(params);
  const ticketId = Number(id);
  const invalidTicketId = Number.isNaN(ticketId);

  useEffect(() => {
    if (invalidTicketId) {
      router.push("/tickets");
    }
  }, [invalidTicketId, router]);

  const { data: ticketData, isLoading: ticketLoading } = useTicket(ticketId);
  const { data: repliesData } = useTicketReplies(ticketId);
  const { data: activityData } = useTicketActivity(ticketId);
  const addReply = useAddReply();
  const updateTicket = useUpdateTicket();
  const deleteTicket = useDeleteTicket();

  const { data: customersData } = useCustomers(1, 100);
  const customers = (customersData?.data?.items ?? []) as Array<{ id: number; name: string }>;

  const [replyContent, setReplyContent] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const slaToastShownRef = useRef(false);

  const ticket = ticketData?.data as Record<string, unknown> | undefined;
  const customerName = useMemo(
    () => customers.find((c) => c.id === Number(ticket?.customer_id))?.name,
    [customers, ticket?.customer_id]
  );
  const replies = (repliesData?.data ?? []) as Array<Record<string, unknown>>;
  const activities = (activityData?.data ?? []) as Array<Record<string, unknown>>;

  // SLA breach toast on load
  useEffect(() => {
    if (ticket && ticket.response_deadline && !slaToastShownRef.current) {
      const deadline = new Date(ticket.response_deadline as string).getTime();
      if (deadline < Date.now() && !ticket.resolved_at) {
        slaToastShownRef.current = true;
        toast.error(`SLA breached on ticket #${ticketId}`);
      }
    }
  }, [ticket, ticketId]);

  if (invalidTicketId) {
    return null;
  }

  async function handleSendReply() {
    if (!replyContent.trim()) return;
    try {
      await addReply.mutateAsync({
        ticketId,
        data: {
          content: replyContent,
          is_internal: isInternal,
        },
      });
      setReplyContent("");
      toast.success(isInternal ? "Internal note saved" : "Reply sent");
    } catch {
      toast.error("Failed to send reply");
    }
  }

  if (ticketLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-muted rounded animate-pulse" />
        <div className="h-40 bg-muted rounded animate-pulse" />
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="text-center py-16">
        <p className="text-muted-foreground">Ticket not found.</p>
        <Button variant="link" onClick={() => router.push("/tickets")} className="mt-2">
          <ArrowLeftIcon className="h-4 w-4 mr-1" />
          Back to tickets
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => router.push("/tickets")}>
          <ArrowLeftIcon className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold">
              #{ticketId} — {ticket.subject as string}
            </h1>
            <span className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
              STATUS_COLORS[ticket.status as string] ?? "bg-gray-100 text-gray-600"
            )}>
              {STATUS_LABELS[ticket.status as string] ?? ticket.status}
            </span>
            <span className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
              PRIORITY_COLORS[ticket.priority as string] ?? "bg-gray-100 text-gray-600"
            )}>
              {ticket.priority as string}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setEditDialogOpen(true)}>
            <EditIcon className="h-4 w-4 mr-1" />
            Edit
          </Button>
          <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setDeleteDialogOpen(true)}>
            <Trash2Icon className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: description + replies */}
        <div className="lg:col-span-2 space-y-4">
          {/* Description */}
          <Card>
            <CardContent className="p-4 space-y-2">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Description</h2>
              <div className="prose prose-sm max-w-none text-sm">
                {ticket.description ? (
                  <ReactMarkdown>{ticket.description as string}</ReactMarkdown>
                ) : (
                  <p className="text-muted-foreground italic">No description provided.</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Reply thread */}
          <Card>
            <CardContent className="p-4 space-y-4">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Replies ({replies.length})
              </h2>
              {replies.length === 0 && (
                <p className="text-sm text-muted-foreground italic py-2">No replies yet.</p>
              )}
              {replies.map((reply) => (
                <div key={String(reply.id)} className="flex gap-3">
                  <Avatar size="sm" className="mt-0.5 shrink-0">
                    <AvatarFallback>{initials(`Agent ${reply.created_by}`)}</AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium">Agent {reply.created_by}</span>
                      {reply.is_internal && (
                        <span className="inline-flex items-center gap-1 text-xs bg-yellow-100 text-yellow-800 px-1.5 py-0.5 rounded-full">
                          <LockIcon className="h-3 w-3" />
                          Internal
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground ml-auto">
                        {formatDate(reply.created_at as string)}
                      </span>
                    </div>
                    <div className={cn(
                      "rounded-lg p-3 text-sm whitespace-pre-wrap",
                      reply.is_internal ? "bg-yellow-50 border border-yellow-200" : "bg-muted/40"
                    )}>
                      {(reply.content as string)}
                    </div>
                  </div>
                </div>
              ))}

              <Separator className="my-4" />

              {/* Reply form */}
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Button
                    variant={isInternal ? "outline" : "secondary"}
                    size="sm"
                    onClick={() => setIsInternal(false)}
                  >
                    <MessageSquareIcon className="h-4 w-4 mr-1" />
                    Send Reply
                  </Button>
                  <Button
                    variant={isInternal ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => setIsInternal(true)}
                  >
                    <LockIcon className="h-4 w-4 mr-1" />
                    Internal Note
                  </Button>
                </div>
                <Textarea
                  placeholder={isInternal ? "Write an internal note..." : "Write a reply..."}
                  value={replyContent}
                  onChange={(e) => setReplyContent(e.target.value)}
                  rows={3}
                />
                <div className="flex justify-end">
                  <Button size="sm" onClick={handleSendReply} disabled={!replyContent.trim() || addReply.isPending}>
                    {addReply.isPending ? "Sending..." : isInternal ? "Save Note" : "Send Reply"}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          <Card>
            <CardContent className="p-4 space-y-3">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Details</h2>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Assignee</span>
                  <span className="font-medium">
                    {ticket.assigned_to ? `Agent ${ticket.assigned_to}` : "Unassigned"}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Channel</span>
                  <span className="font-medium capitalize">{ticket.channel ? (ticket.channel as string) : "—"}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Customer</span>
                  <a
                    href={`/customers/${ticket.customer_id}`}
                    className="font-medium hover:underline text-primary"
                  >
                    {customerName ?? `#${ticket.customer_id ?? "—"}`}
                  </a>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Created</span>
                  <span className="text-right text-xs">{formatDate(ticket.created_at as string)}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">SLA Level</span>
                  <span className="font-medium capitalize">{(ticket.sla_level as string) ?? "standard"}</span>
                </div>
              </div>

              {ticket.response_deadline && (
                <div className="pt-2 border-t">
                  <span className="text-xs text-muted-foreground block mb-1.5">SLA Timer</span>
                  <SLATimer
                    responseDeadline={ticket.response_deadline as string}
                    createdAt={ticket.created_at as string}
                    slaLevel={(ticket.sla_level as string) ?? "standard"}
                  />
                </div>
              )}
            </CardContent>
          </Card>

          {/* Activity log */}
          <Card>
            <CardContent className="p-4 space-y-3">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Activity ({activities.length})
              </h2>
              {activities.length === 0 && (
                <p className="text-sm text-muted-foreground italic">No activity recorded.</p>
              )}
              <div className="space-y-2">
                {activities.map((act) => (
                  <div key={act.id as number} className="flex gap-2 text-xs">
                    <span className="text-muted-foreground shrink-0 w-24">
                      {formatDate(act.created_at as string)}
                    </span>
                    <span className="text-muted-foreground capitalize">{(act.type as string) ?? "event"}</span>
                    <span className="flex-1">{act.content as string}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <TicketFormDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        initialData={{
          id: ticketId,
          subject: (ticket.subject as string) ?? "",
          description: (ticket.description as string) ?? "",
          channel: (ticket.channel as string) ?? "email",
          priority: (ticket.priority as string) ?? "medium",
          sla_level: (ticket.sla_level as string) ?? "standard",
        }}
      />

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Ticket</DialogTitle>
            <DialogDescription>
              Delete ticket #{ticketId}? This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                try {
                  await deleteTicket.mutateAsync(ticketId);
                  setDeleteDialogOpen(false);
                  toast.success("Ticket deleted");
                  router.push("/tickets");
                } catch {
                  toast.error("Failed to delete ticket");
                }
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
