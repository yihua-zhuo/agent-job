"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { useCustomers, useSearchCustomers, useCreateCustomer, useDeleteCustomer } from "@/lib/api/queries";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, X, ChevronUp, ChevronDown, MoreHorizontal, UserPlus } from "lucide-react";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  lead: "bg-blue-100 text-blue-800",
  customer: "bg-green-100 text-green-800",
  partner: "bg-purple-100 text-purple-800",
  prospect: "bg-yellow-100 text-yellow-800",
  active: "bg-green-100 text-green-800",
  inactive: "bg-gray-100 text-gray-500",
  blocked: "bg-red-100 text-red-800",
};

type SortKey = "name" | "email" | "phone" | "status" | "company" | "created_at";
type SortDir = "asc" | "desc";

interface CustomerRowData {
  id: number;
  name: string;
  email: string;
  phone: string;
  status: string;
  company: string;
  created_at: string;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "numeric", day: "numeric", year: "numeric" });
}

function CustomerRow({
  c,
  onNavigate,
  selected,
  onToggle,
  onDelete,
}: {
  c: CustomerRowData;
  onNavigate: (id: number) => void;
  selected: boolean;
  onToggle: (id: number) => void;
  onDelete: (c: CustomerRowData) => void;
}) {
  return (
    <tr
      className={cn(
        "border-b hover:bg-muted/40 transition-colors group",
        selected && "bg-primary/5"
      )}
    >
      <td scope="row" className="px-3 py-2.5 w-10">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(c.id)}
          className="accent-primary h-4 w-4 cursor-pointer"
          onClick={(e) => e.stopPropagation()}
        />
      </td>
      <td scope="row" className="px-3 py-2.5">
        <span className="font-medium truncate block max-w-[160px]" title={c.name || "—"}>
          {c.name || "—"}
        </span>
      </td>
      <td scope="row" className="px-3 py-2.5">
        {c.email ? (
          <a
            href={`mailto:${c.email}`}
            className="text-sm text-muted-foreground hover:text-foreground underline-offset-2 hover:underline truncate block max-w-[180px]"
            title={c.email}
            onClick={(e) => e.stopPropagation()}
          >
            {c.email}
          </a>
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        )}
      </td>
      <td scope="row" className="px-3 py-2.5">
        {c.phone ? (
          <a
            href={`tel:${c.phone}`}
            className="text-sm font-mono text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {c.phone}
          </a>
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        )}
      </td>
      <td scope="row" className="px-3 py-2.5">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
            STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-600"
          )}
        >
          {c.status || "—"}
        </span>
      </td>
      <td scope="row" className="px-3 py-2.5">
        <span className="text-sm text-muted-foreground truncate block max-w-[140px]" title={c.company}>
          {c.company || "—"}
        </span>
      </td>
      <td scope="row" className="px-3 py-2.5">
        <span className="text-sm text-muted-foreground">{formatDate(c.created_at)}</span>
      </td>
      <td scope="row" className="px-3 py-2.5 w-10" onClick={(e) => e.stopPropagation()}>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100"
              aria-label="Row actions"
            >
              <MoreHorizontal className="h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onNavigate(c.id)}>View details</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive" onClick={() => onDelete(c)}>Delete</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </td>
    </tr>
  );
}

function useCustomersData(page: number, pageSize: number, keyword: string) {
  const search = useSearchCustomers(keyword);
  const list = useCustomers(page, pageSize);
  return keyword ? search : list;
}

interface CreateForm {
  name: string;
  email: string;
  phone: string;
  company: string;
  status: string;
}

const blankCreateForm: CreateForm = { name: "", email: "", phone: "", company: "", status: "lead" };

