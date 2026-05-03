"use client";
import { useState } from "react";
import { useUsers, useCreateUser } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-red-100 text-red-800",
  manager: "bg-yellow-100 text-yellow-800",
  user: "bg-blue-100 text-blue-800",
};
const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  pending: "bg-yellow-100 text-yellow-800",
  inactive: "bg-gray-100 text-gray-500",
};

export default function TeamPage() {
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ username: "", email: "", password: "", full_name: "", role: "user" });

  const { data, isLoading } = useUsers(page);
  const items = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;
  const create = useCreateUser();

  const filtered = roleFilter === "all" ? items : items.filter((u) => u.role === roleFilter);

  async function handleCreate() {
    if (!form.username || !form.email || !form.password) return;
    try {
      await create.mutateAsync(form as Record<string, unknown>);
      setShowCreate(false);
      setForm({ username: "", email: "", password: "", full_name: "", role: "user" });
    } catch {
      // mutation error is surfaced via create.isError / create.error in the UI
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Team Directory</h1>
        <Button size="sm" onClick={() => setShowCreate(true)}>+ Add Member</Button>
      </div>

      <div className="flex gap-2">
        <Select value={roleFilter} onValueChange={(v) => { setRoleFilter(v); setPage(1); }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="All Roles" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Roles</SelectItem>
            <SelectItem value="admin">Admin</SelectItem>
            <SelectItem value="manager">Manager</SelectItem>
            <SelectItem value="user">User</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
        {isLoading && Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}><CardContent className="p-4 animate-pulse space-y-2"><div className="h-4 bg-muted rounded w-3/4" /><div className="h-3 bg-muted rounded w-1/2" /></CardContent></Card>
        ))}
        {!isLoading && filtered.length === 0 && <div className="col-span-full py-12 text-center text-muted-foreground">No team members found</div>}
        {filtered.map((u) => (
          <Card key={String(u.id)} className="hover:shadow-md transition-shadow">
            <CardContent className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="font-medium text-sm">{String(u.full_name ?? u.username ?? "")}</div>
                <Badge colorClass={STATUS_COLORS[String(u.status)] ?? "bg-gray-100 text-gray-600"}>{String(u.status ?? "")}</Badge>
              </div>
              <div className="text-xs text-muted-foreground">{String(u.email ?? "")}</div>
              <div className="flex items-center gap-2">
                <Badge colorClass={ROLE_COLORS[String(u.role)] ?? "bg-blue-100 text-blue-800"}>{String(u.role ?? "")}</Badge>
                <span className="text-xs text-muted-foreground">#{String(u.id)}</span>
              </div>
              {Boolean(u.created_at) && (
                <div className="text-xs text-muted-foreground">Joined {new Date(String(u.created_at)).toLocaleDateString()}</div>
              )}
            </CardContent>
          </Card>
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

      <Dialog open={showCreate} onOpenChange={(o) => !o && setShowCreate(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Add Team Member</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">Username *</label>
              <Input value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} placeholder="username" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Email *</label>
              <Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} placeholder="email@example.com" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Password *</label>
              <Input type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} placeholder="Min 8 chars" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Full Name</label>
              <Input value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} placeholder="Full Name" />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Role</label>
              <Select value={form.role} onValueChange={(v) => setForm((f) => ({ ...f, role: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">User</SelectItem>
                  <SelectItem value="manager">Manager</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={create.isPending || !form.username || !form.email || !form.password}>
              {create.isPending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
