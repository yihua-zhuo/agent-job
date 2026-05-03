"use client";
import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { AuthGuard } from "@/lib/components/auth-guard";
import { SessionTimeoutGuard } from "@/lib/components/session-timeout-guard";
import { OfflineBanner } from "@/lib/components/offline-banner";
import { AIPanel } from "@/lib/components/ai-panel";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  // Close sidebar on navigation
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  return (
    <AuthGuard>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — slides in on mobile, static on lg+ */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-30 w-56 transition-transform duration-200 lg:relative lg:translate-x-0 lg:z-auto",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <AppSidebar />
      </div>

      <OfflineBanner />

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile header with hamburger */}
        <div className="flex h-14 items-center border-b bg-background px-4 lg:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="flex cursor-pointer items-center justify-center rounded-md p-1.5 text-muted-foreground hover:bg-muted"
            aria-label="Open navigation menu"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>

        <main className="flex-1 overflow-y-auto">
          <div className="p-6">{children}</div>
        </main>

        <AIPanel />

        <SessionTimeoutGuard />
      </div>
    </AuthGuard>
  );
}