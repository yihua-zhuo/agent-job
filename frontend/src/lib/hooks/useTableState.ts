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
  /**
   * Restricts global filtering to the given column ids.
   * When empty (the default), all columns are included in filtering.
   */
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
    columns,
    state: { globalFilter, sorting },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    globalFilterFn: "includesString",
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getCoreRowModel: getCoreRowModel(),
    getColumnCanGlobalFilter: (column) => {
      if (searchableKeys.length === 0) return true;
      return searchableKeys.includes(column.id);
    },
  });

  return { table, globalFilter, setGlobalFilter, sorting };
}