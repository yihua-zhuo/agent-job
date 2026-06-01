"use client";

import { useState, useCallback } from "react";
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

/**
 * Manages global filter and sorting state for a TanStack Table instance.
 *
 * @param data - The row data to display in the table.
 * @param columns - TanStack column definitions.
 * @param searchableKeys - Optional list of column ids to restrict global filtering to.
 *                         When empty, all columns are included in the filter.
 * @returns A table instance and state setters.
 */
export function useTableState<TData>({
  data,
  columns,
  searchableKeys = [],
}: UseTableStateOptions<TData>) {
  const [globalFilter, setGlobalFilter] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);

  const getColumnCanGlobalFilter = useCallback(
    (column: { id: string | null }) => {
      if (searchableKeys.length === 0) return true;
      return column.id !== null && searchableKeys.includes(column.id);
    },
    [searchableKeys]
  );

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
    getColumnCanGlobalFilter,
  });

  return { table, globalFilter, setGlobalFilter, sorting, setSorting };
}
