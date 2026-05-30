import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { ColumnDef } from "@tanstack/react-table";
import { useTableState } from "./useTableState";

interface TestRow {
  id: number;
  name: string;
  email: string;
  phone?: string;
  status?: string;
  company?: string;
  created_at?: string;
  notes?: string;
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
    notes: "",
  }));

// Column defs covering name + email (used to scope globalFilter to specific columns)
const nameCol: ColumnDef<TestRow, string> = {
  id: "name",
  accessorKey: "name",
  sortingFn: "alphanumeric",
};

const emailCol: ColumnDef<TestRow, string> = {
  id: "email",
  accessorKey: "email",
};

describe("useTableState", () => {
  it("returns all rows when globalFilter is empty", () => {
    const rows = makeRows(["Alice", "Bob", "Charlie"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameCol, emailCol], searchableKeys: ["name", "email"] })
    );
    expect(result.current.globalFilter).toBe("");
    expect(result.current.table.getRowModel().rows.length).toBe(3);
  });

  it("filters rows by globalFilter across scoped columns", () => {
    const rows = makeRows(["Alice", "Bob", "Charlie"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameCol, emailCol], searchableKeys: ["name", "email"] })
    );
    act(() => { result.current.setGlobalFilter("alice"); });
    expect(result.current.table.getRowModel().rows.length).toBe(1);
    expect(result.current.table.getRowModel().rows[0].original.name).toBe("Alice");
  });

  it("returns empty rows when no match", () => {
    const rows = makeRows(["Alice", "Bob"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameCol, emailCol], searchableKeys: ["name", "email"] })
    );
    act(() => { result.current.setGlobalFilter("xyz"); });
    expect(result.current.table.getRowModel().rows.length).toBe(0);
  });

  it("does NOT match text in non-searchable columns", () => {
    // searchableKeys = ["name", "email"]; "notes" is NOT included
    const notesCol: ColumnDef<TestRow, string> = { id: "notes", accessorKey: "notes" };
    const rows: TestRow[] = [
      { id: 1, name: "Bob", email: "bob@test.com" },
      { id: 2, name: "Carol", email: "carol@test.com", notes: "alice is a contact" },
    ];
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameCol, emailCol, notesCol], searchableKeys: ["name", "email"] })
    );
    act(() => { result.current.setGlobalFilter("alice"); });
    // "alice" only exists in the notes column (not in name/email), so no rows match
    expect(result.current.table.getRowModel().rows.length).toBe(0);
  });

  it("updates globalFilter state when setGlobalFilter is called", () => {
    const rows = makeRows(["Alice", "Bob", "Charlie"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameCol, emailCol], searchableKeys: ["name", "email"] })
    );
    expect(result.current.globalFilter).toBe("");
    act(() => { result.current.setGlobalFilter("test"); });
    expect(result.current.globalFilter).toBe("test");
  });

  it("adds and removes sorting state on toggleSorting", () => {
    const rows = makeRows(["Charlie", "Alice", "Bob"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameCol] })
    );
    expect(result.current.sorting).toEqual([]);
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); });
    expect(result.current.sorting).toEqual([{ desc: false, id: "name" }]);
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); });
    expect(result.current.sorting).toEqual([{ desc: true, id: "name" }]);
  });

  it("third toggleSorting clears the sort", () => {
    const rows = makeRows(["Charlie", "Alice"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameCol] })
    );
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // asc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // desc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // clear
    expect(result.current.sorting).toEqual([]);
  });

  it("sorting order: first click = asc (Alice first), second click = desc (Charlie first)", () => {
    const rows = makeRows(["Charlie", "Alice", "Bob"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameCol] })
    );
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); });
    expect(result.current.table.getRowModel().rows[0].original.name).toBe("Alice");
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); });
    expect(result.current.table.getRowModel().rows[0].original.name).toBe("Charlie");
  });

  it("sorting clears when column's toggleSorting is called a third time", () => {
    const rows = makeRows(["Charlie", "Alice"]);
    const { result } = renderHook(() =>
      useTableState({ data: rows, columns: [nameCol] })
    );
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // asc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // desc
    act(() => { result.current.table.getColumn("name")?.toggleSorting(); }); // clear
    expect(result.current.table.getColumn("name")?.getIsSorted()).toBe(false);
  });
});
