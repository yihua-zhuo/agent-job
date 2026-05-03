"use client";
import { useState } from "react";
import { useNotifications, useMarkAllNotificationsRead, useMarkNotificationRead } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const TYPE_COLORS: Record<string, string> = {
  info: "bg-blue-100 text-blue-800",
  warning: "bg-yellow-100 text-yellow-800",
  error: "bg-red-100 text-red-800",
  success: "bg-green-100 text-green-800",
};

export default function NotificationsPage() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const { data, isLoading, isError } = useNotifications(page, unreadOnly);
  const items = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;

  const markAll = useMarkAllNotificationsRead();
  const markOne = useMarkNotificationRead();

  function formatTime(ts: string) {
    const d = new Date(ts);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const mins = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Notifications</h1>
        <div className="flex gap-2">
          <Button
            variant={unreadOnly ? "default" : "outline"}
            size="sm"
            onClick={() => { setUnreadOnly(!unreadOnly); setPage(1); }}
          >
            {unreadOnly ? "All" : "Unread Only"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => markAll.mutate()}
            disabled={markAll.isPending}
          >
            Mark All Read
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        {isLoading && <div className="py-8 text-center text-muted-foreground">Loading…</div>}
        {isError && <div className="py-8 text-center text-destructive">Failed to load notifications</div>}
        {!isLoading && items.length === 0 && (
          <div className="py-12 text-center text-muted-foreground">
            <div className="text-4xl mb-2">🔔</div>
            <p>No notifications</p>
          </div>
        )}
        {items.map((n) => (
          <div
            key={String(n.id)}
            className={`flex items-start gap-3 rounded-md border p-3 transition-colors ${n.is_read ? "bg-background" : "bg-blue-50/50 border-blue-200"}`}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                {!n.is_read && <span className="h-2 w-2 rounded-full bg-blue-500 flex-shrink-0" />}
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${TYPE_COLORS[String(n.type ?? "info")] ?? "bg-gray-100 text-gray-600"}`}>
                  {String(n.type ?? "info")}
                </span>
                <span className="text-xs text-muted-foreground">{n.created_at ? formatTime(String(n.created_at)) : ""}</span>
              </div>
              <div className="font-medium text-sm">{String(n.title ?? "")}</div>
              {n.content && (
                <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">{String(n.content)}</p>
              )}
            </div>
            {!n.is_read && (
              <Button
                variant="ghost"
                size="sm"
                className="text-xs flex-shrink-0"
                onClick={() => markOne.mutate(Number(n.id))}
                disabled={markOne.isPending}
              >
                Mark read
              </Button>
            )}
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
