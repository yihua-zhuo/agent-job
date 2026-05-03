"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { useCustomers, useSearchCustomers } from "@/lib/api/queries";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, X, ChevronUp, ChevronDown, MoreHorizontal } from "lucide-react";
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
}: {
  c: CustomerRowData;
  onNavigate: (id: number) => void;
  selected: boolean;
  onToggle: (id: number) => void;
}) {
  const phone = c.phone;
  const formattedPhone = phone
    ? phone.replace(/^\+1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/, (m) => m)
    : "";

  return (
    <tr
      className={cn(
        "border-b hover:bg-muted/40 transition-colors",
        selected && "bg-primary/5"
      )}
    >
      {/* Bulk select checkbox */}
      <td className="px-3 py-2.5 w-10">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggle(c.id)}
          className="accent-primary h-4 w-4 cursor-pointer"
          onClick={(e) => e.stopPropagation()}
        />
      </td>
      {/* Name */}
      <td className="px-3 py-2.5">
        <span
          className="font-medium truncate block max-w-[160px]"
          title={c.name}
        >
          {c.name || "—"}
        </span>
      </td>
      {/* Email */}
      <td className="px-3 py-2.5">
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
      {/* Phone */}
      <td className="px-3 py-2.5">
        {phone ? (
          <a
            href={`tel:${phone}`}
            className="text-sm font-mono text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {phone}
          </a>
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        )}
      </td>
      {/* Status */}
      <td className="px-3 py-2.5">
        <Badge colorClass={STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-600"}>
          {c.status || "—"}
        </Badge>
      </td>
      {/* Company */}
      <td className="px-3 py-2.5">
        <span className="text-sm text-muted-foreground truncate block max-w-[140px]" title={c.company}>
          {c.company || "—"}
        </span>
      </td>
      {/* Created */}
      <td className="px-3 py-2.5">
        <span className="text-sm text-muted-foreground">{formatDate(c.created_at)}</span>
      </td>
      {/* Actions */}
      <td className="px-3 py-2.5 w-10" onClick={(e) => e.stopPropagation()}>
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
            <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </td>
    </tr>
  );
}

function useCustomersData(page: number, keyword: string) {
  const search = useSearchCustomers(keyword);
  const list = useCustomers(page);
  return keyword ? search : list;
}

export default function CustomersPage() {
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

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

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  const { data, isLoading, isError } = useCustomersData(
    debouncedKeyword ? 1 : page,
    debouncedKeyword
  );

  const rawItems = data?.data?.items ?? [];
  const info = data?.data;

  // Normalize items
  const items: CustomerRowData[] = rawItems.map((c) => ({
    id: Number(c.id),
    name: String(c.name ?? ""),
    email: String(c.email ?? ""),
    phone: String(c.phone ?? ""),
    status: String(c.status ?? ""),
    company: String(c.company ?? ""),
    created_at: String(c.created_at ?? ""),
  }));

  // Sort
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

  const totalShown = info?.total ?? 0;
  const startShown = info?.total === 0 ? 0 : ((page - 1) * (info?.page_size ?? 20)) + 1;
  const endShown = Math.min(page * (info?.page_size ?? 20), info?.total ?? 0);

  return (
    <div className="space-y-0">
      {/* Sticky header: page title + search */}
      <div className="sticky top-0 z-10 bg-background pb-4 border-b border-border mb-0">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <h1 className="text-2xl font-bold">Customers</h1>
        </div>
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            type="text"
            value={keyword}
            onChange={handleChange}
            placeholder="Search customers…"
            className="pl-8 pr-8 rounded-lg border-[1px] shadow-sm focus:ring-2 focus:ring-primary focus:ring-offset-1"
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
              <th className="px-3 py-2.5 w-10">
                <input
                  type="checkbox"
                  className="accent-primary h-4 w-4 cursor-pointer"
                  onChange={(e) => {
                    if (e.target.checked) setSelectedIds(new Set(items.map((c) => c.id)));
                    else setSelectedIds(new Set());
                  }}
                  checked={items.length > 0 && selectedIds.size === items.length}
                />
              </th>
              <th
                className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                onClick={() => handleSort("name")}
              >
                Name<SortIcon col="name" />
              </th>
              <th
                className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                onClick={() => handleSort("email")}
              >
                Email<SortIcon col="email" />
              </th>
              <th
                className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                onClick={() => handleSort("phone")}
              >
                Phone<SortIcon col="phone" />
              </th>
              <th
                className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                onClick={() => handleSort("status")}
              >
                Status<SortIcon col="status" />
              </th>
              <th
                className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                onClick={() => handleSort("company")}
              >
                Company<SortIcon col="company" />
              </th>
              <th
                className="px-3 py-2.5 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold cursor-pointer hover:text-foreground group select-none"
                onClick={() => handleSort("created_at")}
              >
                Created<SortIcon col="created_at" />
              </th>
              <th className="px-3 py-2.5 w-10" />
            </tr>
          </thead>
          <tbody>
            {isLoading && Array.from({ length: 6 }).map((_, i) => (
              <tr key={i} className="border-b">
                <td className="px-3 py-2.5"><div className="h-4 w-4 bg-muted rounded animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-32 animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-40 animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-28 animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-5 bg-muted rounded w-16 animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-24 animate-pulse" /></td>
                <td className="px-3 py-2.5"><div className="h-4 bg-muted rounded w-20 animate-pulse" /></td>
                <td className="px-3 py-2.5" />
              </tr>
            ))}
            {isError && (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-destructive">
                  Failed to load customers
                </td>
              </tr>
            )}
            {!isLoading && !isError && sorted.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-12 text-center">
                  <div className="flex flex-col items-center gap-2">
                    <Search className="h-8 w-8 text-muted-foreground/50" />
                    <p className="font-medium text-muted-foreground">No customers found</p>
                    {keyword && (
                      <p className="text-sm text-muted-foreground/70">
                        No results for &ldquo;{keyword}&rdquo;
                      </p>
                    )}
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
                />
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {info && !isError && (
        <div className="flex items-center justify-between text-xs text-muted-foreground py-3">
          <span>
            {selectedIds.size > 0
              ? `${selectedIds.size} selected`
              : `Showing ${startShown}–${endShown} of ${totalShown}`}
          </span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</Button>
            <Button variant="outline" size="sm" disabled={!info.has_next} onClick={() => setPage(page + 1)}>Next →</Button>
          </div>
        </div>
      )}
    </div>
  );
}