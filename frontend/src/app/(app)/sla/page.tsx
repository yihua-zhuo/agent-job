"use client";
import { useState } from "react";
import { useSlaBreaches, useTickets } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  pending: "bg-yellow-100 text-yellow-800",
  resolved: "bg-green-100 text-green-800",
  closed: "bg-gray-100 text-gray-500",
};

const SLA_COLORS: Record<string, string> = {
  breached: "bg-red-100 text-red-800 border-red-300",
  at_risk: "bg-yellow-100 text-yellow-800 border-yellow-300",
  on_track: "bg-green-100 text-green-800 border-green-300",
};

function slaStatus(ticket: Record<string, unknown>) {
  if (ticket.status === "resolved" || ticket.status === "closed") return "on_track";
  const deadline = ticket.response_deadline ? new Date(String(ticket.response_deadline)) : null;
  if (!deadline) return "on_track";
  const hoursLeft = (deadline.getTime() - Date.now()) / 3600000;
  if (hoursLeft < 0) return "breached";
  if (hoursLeft < 4) return "at_risk";
  return "on_track";
}

function slaLabel(ticket: Record<string, unknown>) {
  const s = slaStatus(ticket);
  if (s === "breached") return "Breached";
  if (s === "at_risk") return "At Risk";
  return "On Track";
}

export default function SlaPage() {
  const { data: breachData, isLoading: breachLoading } = useSlaBreaches();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useTickets(page, "open");
  const tickets = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;

  const breaches = (breachData?.data?.items ?? []) as Record<string, unknown>[];

  const atRisk = tickets.filter((t) => slaStatus(t) === "at_risk");
  const onTrack = tickets.filter((t) => slaStatus(t) === "on_track" && t.status !== "resolved" && t.status !== "closed");

  function fmtDeadline(deadline: unknown) {
    if (!deadline) return "—";
    const d = new Date(String(deadline));
    return d.toLocaleString();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">SLA Configuration</h1>
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
        <Card>
          <CardContent className="p-4 text-center space-y-2">
            <div className="text-3xl font-bold text-red-600">{breaches.length}</div>
            <div className="text-sm text-muted-foreground">SLA Breaches</div>
            <Badge colorClass="bg-red-100 text-red-800">Action Required</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center space-y-2">
            <div className="text-3xl font-bold text-yellow-600">{atRisk.length}</div>
            <div className="text-sm text-muted-foreground">At Risk</div>
            <Badge colorClass="bg-yellow-100 text-yellow-800">Within 4 hours</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center space-y-2">
            <div className="text-3xl font-bold text-green-600">{onTrack.length}</div>
            <div className="text-sm text-muted-foreground">On Track</div>
            <Badge colorClass="bg-green-100 text-green-800">Healthy</Badge>
          </CardContent>
        </Card>
      </div>

      {breachLoading && <div className="py-8 text-center text-muted-foreground">Loading SLA status…</div>}

      {breaches.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">Breached Tickets</h2>
          <div className="rounded-md border border-red-300 bg-red-50/30 divide-y">
            {breaches.map((t) => (
              <div key={String(t.id)} className="flex items-center justify-between p-3">
                <div>
                  <div className="font-medium text-sm">{String(t.subject ?? `Ticket #${t.id}`)}</div>
                  <div className="text-xs text-muted-foreground">SLA Level: {String(t.sla_level ?? "standard")}</div>
                </div>
                <div className="text-right">
                  <Badge colorClass="bg-red-100 text-red-800">Breached</Badge>
                  <div className="text-xs text-muted-foreground mt-1">Deadline: {fmtDeadline(t.response_deadline)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-3 py-2.5 text-left font-semibold">ID</th>
              <th className="px-3 py-2.5 text-left font-semibold">Subject</th>
              <th className="px-3 py-2.5 text-left font-semibold">SLA</th>
              <th className="px-3 py-2.5 text-left font-semibold">Status</th>
              <th className="px-3 py-2.5 text-left font-semibold">Deadline</th>
              <th className="px-3 py-2.5 text-left font-semibold">SLA Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">Loading…</td></tr>}
            {!isLoading && tickets.length === 0 && <tr><td colSpan={6} className="px-3 py-8 text-center text-muted-foreground">No open tickets</td></tr>}
            {tickets.map((t) => (
              <tr key={String(t.id)} className="border-b hover:bg-muted/50 transition-colors">
                <td className="px-3 py-2.5 font-mono text-xs text-muted-foreground">#{t.id}</td>
                <td className="px-3 py-2.5 font-medium text-sm">{String(t.subject ?? "")}</td>
                <td className="px-3 py-2.5 text-sm">{String(t.sla_level ?? "standard")}</td>
                <td className="px-3 py-2.5"><Badge colorClass={STATUS_COLORS[String(t.status)] ?? "bg-gray-100 text-gray-600"}>{String(t.status ?? "")}</Badge></td>
                <td className="px-3 py-2.5 text-sm text-muted-foreground">{fmtDeadline(t.response_deadline)}</td>
                <td className="px-3 py-2.5"><Badge colorClass={SLA_COLORS[slaStatus(t)]}>{slaLabel(t)}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {info && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Showing {info.total === 0 ? 0 : ((page - 1) * 20) + 1}–{Math.min(page * 20, info.total)} of {info.total}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</Button>
            <Button variant="outline" size="sm" disabled={!info.has_next} onClick={() => setPage(page + 1)}>Next →</Button>
          </div>
        </div>
      )}
    </div>
  );
}
