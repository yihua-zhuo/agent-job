"use client";
import { useCustomers } from "@/lib/api/queries";
import { useReactTable, getCoreRowModel, getPaginationRowModel } from "@tanstack/react-table";
import { ColumnDef } from "@tanstack/react-table";

interface CustomerRow {
  id: number;
  name: string;
  industry: string;
  status: string;
  lead_tier: string;
  last_activity: string;
  value: string;
}

const STATUS_COLORS: Record<string, string> = {
  lead: "bg-blue-100 text-blue-800",
  customer: "bg-green-100 text-green-800",
  partner: "bg-purple-100 text-purple-800",
  prospect: "bg-yellow-100 text-yellow-800",
  active: "bg-green-100 text-green-800",
  inactive: "bg-gray-100 text-gray-500",
  blocked: "bg-red-100 text-red-800",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
        STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {status || "—"}
    </span>
  );
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "numeric", day: "numeric", year: "numeric" });
}

const columns: ColumnDef<CustomerRow>[] = [
  {
    accessorKey: "name",
    header: "Name",
  },
  {
    accessorKey: "industry",
    header: "Industry",
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ getValue }) => <StatusBadge status={getValue<string>()} />,
  },
  {
    accessorKey: "lead_tier",
    header: "Lead Tier",
  },
  {
    accessorKey: "last_activity",
    header: "Last Activity",
    cell: ({ getValue }) => <span>{formatDate(getValue<string>())}</span>,
  },
  {
    accessorKey: "value",
    header: "Value",
  },
];

export default function CustomersTablePage() {
  const { data, isLoading, isError } = useCustomers(1, 20);

  const items: CustomerRow[] = (data?.data?.items ?? []).map((c) => ({
    id: Number(c.id),
    name: String(c.name ?? ""),
    industry: String(c.company ?? ""),
    status: String(c.status ?? ""),
    lead_tier: Array.isArray(c.tags) && c.tags.length > 0 ? String(c.tags[0]) : "unknown",
    last_activity: String(c.created_at ?? ""),
    value: String((c as Record<string, unknown>).value ?? "—"),
  }));

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  if (isLoading) {
    return <p className="p-6">Loading...</p>;
  }

  if (isError) {
    return <p className="p-6 text-destructive">Failed to load customers</p>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Customers</h1>
      <div className="rounded-md border overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/60">
            <tr className="border-b">
              {table.getHeaderGroups().map((headerGroup) =>
                headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    scope="col"
                    className="px-4 py-3 text-left text-xs uppercase tracking-wide text-muted-foreground font-semibold"
                  >
                    {header.isPlaceholder ? null : header.getContext().renderedValue}
                  </th>
                ))
              )}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                  No customers found
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b hover:bg-muted/40 transition-colors">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3">
                      {cell.getValue() as string}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}