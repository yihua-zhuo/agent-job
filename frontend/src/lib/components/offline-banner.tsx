"use client";
import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";

export function OfflineBanner() {
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    setIsOffline(!navigator.onLine);

    function onOnline() { setIsOffline(false); }
    function onOffline() { setIsOffline(true); }

    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  return (
    <div
      className={cn(
        "flex items-center justify-center gap-2 bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground transition-all",
        isOffline ? "h-auto opacity-100" : "h-0 opacity-0 overflow-hidden py-0 px-0 border-0"
      )}
      role="status"
      aria-live="polite"
    >
      <WifiOff className="h-4 w-4 flex-shrink-0" />
      <span>You are currently offline. Read-only mode active.</span>
    </div>
  );
}
