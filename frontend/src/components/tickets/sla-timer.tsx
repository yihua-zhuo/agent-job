"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";

const SLA_HOURS: Record<string, number> = {
  basic: 24,
  standard: 8,
  premium: 4,
  enterprise: 1,
};

interface SLATimerProps {
  responseDeadline: string | null;
  createdAt: string;
  slaLevel: string;
  className?: string;
}

function formatRemaining(totalMs: number): string {
  const totalMinutes = Math.floor(Math.abs(totalMs) / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (totalMs <= 0) return `${hours}h ${minutes}m left`;
  return `${hours}h ${minutes}m`;
}

export function SLATimer({ responseDeadline, createdAt, slaLevel, className }: SLATimerProps) {
  const [, tick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 60000);
    return () => clearInterval(id);
  }, []);

  if (!responseDeadline || !createdAt) {
    return (
      <Badge variant="outline" className={className}>
        —
      </Badge>
    );
  }

  const now = Date.now();
  const deadline = new Date(responseDeadline).getTime();
  const created = new Date(createdAt).getTime();

  const slaHours = SLA_HOURS[slaLevel] ?? 8;
  const totalMs = slaHours * 60 * 60 * 1000;
  const elapsedMs = now - created;
  const remainingMs = deadline - now;

  const ratio = Math.min(elapsedMs / totalMs, 1);
  const breached = remainingMs < 0;

  let colorClass = "bg-green-100 text-green-800 border-green-300";
  if (ratio > 0.75) colorClass = "bg-red-100 text-red-800 border-red-300";
  else if (ratio > 0.5) colorClass = "bg-yellow-100 text-yellow-800 border-yellow-300";

  const remaining = formatRemaining(remainingMs);

  return (
    <Badge
      colorClass={colorClass}
      className={
        breached
          ? `${colorClass} animate-pulse border-red-500`
          : colorClass + (className ? ` ${className}` : "")
      }
    >
      {remaining}
    </Badge>
  );
}