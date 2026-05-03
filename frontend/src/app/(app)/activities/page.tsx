"use client";
import { useState } from "react";
import { useActivities } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

const TYPE_COLORS: Record<string, string> = {
  call: "bg-blue-100 text-blue-800",
  email: "bg-green-100 text-green-800",
  meeting: "bg-purple-100 text-purple-800",
  note: "bg-gray-100 text-gray-600",
  demo: "bg-yellow-100 text-yellow-800",
};

const TYPE_ICONS: Record<string, string> = {
  call: "📞",
  email: "📧",
  meeting: "🤝",
  note: "📝",
  demo: "🎯",
};

export default function ActivitiesPage() {
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [keyword, setKeyword] = useState("");

  const { data, isLoading } = useActivities(page, typeFilter);
  const items = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Activities</h1>
      </div>

      <div className="flex flex-wrap gap-2">
        <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="call">Call</SelectItem>
            <SelectItem value="email">Email</SelectItem>
            <SelectItem value="meeting">Meeting</SelectItem>
            <SelectItem value="note">Note</SelectItem>
            <SelectItem value="demo">Demo</SelectItem>
          </SelectContent>
        </Select>
        <Input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Search activities…"
          className="w-56"
        />
      </div>

      <div className="space-y-3">
        {isLoading && <div className="py-8 text-center text-muted-foreground">Loading…</div>}
        {!isLoading && items.length === 0 && (
          <div className="py-12 text-center text-muted-foreground">No activities found</div>
        )}
        {items.map((a) => (
          <div key={String(a.id)} className="flex items-start gap-3 rounded-md border p-3">
            <span className="text-xl flex-shrink-0">{TYPE_ICONS[String(a.type)] ?? "📌"}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <Badge colorClass={TYPE_COLORS[String(a.type)] ?? "bg-gray-100 text-gray-600"}>
                  {String(a.type ?? "")}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {a.created_at ? new Date(String(a.created_at)).toLocaleDateString() : ""}
                </span>
              </div>
              <p className="text-sm">{String(a.content ?? "")}</p>
              {a.customer_id && (
                <p className="text-xs text-muted-foreground mt-1">Customer #{a.customer_id}</p>
              )}
            </div>
          </div>
        ))}
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
