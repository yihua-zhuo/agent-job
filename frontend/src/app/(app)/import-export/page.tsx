"use client";
import { useState, useRef } from "react";
import { useCreateCustomer } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ImportExportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string[][]>([]);
  const [result, setResult] = useState<{ imported: number; errors: string[] } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const create = useCreateCustomer();

  function parseCSV(text: string): string[][] {
    const lines = text.trim().split("\n");
    return lines.map((line) => {
      const cells: string[] = [];
      let current = "";
      let inQuotes = false;
      for (const ch of line) {
        if (ch === '"') { inQuotes = !inQuotes; }
        else if (ch === "," && !inQuotes) { cells.push(current.trim()); current = ""; }
        else { current += ch; }
      }
      cells.push(current.trim());
      return cells;
    });
  }

  function handleFile(f: File) {
    setFile(f);
    setResult(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const rows = parseCSV(text);
      setPreview(rows.slice(0, 6));
    };
    reader.readAsText(f);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && (f.name.endsWith(".csv") || f.name.endsWith(".txt"))) handleFile(f);
  }

  async function handleImport() {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (e) => {
      const text = e.target?.result as string;
      const rows = parseCSV(text);
      const headers = rows[0].map((h) => h.toLowerCase().trim());
      const dataRows = rows.slice(1);

      const errors: string[] = [];
      let imported = 0;

      for (let i = 0; i < dataRows.length; i++) {
        const row = dataRows[i];
        const record: Record<string, string> = {};
        headers.forEach((h, idx) => { record[h] = row[idx] ?? ""; });
        try {
          await create.mutateAsync({
            name: record.name || record.company || "Unnamed",
            email: record.email || undefined,
            phone: record.phone || undefined,
            company: record.company || record.name || undefined,
            status: record.status || "lead",
          });
          imported++;
        } catch (err) {
          errors.push(`Row ${i + 2}: ${err instanceof Error ? err.message : "Unknown error"}`);
        }
      }
      setResult({ imported, errors });
    };
    reader.readAsText(file);
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold">Import / Export</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">CSV Import</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Import customers from a CSV file. Required column: <code className="bg-muted px-1 rounded">name</code> or <code className="bg-muted px-1 rounded">company</code>.
            Optional: <code className="bg-muted px-1 rounded">email</code>, <code className="bg-muted px-1 rounded">phone</code>, <code className="bg-muted px-1 rounded">status</code>.
          </p>

          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/30"}`}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
          >
            {file ? (
              <div className="space-y-2">
                <div className="text-sm font-medium">{file.name}</div>
                <div className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</div>
                <Button variant="outline" size="sm" onClick={() => { setFile(null); setPreview([]); }}>Remove</Button>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="text-muted-foreground">Drag & drop a CSV file here, or</div>
                <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>Browse Files</Button>
                <input ref={fileRef} type="file" accept=".csv,.txt" className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
              </div>
            )}
          </div>

          {preview.length > 0 && (
            <div className="space-y-2">
              <div className="text-sm font-medium">Preview (first {preview.length} rows)</div>
              <div className="overflow-x-auto rounded-md border">
                <table className="text-xs">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      {preview[0].map((h, i) => <th key={i} className="px-2 py-1.5 text-left font-semibold whitespace-nowrap">{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.slice(1).map((row, ri) => (
                      <tr key={ri} className="border-b">
                        {row.map((cell, ci) => <td key={ci} className="px-2 py-1 whitespace-nowrap">{cell}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <Button onClick={handleImport} disabled={!file || create.isPending}>
            {create.isPending ? "Importing…" : "Import Customers"}
          </Button>

          {result && (
            <div className={`rounded-md p-4 text-sm ${result.errors.length > 0 ? "bg-yellow-50 border border-yellow-300" : "bg-green-50 border border-green-300"}`}>
              <div className="font-medium">{result.imported} records imported successfully</div>
              {result.errors.length > 0 && (
                <div className="mt-2 space-y-1">
                  <div className="font-medium text-yellow-800">Errors ({result.errors.length}):</div>
                  {result.errors.slice(0, 5).map((e, i) => <div key={i} className="text-xs text-yellow-700">{e}</div>)}
                  {result.errors.length > 5 && <div className="text-xs text-yellow-700">…and {result.errors.length - 5} more</div>}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Export</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Export customer data to CSV. Select the fields you want to include.
          </p>
          <div className="flex flex-wrap gap-2">
            {["name", "email", "phone", "company", "status", "created_at"].map((field) => (
              <label key={field} className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" defaultChecked className="accent-primary" />
                {field}
              </label>
            ))}
          </div>
          <Button variant="outline" disabled>Export (coming soon)</Button>
        </CardContent>
      </Card>
    </div>
  );
}
