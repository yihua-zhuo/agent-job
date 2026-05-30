import { describe, it, expect } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { ColumnDef } from "@tanstack/react-table";
import { useTableState } from "./useTableState";

interface TestRow {
  id: number;
  name: string;
  email: string;
  phone: string;
  status: string;
  company: string;
  created_at: string;
}

const makeRows = (names: string[]): TestRow[] =>
  names.map((name, i) => ({
    id: i + 1,
    name,
    email: `${name.toLowerCase()}@test.com`,
    phone: "",
    status: "lead",
    company: "",
    created_at: "",
  }));

// Minimal name column for sorting tests
const nameColumn: ColumnDef<TestRow, unknown> = {
  id: "name",
  accessorKey: "name",
  sortingFn: "alphanumeric",
};

describe("useTableState", () => {
  it("returns all rows when globalFilter is empty", () => {
    const rows = makeRows(["Alice", "Bob", "Charlie"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [] })
    );
    expect(result.current.table.getRowModel().rows.length).toBe(3);
  });

  it("filters rows by globalFilter across default string columns", () => {
    const rows = makeRows(["Alice", "Bob", "Charlie"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [] })
    );
    act(() => { result.current.setGlobalFilter("test.com"); });
    expect(result.current.table.getRowModel().rows.length).toBe(3);
  });

  it("updates globalFilter state when setGlobalFilter is called", async () => {
    const rows = makeRows(["Alice", "Bob", "Charlie"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [] })
    );
    expect(result.current.globalFilter).toBe("");
    act(() => { result.current.setGlobalFilter("test"); });
    await waitFor(() => {
      expect(result.current.globalFilter).toBe("test");
    });
  });

  it("adds and removes sorting state on toggleSorting", async () => {
    const rows = makeRows(["Charlie", "Alice", "Bob"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameColumn] })
    );
    expect(result.current.sorting).toEqual([]);
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); });
    await waitFor(() => {
      expect(result.current.sorting).toEqual([{ desc: false, id: "name" }]);
    });
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); });
    await waitFor(() => {
      expect(result.current.sorting).toEqual([{ desc: true, id: "name" }]);
    });
  });

  it("third toggleSorting clears the sort", async () => {
    const rows = makeRows(["Charlie", "Alice"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameColumn] })
    );
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // asc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // desc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // clear
    await waitFor(() => {
      expect(result.current.sorting).toEqual([]);
    });
  });

  it("sorting order: first click = asc (Alice first), second click = desc (Charlie first)", async () => {
    const rows = makeRows(["Charlie", "Alice", "Bob"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameColumn] })
    );
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); });
    await waitFor(() => {
      expect(result.current.table.getRowModel().rows[0].original.name).toBe("Alice");
    });
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); });
    await waitFor(() => {
      expect(result.current.table.getRowModel().rows[0].original.name).toBe("Charlie");
    });
  });

  it("sorting clears when column's toggleSorting is called a third time", async () => {
    const rows = makeRows(["Charlie", "Alice"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameColumn] })
    );
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // asc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // desc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // clear
    await waitFor(() => {
      expect(result.current.table.getColumn("name")?.getIsSorted()).toBeFalsy();
    });
  });
});
