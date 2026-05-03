"use client";
import { useState, useRef, useCallback, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useCustomers, useCreateCustomer, useDeleteCustomer } from "@/lib/api/queries";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, X, ChevronUp, ChevronDown, MoreHorizontal, UserPlus, RefreshCw, Trash2, Download, Save, LayoutList } from "lucide-react";
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
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Settings2 } from "lucide-react";

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

interface SavedView {
  id: string;
  name: string;
  keyword: string;
  sortKey: SortKey | null;
  sortDir: "asc" | "desc";
  hiddenCols: string[];
}

const VIEWS_KEY = "crm_customers_views";

function loadViews(): SavedView[] {
  try { return JSON.parse(localStorage.getItem(VIEWS_KEY) ?? "[]"); }
  catch { return []; }
}

function saveViews(views: SavedView[]) {
  localStorage.setItem(VIEWS_KEY, JSON.stringify(views));
}

function useColumnResize(initialWidths: Record<string, number>) {
  const [widths, setWidths] = useState<Record<string, number>>(initialWidths);
  const [dragging, setDragging] = useState<string | null>(null);
  const startXRef = useRef<number>(0);
  const startWRef = useRef<number>(0);

  function onMouseDown(col: string, e: React.MouseEvent) {
    e.preventDefault();
    setDragging(col);
    startXRef.current = e.clientX;
    startWRef.current = widths[col] ?? 150;
  }

  useEffect(() => {
    if (!dragging) return;
    function onMove(e: MouseEvent) {
      setWidths((w) => ({ ...w, [dragging as string]: Math.max(60, startWRef.current + (e.clientX - startXRef.current)) }));
    }
    function onUp() { setDragging(null); }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging]);

  return { widths, onMouseDown, dragging };
}
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

function CopyCell({ value, type, style }: { value: string; type: "email" | "phone"; style?: React.CSSProperties }) {
  return (
    <div
      className="group/copy relative"
      title={`Double-click to copy ${type}`}
      onDoubleClick={() => {
        navigator.clipboard.writeText(value).then(() => toast.success(`${type} copied!`));
      }}
    >
      {value ? (
        <a
          href={type === "email" ? `mailto:${value}` : `tel:${value}`}
          className="text-sm text-muted-foreground hover:text-foreground underline-offset-2 hover:underline truncate block"
          title={value}
          onClick={(e) => e.stopPropagation()}
          style={style}
        >
          {value}
        </a>
      ) : (
        <span className="text-sm text-muted-foreground">—</span>
      )}
      <span className="absolute -top-4 left-0 text-[10px] text-muted-foreground opacity-0 group-hover/copy:opacity-100 transition-opacity pointer-events-none">
        Click to copy
      </span>
    </div>
  );
}

function CustomerRow({
  c,
  onNavigate,
  selected,
  onToggle,
  onDelete,
  widths,
  hiddenCols,
  onRowClick,
}: {
  c: CustomerRowData;
  onNavigate: (id: number) => void;
  selected: boolean;
  onToggle: (id: number) => void;
  onDelete: (c: CustomerRowData) => void;
  widths: Record<string, number>;
  hiddenCols: Set<string>;
  onRowClick?: () => void;
}) {
  return (
    <tr
      className={cn(
        "border-b hover:bg-muted/40 transition-colors group cursor-pointer",
        selected && "bg-primary/5"
      )}
      onClick={onRowClick}
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
      {!hiddenCols.has("name") && (
        <td scope="row" className="px-3 py-2.5" style={{ width: widths.name, minWidth: widths.name }}>
          <span className="font-medium truncate block" title={c.name || "—"}>
            {c.name || "—"}
          </span>
        </td>
      )}
      {!hiddenCols.has("email") && (
        <td scope="row" className="px-3 py-2.5" style={{ width: widths.email, minWidth: widths.email }}>
          <CopyCell value={c.email} type="email" />
        </td>
      )}
      {!hiddenCols.has("phone") && (
        <td scope="row" className="px-3 py-2.5" style={{ width: widths.phone, minWidth: widths.phone }}>
          <CopyCell value={c.phone} type="phone" />
        </td>
      )}
      {!hiddenCols.has("status") && (
        <td scope="row" className="px-3 py-2.5" style={{ width: widths.status, minWidth: widths.status }}>
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
              STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-600"
            )}
          >
            {c.status || "—"}
          </span>
        </td>
      )}
      {!hiddenCols.has("company") && (
        <td scope="row" className="px-3 py-2.5" style={{ width: widths.company, minWidth: widths.company }}>
          <span className="text-sm text-muted-foreground truncate block" title={c.company}>
            {c.company || "—"}
          </span>
        </td>
      )}
      {!hiddenCols.has("created_at") && (
        <td scope="row" className="px-3 py-2.5" style={{ width: widths.created_at, minWidth: widths.created_at }}>
          <span className="text-sm text-muted-foreground">{formatDate(c.created_at)}</span>
        </td>
      )}
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