export default function CustomersPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(blankCreateForm);
  const createCustomer = useCreateCustomer();

  // Delete dialog
  const [deletingCustomer, setDeletingCustomer] = useState<CustomerRowData | null>(null);
  const [showDelete, setShowDelete] = useState(false);
  const deleteCustomer = useDeleteCustomer();

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setKeyword(val);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedKeyword(val);
      setPage(1);
    }, 300);
  }, []);

  const clearSearch = useCallback(() => {
    setKeyword("");
    setDebouncedKeyword("");
    setPage(1);
  }, []);

  // Escape key clears search when search input is focused
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && document.activeElement?.tagName === "INPUT") {
        clearSearch();
        (document.activeElement as HTMLInputElement)?.blur();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [clearSearch]);

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  const { data, isLoading, isError } = useCustomersData(
    debouncedKeyword ? 1 : page,
    pageSize,
    debouncedKeyword
  );

  const rawItems = data?.data?.items ?? [];
  const info = data?.data;

  const items: CustomerRowData[] = rawItems.map((c) => ({
    id: Number(c.id),
    name: String(c.name ?? ""),
    email: String(c.email ?? ""),
    phone: String(c.phone ?? ""),
    status: String(c.status ?? ""),
    company: String(c.company ?? ""),
    created_at: String(c.created_at ?? ""),
  }));

  const sorted = [...items].sort((a, b) => {
    if (!sortKey) return 0;
    const av = a[sortKey];
    const bv = b[sortKey];
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortDir === "asc" ? cmp : -cmp;
  });

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) {
      return <ChevronUp className="h-3 w-3 opacity-0 group-hover:opacity-40 transition-opacity inline ml-1" />;
    }
    return sortDir === "asc"
      ? <ChevronUp className="h-3 w-3 opacity-100 inline ml-1 text-primary" />
      : <ChevronDown className="h-3 w-3 opacity-100 inline ml-1 text-primary" />;
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function navigateToCustomer(id: number) {
    window.location.href = `/customers/${id}`;
  }

  function openDelete(c: CustomerRowData) {
    setDeletingCustomer(c);
    setShowDelete(true);
  }

  async function handleDelete() {
    if (!deletingCustomer) return;
    try {
      await deleteCustomer.mutateAsync(deletingCustomer.id);
      toast.success("Customer deleted");
      setShowDelete(false);
      setDeletingCustomer(null);
    } catch {
      toast.error("Failed to delete customer");
    }
  }

  async function handleCreate() {
    if (!createForm.name || !createForm.email) return;
    try {
      await createCustomer.mutateAsync(createForm as unknown as Record<string, unknown>);
      toast.success("Customer created");
      setShowCreate(false);
      setCreateForm(blankCreateForm);
    } catch {
      toast.error("Failed to create customer");
    }
  }

  function handlePageSizeChange(v: string) {
    setPageSize(Number(v));
    setPage(1);
  }

  const totalShown = info?.total ?? 0;
  const startShown = info?.total === 0 ? 0 : ((page - 1) * (info?.page_size ?? pageSize)) + 1;
  const endShown = Math.min(page * (info?.page_size ?? pageSize), info?.total ?? 0);

  return (
    <div className="space-y-0">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-background pb-4 border-b border-border mb-0">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <h1 className="text-2xl font-bold">Customers</h1>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <UserPlus className="h-4 w-4 mr-1" />
            Add Customer
          </Button>
        </div>
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            type="text"
            value={keyword}
            onChange={handleChange}
            placeholder="Search customers…"
            className="pl-8 pr-8 rounded-lg border-[1px] shadow-sm focus:ring-2 focus:ring-primary focus:ring-offset-1"
            aria-label="Search customers"
          />
          {keyword && (
            <button
              type="button"
              onClick={clearSearch}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
              aria-label="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border mt-4 overflow-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="sticky top-[calc(2.5rem+72px)] z-10 bg-muted/60 backdrop-blur-sm">
            <tr className="border-b border-border">
              <th scope="col" className="px-3 py-2.5 w-10">
                <input
                  type="checkbox"
                  className="accent-primary h-4 w-4 cursor-pointer"
                  aria-label="Select all"
                  onChange={(e) => {
                    if (e.target.checked) setSelectedIds(new Set(items.map((c) => c.id)));
                    else setSelectedIds(new Set());
                  }}
                  checked={items.length > 0 && selectedIds.size === items.length}
                />
              </th>
              <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none" onClick={() => handleSort("name")}>
                Name<SortIcon col="name" />
              </th>
              <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none" onClick={() => handleSort("email")}>
                Email<SortIcon col="email" />
              </th>
              <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none" onClick={() => handleSort("phone")}>
                Phone<SortIcon col="phone" />
              </th>
              <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none" onClick={() => handleSort("status")}>
                Status<SortIcon col="status" />
              </th>
              <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none" onClick={() => handleSort("company")}>
                Company<SortIcon col="company" />
              </th>
              <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none" onClick={() => handleSort("created_at")}>
                Created<SortIcon col="created_at" />
              </th>
              <th scope="col" className="px-3 py-2.5 w-10" />
            </tr>
          </thead>
          <tbody>
            {isLoading && Array.from({ length: 6 }).map((_, i) => (
              <tr key={i} className="border-b">
                <td scope="row" className="px-3 py-2.5"><div className="h-4 w-4 bg-muted rounded animate-pulse" /></td>
                <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-32 animate-pulse" /></td>
                <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-40 animate-pulse" /></td>
                <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-28 animate-pulse" /></td>
                <td scope="row" className="px-3 py-2.5"><div className="h-5 bg-muted rounded w-16 animate-pulse" /></td>
                <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-24 animate-pulse" /></td>
                <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-20 animate-pulse" /></td>
                <td scope="row" className="px-3 py-2.5" />
              </tr>
            ))}
            {isError && (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-destructive">Failed to load customers</td>
              </tr>
            )}
            {!isLoading && !isError && sorted.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-12 text-center">
                  <div className="flex flex-col items-center gap-2">
                    <Search className="h-8 w-8 text-muted-foreground/50" />
                    <p className="font-medium text-muted-foreground">No customers found</p>
                    {keyword && <p className="text-sm text-muted-foreground/70">No results for &ldquo;{keyword}&rdquo;</p>}
                  </div>
                </td>
              </tr>
            )}
            {sorted.map((c) => (
              <tr
                key={c.id}
                className="border-b hover:bg-muted/40 transition-colors group"
                onClick={() => navigateToCustomer(c.id)}
              >
                <CustomerRow
                  c={c}
                  onNavigate={navigateToCustomer}
                  selected={selectedIds.has(c.id)}
                  onToggle={toggleSelect}
                  onDelete={openDelete}
                />
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {info && !isError && (
        <div className="flex items-center justify-between text-xs text-muted-foreground py-3 gap-4">
          <span>
            {selectedIds.size > 0 ? `${selectedIds.size} selected` : `Showing ${startShown}–${endShown} of ${totalShown}`}
          </span>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Rows per page</span>
              <Select value={String(pageSize)} onValueChange={handlePageSizeChange}>
                <SelectTrigger className="w-16 h-7 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="20">20</SelectItem>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-1">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</Button>
              <Button variant="outline" size="sm" disabled={!info.has_next} onClick={() => setPage(page + 1)}>Next →</Button>
            </div>
          </div>
        </div>
      )}

      {/* Create Customer Dialog */}
      <Dialog open={showCreate} onOpenChange={(o) => !o && setShowCreate(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Customer</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {[
              { label: "Name *", key: "name", type: "text" },
              { label: "Email *", key: "email", type: "email" },
              { label: "Phone", key: "phone", type: "tel" },
              { label: "Company", key: "company", type: "text" },
            ].map(({ label, key, type }) => (
              <div key={key} className="space-y-1">
                <label className="text-sm font-medium">{label}</label>
                <Input
                  type={type}
                  value={createForm[key as keyof CreateForm]}
                  onChange={(e) => setCreateForm((f) => ({ ...f, [key]: e.target.value }))}
                  placeholder={label}
                />
              </div>
            ))}
            <div className="space-y-1">
              <label className="text-sm font-medium">Status</label>
              <Select value={createForm.status} onValueChange={(v) => setCreateForm((f) => ({ ...f, status: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="lead">Lead</SelectItem>
                  <SelectItem value="customer">Customer</SelectItem>
                  <SelectItem value="partner">Partner</SelectItem>
                  <SelectItem value="prospect">Prospect</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {createCustomer.isError && <p className="text-xs text-destructive">Failed to create customer</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button
              onClick={handleCreate}
              disabled={createCustomer.isPending || !createForm.name || !createForm.email}
            >
              {createCustomer.isPending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDelete} onOpenChange={(o) => !o && setShowDelete(false)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Customer</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <strong>{deletingCustomer?.name ?? ""}</strong>? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDelete(false)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteCustomer.isPending}
            >
              {deleteCustomer.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}