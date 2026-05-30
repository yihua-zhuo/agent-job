"use client";

import { useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  ColumnDef,
  SortingState,
} from "@tanstack/react-table";

export interface UseTableStateOptions<TData> {
  data: TData[];
  columns: ColumnDef<TData, unknown>[];
  /** Column ids that the globalFilter applies to; all string columns if empty/undefined */
  searchableKeys?: string[];
}

export function useTableState<TData>({
  data,
  columns,
  searchableKeys = [],
}: UseTableStateOptions<TData>) {
  const [globalFilter, setGlobalFilter] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable<TData>({
    data,
    columns: columns as ColumnDef<TData, unknown>[],
    state: { globalFilter, sorting },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    globalFilterFn: "includesString",
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getCoreRowModel: getCoreRowModel(),
    getColumnCanGlobalFilter: (column) => {
      if (searchableKeys.length === 0) return true;
      return column.id != null && (searchableKeys as string[]).includes(column.id);
    },
  });

  return { table, globalFilter, setGlobalFilter, sorting };
}