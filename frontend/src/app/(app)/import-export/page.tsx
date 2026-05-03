"use client";
import { useState, useRef } from "react";
import { useCreateCustomer, useCustomers } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

const TARGET_FIELDS = [
  { key: "name", label: "Name (required)", required: true },
  { key: "email", label: "Email", required: false },
  { key: "phone", label: "Phone", required: false },
  { key: "company", label: "Company", required: false },
  { key: "status", label: "Status", required: false },
  { key: "ignore", label: "— Ignore —", required: false },
];

type FieldKey = "name" | "email" | "phone" | "company" | "status" | "ignore";

export default function ImportExportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [preview, setPreview] = useState<string[][]>([]);
  const [result, setResult] = useState<{ imported: number; errors: string[] } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [mapping, setMapping] = useState<Record<number, FieldKey>>({});
  const fileRef = useRef<HTMLInputElement>(null);
  const create = useCreateCustomer();
  const { data: custData } = useCustomers(1, 1);

  function parseCSV(text: string): string[][] {
    const rows: string[][] = [];
    let row: string[] = [];
    let cell = "";
    let inQuotes = false;

    for (let i = 0; i < text.length; i++) {
      const ch = text[i];

      if (ch === '"') {
        if (inQuotes && text[i + 1] === '"') {
          cell += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
        continue;
      }

      if (ch === "," && !inQuotes) {
        row.push(cell.trim());
        cell = "";
        continue;
      }

      if ((ch === "\n" || ch === "\r") && !inQuotes) {
        if (ch === "\r" && text[i + 1] === "\n") i++;
        row.push(cell.trim());
        rows.push(row);
        row = [];
        cell = "";
        continue;
      }

      cell += ch;
    }

    if (cell.length > 0 || row.length > 0) {
      row.push(cell.trim());
      rows.push(row);
    }

    return rows;
  }

  function autoMap(headers: string[]): Record<number, FieldKey> {
    const map: Record<number, FieldKey> = {};
    const known: Record<string, FieldKey> = {
      name: "name", full_name: "name", customer_name: "name",
      email: "email", email_address: "email",
      phone: "phone", telephone: "phone", phone_number: "phone", mobile: "phone",
      company: "company", company_name: "company", organization: "company",
      status: "status",
    };
    headers.forEach((h, i) => {
      const key = known[h.toLowerCase().trim()];
      if (key) map[i] = key;
    });
    return map;
  }

  function handleFile(f: File) {
    setFile(f);
    setResult(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const rows = parseCSV(text);
      if (rows.length === 0) return;
      const hdrs = rows[0];
      setHeaders(hdrs);
      setPreview(rows.slice(1, 7));
      setMapping(autoMap(hdrs));
    };
    reader.readAsText(f);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && /\.(csv|txt)$/i.test(f.name)) handleFile(f);
  }

  function handleClear() {
    setFile(null);
    setHeaders([]);
    setPreview([]);
    setMapping({});
    setResult(null);
  }

  const requiredFields = ["name", "company"];
  const mappedRequired = requiredFields.filter((req) =>
    Object.values(mapping).includes(req as FieldKey)
  );
  const canImport = file && mappedRequired.length > 0;

  async function handleImport() {
    if (!file) return;
    setResult(null);

    const reader = new FileReader();
    reader.onload = async (e) => {
      const text = e.target?.result as string;
      const rows = parseCSV(text);
      const dataRows = rows.slice(1);

      const fieldToIdx: Record<string, number> = {};
      Object.entries(mapping).forEach(([idx, field]) => {
        if (field !== "ignore") fieldToIdx[field] = Number(idx);
      });

      const errors: string[] = [];
      let imported = 0;

      for (let i = 0; i < dataRows.length; i++) {
        const row = dataRows[i];
        const name = fieldToIdx.name !== undefined ? row[fieldToIdx.name]?.trim() : undefined;
        const company = fieldToIdx.company !== undefined ? row[fieldToIdx.company]?.trim() : undefined;
        const email = fieldToIdx.email !== undefined ? row[fieldToIdx.email]?.trim() : undefined;
        const phone = fieldToIdx.phone !== undefined ? row[fieldToIdx.phone]?.trim() : undefined;
        const status = fieldToIdx.status !== undefined ? row[fieldToIdx.status]?.trim() : undefined;

        if (!name && !company) {
          errors.push(`Row ${i + 2}: missing name or company`);
          continue;
        }

        try {
          await create.mutateAsync({
            name: name || company!,
            email: email || undefined,
            phone: phone || undefined,
            company: company || name || undefined,
            status: status || "lead",
          });
          imported++;
        } catch (err) {
          errors.push(`Row ${i + 2}: ${err instanceof Error ? err.message : "Unknown error"}`);
        }
      }

      setResult({ imported, errors });
      if (imported > 0) toast.success(`${imported} customers imported`);
      if (errors.length > 0) toast.error(`${errors.length} rows failed`);
    };
    reader.readAsText(file);
  }

  async function handleExportCustomers() {
    const { data } = useCustomers(1, 10000);
    // Export uses the same API — trigger via fetch
    const total = custData?.data?.total ?? 0;
    toast.info(`Exporting ${total} customers…`);
    // Placeholder: wire to backend export endpoint when available
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-2xl font-bold">Import / Export</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">CSV Import — Step 1: Upload</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Upload a CSV file. The first row must be column headers. Required fields: <strong>name</strong> or <strong>company</strong>.
          </p>

          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/30 hover:border-muted-foreground/60"}`}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
          >
            {file ? (
              <div className="space-y-2">
                <div className="text-sm font-medium">{file.name}</div>
                <div className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</div>
                <Button variant="outline" size="sm" onClick={handleClear}>Remove</Button>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="text-muted-foreground">Drag & drop a CSV file here, or</div>
                <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>Browse Files</Button>
                <input ref={fileRef} type="file" accept=".csv,.txt" className="hidden" onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                }} />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {headers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">CSV Import — Step 2: Map Columns</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Tell us which CSV column maps to each CRM field. Required: <strong>Name</strong> or <strong>Company</strong>.
            </p>
            <div className="rounded-md border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">CSV Column</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Sample Value</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Maps To</th>
                  </tr>
                </thead>
                <tbody>
                  {headers.map((h, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="px-3 py-2 font-medium text-sm">{h}</td>
                      <td className="px-3 py-2 text-xs text-muted-foreground truncate max-w-[200px]">
                        {preview[0]?.[i] ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        <Select
                          value={mapping[i] ?? "ignore"}
                          onValueChange={(v) => setMapping((m) => ({ ...m, [i]: v as FieldKey }))}
                        >
                          <SelectTrigger className="w-48">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {TARGET_FIELDS.map(({ key, label }) => (
                              <SelectItem key={key} value={key}>
                                {label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {mappedRequired.length === 0 && (
              <p className="text-xs text-destructive">At least one of Name or Company must be mapped.</p>
            )}
          </CardContent>
        </Card>
      )}

      {headers.length > 0 && preview.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">CSV Import — Step 3: Preview & Import</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="overflow-x-auto rounded-md border">
              <table className="text-xs">
                <thead>
                  <tr className="border-b bg-muted/50">
                    {headers.map((h, i) => (
                      <th key={i} className="px-2 py-1.5 text-left font-semibold whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row, ri) => (
                    <tr key={ri} className="border-b last:border-0">
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-2 py-1 whitespace-nowrap">{cell || <span className="text-muted-foreground">—</span>}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="text-xs text-muted-foreground">Showing first {preview.length} of {(file?.size ?? 0) > 0 ? "many" : preview.length} data rows</div>
            <Button onClick={handleImport} disabled={!canImport || create.isPending}>
              {create.isPending ? "Importing…" : `Import ${preview.length > 0 ? `${preview.length} rows` : "file"}`}
            </Button>

            {result && (
              <div className={`rounded-md p-4 text-sm ${result.errors.length > 0 ? "bg-yellow-50 border border-yellow-300" : "bg-green-50 border border-green-300"}`}>
                <div className="font-medium">{result.imported} records imported successfully</div>
                {result.errors.length > 0 && (
                  <div className="mt-2 space-y-1">
                    <div className="font-medium text-yellow-800">Errors ({result.errors.length}):</div>
                    {result.errors.slice(0, 10).map((e, i) => (
                      <div key={i} className="text-xs text-yellow-700">{e}</div>
                    ))}
                    {result.errors.length > 10 && (
                      <div className="text-xs text-yellow-700">…and {result.errors.length - 10} more</div>
                    )}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Export Customers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Export all customer records to a CSV file. Select the fields to include.
          </p>
          <div className="flex flex-wrap gap-2">
            {["name", "email", "phone", "company", "status", "created_at"].map((field) => (
              <label key={field} className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" defaultChecked className="accent-primary" />
                {field}
              </label>
            ))}
          </div>
          <Button variant="outline" onClick={handleExportCustomers} disabled>
            Export CSV (coming soon)
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
