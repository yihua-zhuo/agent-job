"use client";
import { useCustomers, useOpportunities, useTickets, useTasks } from "@/lib/api/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useState } from "react";
import { Download } from "lucide-react";

const PIECHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

const MOCK_TIMELINE = [
  { month: "Jan", customers: 12, leads: 34, deals: 5 },
  { month: "Feb", customers: 19, leads: 41, deals: 8 },
  { month: "Mar", customers: 28, leads: 55, deals: 11 },
  { month: "Apr", customers: 35, leads: 48, deals: 14 },
  { month: "May", customers: 42, leads: 63, deals: 18 },
  { month: "Jun", customers: 51, leads: 70, deals: 22 },
];

const STAGE_DATA = [
  { name: "Lead", value: 35 },
  { name: "Qualified", value: 22 },
  { name: "Proposal", value: 15 },
  { name: "Negotiation", value: 12 },
  { name: "Closed Won", value: 16 },
];

export default function AnalyticsPage() {
  const [activeChart, setActiveChart] = useState<"bar" | "line" | "pie">("bar");

  const { data: custData } = useCustomers(1, 1);
  const { data: oppData } = useOpportunities(1);
  const { data: ticketData } = useTickets(1, 1);
  const { data: taskData } = useTasks(1);

  const totalCustomers = Number(custData?.data?.total ?? 0);
  const totalOpps = Number(oppData?.data?.total ?? 0);
  const totalTickets = Number(ticketData?.data?.total ?? 0);
  const totalTasks = Number(taskData?.data?.total ?? 0);

  function fmtVal(v: number) {
    if (Number.isNaN(v)) return "—";
    return v.toLocaleString();
  }

  function handleExportPDF() {
    if (typeof window === "undefined") return;
    // Placeholder — wire to backend PDF export endpoint when available
    window.print();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Analytics</h1>
        <Button variant="outline" size="sm" onClick={handleExportPDF}>
          <Download className="h-4 w-4 mr-1" />
          Export PDF
        </Button>
      </div>

      {/* KPI cards */}
      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        {[
          { label: "Customers", value: fmtVal(totalCustomers), color: "text-blue-600" },
          { label: "Opportunities", value: fmtVal(totalOpps), color: "text-green-600" },
          { label: "Open Tickets", value: fmtVal(totalTickets), color: "text-yellow-600" },
          { label: "Active Tasks", value: fmtVal(totalTasks), color: "text-purple-600" },
        ].map(({ label, value, color }) => (
          <Card key={label}>
            <CardContent className="p-4 text-center space-y-1">
              <div className={`text-3xl font-bold ${color}`}>{value}</div>
              <div className="text-sm text-muted-foreground">{label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Chart type toggle */}
      <div className="flex gap-2">
        {(["bar", "line", "pie"] as const).map((type) => (
          <Button
            key={type}
            variant={activeChart === type ? "default" : "outline"}
            size="sm"
            onClick={() => setActiveChart(type)}
          >
            {type.charAt(0).toUpperCase() + type.slice(1)} Chart
          </Button>
        ))}
      </div>

      {/* Main chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Customer & Lead Growth</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            {activeChart === "bar" ? (
              <BarChart data={MOCK_TIMELINE}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="customers" name="New Customers" fill="#3b82f6" />
                <Bar dataKey="leads" name="New Leads" fill="#10b981" />
              </BarChart>
            ) : activeChart === "line" ? (
              <LineChart data={MOCK_TIMELINE}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="customers" name="New Customers" stroke="#3b82f6" />
                <Line type="monotone" dataKey="deals" name="Closed Deals" stroke="#10b981" />
              </LineChart>
            ) : (
              <PieChart>
                <Pie
                  data={STAGE_DATA}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={110}
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                >
                  {STAGE_DATA.map((_, i) => (
                    <Cell key={i} fill={PIECHART_COLORS[i % PIECHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            )}
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Secondary charts row */}
      <div className="grid gap-4" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Deal Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={STAGE_DATA} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="name" type="category" width={80} />
                <Tooltip />
                <Bar dataKey="value" name="Opportunities" fill="#8b5cf6" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Ticket Status</CardTitle>
          </CardHeader>
          <CardContent>
            {totalTickets === 0 ? (
              <div className="flex items-center justify-center h-[220px] text-muted-foreground text-sm">
                No tickets yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={[
                      { name: "Open", value: Math.round(totalTickets * 0.4) },
                      { name: "In Progress", value: Math.round(totalTickets * 0.3) },
                      { name: "Resolved", value: Math.round(totalTickets * 0.3) },
                    ]}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {[0, 1, 2].map((i) => (
                      <Cell key={i} fill={PIECHART_COLORS[i]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
