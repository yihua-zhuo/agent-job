"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { useActivities } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, X, ChevronUp, ChevronDown, Phone, Mail, Users, FileText, Target } from "lucide-react";
import { cn } from "@/lib/utils";

const TYPE_COLORS: Record<string, string> = {
  call: "bg-blue-100 text-blue-800",
  email: "bg-green-100 text-green-800",
  meeting: "bg-purple-100 text-purple-800",
  note: "bg-gray-100 text-gray-600",
  demo: "bg-yellow-100 text-yellow-800",
};

const TYPE_ICONS: Record<string, React.ReactNode> = {
  call: <Phone className="h-4 w-4 text-blue-600" />,
  email: <Mail className="h-4 w-4 text-green-600" />,
  meeting: <Users className="h-4 w-4 text-purple-600" />,
  note: <FileText className="h-4 w-4 text-gray-600" />,
  demo: <Target className="h-4 w-4 text-yellow-600" />,
};

type SortKey = "type" | "content" | "created_at";
type SortDir = "asc" | "desc";

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "numeric", day: "numeric", year: "numeric" });
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function groupByDate(items: Record<string, unknown>[]) {
  const groups: Record<string, Record<string, unknown>[]> = {};
  for (const item of items) {
    const dateKey = formatDate(String(item.created_at));
    if (!groups[dateKey]) groups[dateKey] = [];
    groups[dateKey].push(item);
  }
  return Object.entries(groups);
}

export default function ActivitiesPage() {
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

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
    if (timerRef.current) clearTimeout(timerRef.current);
    setKeyword("");
    setDebouncedKeyword("");
    setPage(1);
  }, []);

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  const { data, isLoading, isError } = useActivities(
    page,
    typeFilter === "all" ? "" : typeFilter
  );

  const rawItems = data?.data?.items ?? [];
  const info = data?.data;

  const filtered = debouncedKeyword
    ? rawItems.filter((a) =>
        String(a.content ?? "").toLowerCase().includes(debouncedKeyword.toLowerCase())
      )
    : rawItems;

  const sorted = [...filtered].sort((a, b) => {
    if (!sortKey) {
      const da = new Date(String(a.created_at ?? 0)).getTime();
      const db = new Date(String(b.created_at ?? 0)).getTime();
      return db - da;
    }
    const av = a[sortKey] ?? "";
    const bv = b[sortKey] ?? "";
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortDir === "asc" ? cmp : -cmp;
  });

  const grouped = groupByDate(sorted);

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

  return (
    <div className="space-y-0">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-background pb-4 border-b border-border mb-0">
        <div className="flex items-baseline justify-between gap-4 mb-3">
          <h1 className="text-2xl font-bold">Activities</h1>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Select value={typeFilter} onValueChange={(v) => { setTypeFilter(v); setPage(1); }}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="All Types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="call">Call</SelectItem>
              <SelectItem value="email">Email</SelectItem>
              <SelectItem value="meeting">Meeting</SelectItem>
              <SelectItem value="note">Note</SelectItem>
              <SelectItem value="demo">Demo</SelectItem>
            </SelectContent>
          </Select>
          <div className="relative flex-1 min-w-48 max-w-sm">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              type="text"
              value={keyword}
              onChange={handleChange}
              placeholder="Search activities…"
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
      </div>

      {/* Timeline */}
      {isLoading && (
        <div className="space-y-3 mt-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3 rounded-md border p-3">
              <div className="h-8 w-8 bg-muted rounded animate-pulse flex-shrink-0" />
              <div className="flex-1 space-y-2 pt-1">
                <div className="flex gap-2">
                  <div className="h-5 w-16 bg-muted rounded animate-pulse" />
                  <div className="h-5 w-24 bg-muted rounded animate-pulse" />
                </div>
                <div className="h-4 bg-muted rounded w-3/4 animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      )}
      {isError && (
        <div className="py-12 text-center text-destructive">Failed to load activities</div>
      )}
      {!isLoading && !isError && grouped.length === 0 && (
        <div className="py-12 text-center">
          <div className="flex flex-col items-center gap-2">
            <Search className="h-8 w-8 text-muted-foreground/50" />
            <p className="font-medium text-muted-foreground">No activities found</p>
            {keyword && <p className="text-sm text-muted-foreground/70">No results for &ldquo;{keyword}&rdquo;</p>}
          </div>
        </div>
      )}

      {/* Chronological timeline grouped by date */}
      {!isLoading && !isError && grouped.map(([date, dayItems]) => (
        <div key={date} className="mt-6">
          {/* Date marker */}
          <div className="flex items-center gap-3 mb-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide px-2">
              {date}
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <div className="relative">
            {/* Vertical timeline line */}
            <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />

            <div className="space-y-3">
              {dayItems.map((a) => {
                const type = String(a.type ?? "");
                const icon = TYPE_ICONS[type] ?? <FileText className="h-4 w-4 text-gray-600" />;
                return (
                  <div
                    key={String(a.id)}
                    className="relative flex items-start gap-4 pl-10"
                  >
                    {/* Timeline dot */}
                    <div className="absolute left-2.5 top-1.5 flex h-3 w-3 items-center justify-center rounded-full border-2 border-background bg-primary z-10">
                      <div className="h-1.5 w-1.5 rounded-full bg-background" />
                    </div>

                    {/* Activity card */}
                    <div className="flex-1 rounded-md border bg-background p-3 hover:bg-muted/30 transition-colors">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="flex-shrink-0">{icon}</span>
                        <Badge colorClass={TYPE_COLORS[type] ?? "bg-gray-100 text-gray-600"}>
                          {type}
                        </Badge>
                        <span className="text-xs text-muted-foreground ml-auto">
                          {formatTime(String(a.created_at))}
                        </span>
                      </div>
                      <p className="text-sm text-foreground" title={String(a.content)}>
                        {String(a.content ?? "") || <span className="text-muted-foreground">—</span>}
                      </p>
                      {Boolean(a.customer_id) && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Customer #{String(a.customer_id)}
                        </p>
                      )}
                      {Boolean(a.duration_minutes) && (
                        <p className="text-xs text-muted-foreground">
                          {String(a.duration_minutes)} min
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ))}

      {info && !isError && (
        <div className="flex items-center justify-between text-xs text-muted-foreground py-3">
          <span>Showing {info.total === 0 ? 0 : ((page - 1) * 20) + 1}–{Math.min(page * 20, Number(info.total))} of {info.total}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</Button>
            <Button variant="outline" size="sm" disabled={!info.has_next} onClick={() => setPage(page + 1)}>Next →</Button>
          </div>
        </div>
      )}
    </div>
  );
}
