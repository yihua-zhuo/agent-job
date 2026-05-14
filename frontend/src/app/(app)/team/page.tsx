"use client";
import { useState } from "react";
import { useUsers, useCreateUser, useUpdateUser, useDeleteUser } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { Pencil, Trash2, UserPlus, Search } from "lucide-react";

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

interface MemberForm {
  username: string;
  email: string;
  password: string;
  full_name: string;
  role: string;
}

const blankForm: MemberForm = { username: "", email: "", password: "", full_name: "", role: "user" };

export default function TeamPage() {
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState("all");
  const [search, setSearch] = useState("");

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<MemberForm>(blankForm);

  // Edit dialog
  const [editingUser, setEditingUser] = useState<Record<string, unknown> | null>(null);
  const [editForm, setEditForm] = useState<Partial<MemberForm>>({});
  const [showEdit, setShowEdit] = useState(false);

  // Delete dialog
  const [deletingUser, setDeletingUser] = useState<Record<string, unknown> | null>(null);
  const [showDelete, setShowDelete] = useState(false);

  const { data, isLoading } = useUsers(page, 20, search, roleFilter !== "all" ? roleFilter : "");
  const items = (data?.data?.items ?? []) as Record<string, unknown>[];
  const info = data?.data;
  const create = useCreateUser();
  const updateUser = useUpdateUser();
  const deleteUser = useDeleteUser();

  const totalShown = info?.total ?? 0;
  const startShown = info?.total === 0 ? 0 : ((page - 1) * (info?.page_size ?? 20)) + 1;
  const endShown = Math.min(page * (info?.page_size ?? 20), info?.total ?? 0);

  // Create
  async function handleCreate() {
    if (!createForm.username || !createForm.email || !createForm.password) return;
    try {
      await create.mutateAsync(createForm as unknown as Record<string, unknown>);
      setShowCreate(false);
      setCreateForm(blankForm);
    } catch { /* error surfaced via create.isError */ }
  }

  // Edit
  function openEdit(u: Record<string, unknown>) {
    setEditingUser(u);
    setEditForm({
      full_name: String(u.full_name ?? ""),
      email: String(u.email ?? ""),
    });
    setShowEdit(true);
  }

  async function handleEdit() {
    if (!editingUser) return;
    try {
      await updateUser.mutateAsync({ id: Number(editingUser.id), data: editForm });
      setShowEdit(false);
      setEditingUser(null);
    } catch { /* error surfaced via updateUser.isError */ }
  }

  // Delete
  function openDelete(u: Record<string, unknown>) {
    setDeletingUser(u);
    setShowDelete(true);
  }

  async function handleDelete() {
    if (!deletingUser) return;
    try {
      await deleteUser.mutateAsync(Number(deletingUser.id));
      setShowDelete(false);
      setDeletingUser(null);
    } catch { /* error surfaced via deleteUser.isError */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Team Members</h1>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <UserPlus className="h-4 w-4 mr-1" />
          Add Member
        </Button>
      </div>

      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by name or email…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="pl-8"
            aria-label="Search team members"
          />
        </div>
        <Select value={roleFilter} onValueChange={(v) => { setRoleFilter(v); setPage(1); }}>
          <SelectTrigger className="w-36" aria-label="Filter by role">
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

      {/* Table */}
      <div className="rounded-md border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-3 py-2.5 text-left font-semibold">Name</th>
              <th className="px-3 py-2.5 text-left font-semibold">Email</th>
              <th className="px-3 py-2.5 text-left font-semibold">Role</th>
              <th className="px-3 py-2.5 text-left font-semibold">Status</th>
              <th className="px-3 py-2.5 text-left font-semibold">Joined</th>
              <th className="px-3 py-2.5 text-right font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && Array.from({ length: 6 }).map((_, i) => (
              <tr key={i} className="border-b">
                <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-32 animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-40 animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-5 bg-muted rounded w-16 animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-5 bg-muted rounded w-14 animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-20 animate-pulse" /></td>
                <td className="px-3 py-2.5" />
              </tr>
            ))}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-10 text-center text-muted-foreground">
                  No team members found
                </td>
              </tr>
            )}
            {items.map((u) => (
              <tr key={String(u.id)} className="border-b hover:bg-muted/40 transition-colors">
                <td className="px-3 py-2.5">
                  <div className="font-medium">{String(u.full_name ?? u.username ?? "")}</div>
                  <div className="text-xs text-muted-foreground">#{String(u.id)}</div>
                </td>
                <td className="px-3 py-2.5 text-muted-foreground">{String(u.email ?? "—")}</td>
                <td className="px-3 py-2.5">
                  <Badge colorClass={ROLE_COLORS[String(u.role)] ?? "bg-blue-100 text-blue-800"}>
                    {String(u.role ?? "")}
                  </Badge>
                </td>
                <td className="px-3 py-2.5">
                  <Badge colorClass={STATUS_COLORS[String(u.status)] ?? "bg-gray-100 text-gray-600"}>
                    {String(u.status ?? "")}
                  </Badge>
                </td>
                <td className="px-3 py-2.5 text-muted-foreground text-xs">
                  {u.created_at ? new Date(String(u.created_at)).toLocaleDateString() : "—"}
                </td>
                <td className="px-3 py-2.5 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => openEdit(u)} aria-label="Edit member" title="Edit">
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-destructive hover:text-destructive" onClick={() => openDelete(u)} aria-label="Delete member" title="Delete">
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {info && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Showing {startShown}–{endShown} of {totalShown}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</Button>
            <Button variant="outline" size="sm" disabled={!info.has_next} onClick={() => setPage(page + 1)}>Next →</Button>
          </div>
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={(o) => !o && setShowCreate(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Add Team Member</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {[
              { label: "Username *", key: "username", type: "text" },
              { label: "Email *", key: "email", type: "email" },
              { label: "Password *", key: "password", type: "password" },
              { label: "Full Name", key: "full_name", type: "text" },
            ].map(({ label, key, type }) => (
              <div key={key} className="space-y-1">
                <label className="text-sm font-medium">{label}</label>
                <Input
                  type={type}
                  value={createForm[key as keyof MemberForm]}
                  onChange={(e) => setCreateForm((f) => ({ ...f, [key]: e.target.value }))}
                  placeholder={label}
                />
              </div>
            ))}
            <div className="space-y-1">
              <label className="text-sm font-medium">Role</label>
              <Select value={createForm.role} onValueChange={(v) => setCreateForm((f) => ({ ...f, role: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">User</SelectItem>
                  <SelectItem value="manager">Manager</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {create.isError && <p className="text-xs text-destructive">Failed to create member</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={create.isPending || !createForm.username || !createForm.email || !createForm.password}>
              {create.isPending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEdit} onOpenChange={(o) => !o && setShowEdit(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Edit Member</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label htmlFor="edit-full-name" className="text-sm font-medium">Full Name</label>
              <Input
                id="edit-full-name"
                value={editForm.full_name ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="edit-email" className="text-sm font-medium">Email</label>
              <Input
                id="edit-email"
                type="email"
                value={editForm.email ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
              />
            </div>
            {updateUser.isError && <p className="text-xs text-destructive">Failed to update member</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEdit(false)}>Cancel</Button>
            <Button onClick={handleEdit} disabled={updateUser.isPending}>
              {updateUser.isPending ? "Saving…" : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={showDelete} onOpenChange={(o) => !o && setShowDelete(false)}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Remove Member</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to remove <strong>{String(deletingUser?.full_name ?? deletingUser?.username ?? "")}</strong>? This action cannot be undone.
          </p>
          <DialogFooter className="flex-col gap-2 sm:flex-col">
            {deleteUser.isError && <p className="text-xs text-destructive text-center">Failed to remove member</p>}
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowDelete(false)}>Cancel</Button>
              <Button variant="destructive" onClick={handleDelete} disabled={deleteUser.isPending}>
                {deleteUser.isPending ? "Removing…" : "Remove"}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}