interface CreateForm {
  name: string;
  email: string;
  phone: string;
  company: string;
  status: string;
}

const blankCreateForm: CreateForm = { name: "", email: "", phone: "", company: "", status: "lead" };

const SortIcon = ({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey | null; sortDir: SortDir }) => {
  if (sortKey !== col) {
    return <ChevronUp className="h-3 w-3 opacity-0 group-hover:opacity-40 transition-opacity inline ml-1" />;
  }
  return sortDir === "asc"
    ? <ChevronUp className="h-3 w-3 opacity-100 inline ml-1 text-primary" />
    : <ChevronDown className="h-3 w-3 opacity-100 inline ml-1 text-primary" />;
};

function CustomersPageInner() {
  const searchParams = useSearchParams();

  const initPage = Number(searchParams.get("page") ?? 1);
  const initPageSize = Number(searchParams.get("pageSize") ?? 20);
  const initKeyword = searchParams.get("q") ?? "";

  const [page, setPage] = useState(initPage);
  const [pageSize, setPageSize] = useState(initPageSize);
  const [keyword, setKeyword] = useState(initKeyword);
  const [debouncedKeyword, setDebouncedKeyword] = useState(initKeyword);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pageRef = useRef(page);
  pageRef.current = page;
  const debouncedKeywordRef = useRef(debouncedKeyword);
  debouncedKeywordRef.current = debouncedKeyword;

  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [hiddenCols, setHiddenCols] = useState<Set<string>>(new Set());

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(blankCreateForm);
  const createCustomer = useCreateCustomer();

  // Delete dialog
  const [deletingCustomer, setDeletingCustomer] = useState<CustomerRowData | null>(null);
  const [showDelete, setShowDelete] = useState(false);
  const deleteCustomer = useDeleteCustomer();

  // Bulk / column state
  const [showBulk, setShowBulk] = useState(false);

  function pushParams(overrides: Record<string, string | null>) {
    const params = new URLSearchParams();
    if (pageRef.current > 1) params.set("page", String(pageRef.current));
    if (pageSize !== 20) params.set("pageSize", String(pageSize));
    if (debouncedKeywordRef.current) params.set("q", debouncedKeywordRef.current);
    for (const [k, v] of Object.entries(overrides)) {
      if (v !== null) params.set(k, v);
    }
    const qs = params.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setKeyword(val);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedKeyword(val);
      setPage(1);
    }, 300);
  }, []);

  useEffect(() => {
    pushParams({ q: debouncedKeyword || null, page: page > 1 ? String(page) : null });
  }, [page, debouncedKeyword]);

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

  const { data, isLoading, isError, refetch, isFetching } = useCustomers(
    debouncedKeyword ? 1 : page,
    pageSize
  );


  // Auto-refresh every 30s
  useEffect(() => {
    if (!refetch) return;
    const interval = setInterval(() => { refetch(); }, 30_000);
    return () => clearInterval(interval);

  }, [refetch]);
  const { widths, onMouseDown, dragging } = useColumnResize({
    name: 160, email: 200, phone: 140, status: 120, company: 160, created_at: 120,
  });

  // Saved views
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [newViewName, setNewViewName] = useState("");

  useEffect(() => { setSavedViews(loadViews()); }, []);

  function applyView(view: SavedView) {
    setKeyword(view.keyword);
    setDebouncedKeyword(view.keyword);
    setSortKey(view.sortKey);
    setSortDir(view.sortDir);
    setHiddenCols(new Set(view.hiddenCols));
    setPage(1);
  }

  function deleteView(id: string) {
    const next = savedViews.filter((v) => v.id !== id);
    setSavedViews(next);
    saveViews(next);
  }

  function handleSaveView() {
    const v: SavedView = {
      id: crypto.randomUUID(),
      name: newViewName.trim() || "Untitled View",
      keyword: debouncedKeyword,
      sortKey,
      sortDir,
      hiddenCols: Array.from(hiddenCols),
    };
    const next = [...savedViews, v];
    setSavedViews(next);
    saveViews(next);
    setShowSaveDialog(false);
    setNewViewName("");
    toast.success(`View "${v.name}" saved`);
  }

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
    let av: string | number = a[sortKey];
    let bv: string | number = b[sortKey];
    if (sortKey === "created_at") {
      av = new Date(av as string).getTime();
      bv = new Date(bv as string).getTime();
    }
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
    pushParams({ pageSize: String(Number(v)), page: null });
  }

  const totalShown = info?.total ?? 0;
  const startShown = info?.total === 0 ? 0 : ((page - 1) * (info?.page_size ?? pageSize)) + 1;
  const endShown = Math.min(page * (info?.page_size ?? pageSize), info?.total ?? 0);

  return (
    <div className="space-y-0">
      {/* Saved views bar */}
      {savedViews.length > 0 && (
        <div className="flex items-center gap-2 mt-4 overflow-x-auto">
          <span className="text-xs text-muted-foreground flex-shrink-0">Views:</span>
          {savedViews.map((v) => (
            <div key={v.id} className="flex items-center flex-shrink-0 rounded-md border bg-muted px-2 py-1 text-xs group/view gap-1.5">
              <button type="button" onClick={() => applyView(v)} className="cursor-pointer hover:text-foreground">
                {v.name}
              </button>
              <button
                type="button"
                onClick={() => deleteView(v.id)}
                className="text-muted-foreground hover:text-destructive cursor-pointer"
                aria-label={`Delete view ${v.name}`}
              >
                ×
              </button>
            </div>
          ))}
          <Button variant="ghost" size="sm" className="flex-shrink-0 cursor-pointer text-xs" onClick={() => setShowSaveDialog(true)}>
            <Save className="h-3 w-3 mr-1" />
            Save current
          </Button>
        </div>
      )}

      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-background pb-4 border-b border-border mb-0">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <h1 className="text-2xl font-bold">Customers</h1>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetch?.()}
              className="cursor-pointer"
              title="Refresh"
              disabled={isFetching}
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
            </Button>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="sm" className="cursor-pointer" title="Customize columns">
                  <Settings2 className="h-4 w-4" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-44 p-2" align="end">
                <div className="text-xs font-semibold text-muted-foreground mb-1.5 px-1">Toggle columns</div>
                {(["name", "email", "phone", "company"] as const).map((col) => (
                  <label key={col} className="flex items-center gap-2 px-1 py-1 cursor-pointer hover:bg-muted rounded text-sm">
                    <input
                      type="checkbox"
                      checked={!hiddenCols.has(col)}
                      onChange={() => setHiddenCols((prev) => {
                        const next = new Set(prev);
                        if (next.has(col)) next.delete(col);
                        else next.add(col);
                        return next;
                      })}
                      className="accent-primary h-3.5 w-3.5 cursor-pointer"
                    />
                    {col.charAt(0).toUpperCase() + col.slice(1)}
                  </label>
                ))}
              </PopoverContent>
            </Popover>
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <UserPlus className="h-4 w-4 mr-1" />
              Add Customer
            </Button>
          </div>
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

      {/* Bulk actions toolbar */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-md border bg-muted px-4 py-2 text-sm mt-4">
          <span className="font-medium">{selectedIds.size} selected</span>
          <Button
            variant="outline"
            size="sm"
            className="cursor-pointer"
            onClick={() => setSelectedIds(new Set())}
          >
            Deselect all
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="cursor-pointer"
            onClick={() => {
              const rows = items.filter((c) => selectedIds.has(c.id));
              const csv = [
                ["name", "email", "phone", "company", "status"].join(","),
                ...rows.map((r) => [r.name, r.email, r.phone, r.company, r.status].map((v) => `"${v}"`).join(","))
              ].join("\n");
              const blob = new Blob([csv], { type: "text/csv" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a"); a.href = url; a.download = "customers.csv"; a.click();
              URL.revokeObjectURL(url);
              toast.success(`Exported ${rows.length} customers`);
            }}
          >
            <Download className="h-3.5 w-3.5 mr-1" />
            Export CSV
          </Button>
          <Button
            variant="destructive"
            size="sm"
            className="cursor-pointer"
            onClick={() => setBulkDeleteOpen(true)}
          >
            <Trash2 className="h-3.5 w-3.5 mr-1" />
            Delete
          </Button>
        </div>
      )}

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
              {!hiddenCols.has("name") && (
                <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold select-none group relative" style={{ width: widths.name, minWidth: widths.name }}>
                  <div className="flex items-center cursor-pointer" onClick={() => handleSort("name")}>
                    Name<SortIcon col="name" sortKey={sortKey} sortDir={sortDir} />
                  </div>
                  <div
                    className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary/50 active:bg-primary"
                    onMouseDown={(e) => onMouseDown("name", e)}
                  />
                </th>
              )}
              {!hiddenCols.has("email") && (
                <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold select-none group relative" style={{ width: widths.email, minWidth: widths.email }}>
                  <div className="flex items-center cursor-pointer" onClick={() => handleSort("email")}>
                    Email<SortIcon col="email" sortKey={sortKey} sortDir={sortDir} />
                  </div>
                  <div
                    className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary/50 active:bg-primary"
                    onMouseDown={(e) => onMouseDown("email", e)}
                  />
                </th>
              )}
              {!hiddenCols.has("phone") && (
                <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold select-none group relative" style={{ width: widths.phone, minWidth: widths.phone }}>
                  <div className="flex items-center cursor-pointer" onClick={() => handleSort("phone")}>
                    Phone<SortIcon col="phone" sortKey={sortKey} sortDir={sortDir} />
                  </div>
                  <div
                    className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary/50 active:bg-primary"
                    onMouseDown={(e) => onMouseDown("phone", e)}
                  />
                </th>
              )}
              {!hiddenCols.has("status") && (
                <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold select-none group relative" style={{ width: widths.status, minWidth: widths.status }}>
                  <div className="flex items-center cursor-pointer" onClick={() => handleSort("status")}>
                    Status<SortIcon col="status" sortKey={sortKey} sortDir={sortDir} />
                  </div>
                  <div
                    className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary/50 active:bg-primary"
                    onMouseDown={(e) => onMouseDown("status", e)}
                  />
                </th>
              )}
              {!hiddenCols.has("company") && (
                <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold select-none group relative" style={{ width: widths.company, minWidth: widths.company }}>
                  <div className="flex items-center cursor-pointer" onClick={() => handleSort("company")}>
                    Company<SortIcon col="company" sortKey={sortKey} sortDir={sortDir} />
                  </div>
                  <div
                    className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary/50 active:bg-primary"
                    onMouseDown={(e) => onMouseDown("company", e)}
                  />
                </th>
              )}
              {!hiddenCols.has("created_at") && (
                <th scope="col" className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold select-none group relative" style={{ width: widths.created_at, minWidth: widths.created_at }}>
                  <div className="flex items-center cursor-pointer" onClick={() => handleSort("created_at")}>
                    Created<SortIcon col="created_at" sortKey={sortKey} sortDir={sortDir} />
                  </div>
                  <div
                    className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-primary/50 active:bg-primary"
                    onMouseDown={(e) => onMouseDown("created_at", e)}
                  />
                </th>
              )}
              <th scope="col" className="px-3 py-2.5 w-10" />
            </tr>
          </thead>
          <tbody>
            {isLoading && Array.from({ length: 6 }).map((_, i) => (
              <tr key={i} className="border-b">
                <td scope="row" className="px-3 py-2.5"><div className="h-4 w-4 bg-muted rounded animate-pulse" /></td>
                {!hiddenCols.has("name") && <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded animate-pulse" style={{ width: widths.name - 24 }} /></td>}
                {!hiddenCols.has("email") && <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded animate-pulse" style={{ width: widths.email - 24 }} /></td>}
                {!hiddenCols.has("phone") && <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded animate-pulse" style={{ width: widths.phone - 24 }} /></td>}
                {!hiddenCols.has("status") && <td scope="row" className="px-3 py-2.5"><div className="h-5 bg-muted rounded animate-pulse" style={{ width: 60 }} /></td>}
                {!hiddenCols.has("company") && <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded animate-pulse" style={{ width: widths.company - 24 }} /></td>}
                {!hiddenCols.has("created_at") && <td scope="row" className="px-3 py-2.5"><div className="h-4 bg-muted rounded animate-pulse" style={{ width: widths.created_at - 24 }} /></td>}
                <td scope="row" className="px-3 py-2.5" />
              </tr>
            ))}
            {isError && (
              <tr>
                <td colSpan={hiddenCols.size === 0 ? 8 : 8} className="px-3 py-10 text-center text-destructive">Failed to load customers</td>
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
              <CustomerRow
                key={c.id}
                c={c}
                onNavigate={navigateToCustomer}
                selected={selectedIds.has(c.id)}
                onToggle={toggleSelect}
                onDelete={openDelete}
                widths={widths}
                hiddenCols={hiddenCols}
                onRowClick={() => navigateToCustomer(c.id)}
              />
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

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog open={bulkDeleteOpen} onOpenChange={(o) => !o && setBulkDeleteOpen(false)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete {selectedIds.size} Customers</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete {selectedIds.size} selected customer{selectedIds.size > 1 ? "s" : ""}? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkDeleteOpen(false)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={async () => {
                const ids = Array.from(selectedIds);
                const results = await Promise.allSettled(ids.map((id) => deleteCustomer.mutateAsync(id)));
                const failed = results.filter((r) => r.status === "rejected").length;
                const succeeded = results.filter((r) => r.status === "fulfilled").length;
                if (failed === 0) toast.success(`${succeeded} customers deleted`);
                else toast.error(`${succeeded} deleted, ${failed} failed`);
                setSelectedIds(new Set());
                setBulkDeleteOpen(false);
              }}
            >
              Delete {selectedIds.size} Customers
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Save View Dialog */}
      <Dialog open={showSaveDialog} onOpenChange={(o) => !o && setShowSaveDialog(false)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Save View</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">View name</label>
              <Input
                value={newViewName}
                onChange={(e) => setNewViewName(e.target.value)}
                placeholder="e.g. My leads"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Saves current search, sort, and column visibility settings.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveDialog(false)}>Cancel</Button>
            <Button onClick={handleSaveView}>Save View</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function CustomersPage() {
  return (
    <Suspense>
      <CustomersPageInner />
    </Suspense>
  );
}