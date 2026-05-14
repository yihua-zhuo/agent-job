"use client";
import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { AuthGuard } from "@/lib/components/auth-guard";
import { SessionTimeoutGuard } from "@/lib/components/session-timeout-guard";
import { OfflineBanner } from "@/lib/components/offline-banner";
import { AIPanel } from "@/lib/components/ai-panel";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { TaskModal } from "@/app/(app)/tasks/task-modal";
import { useQuickAddTask } from "@/lib/store/task-store";
import { useCreateTask, useUpdateTask } from "@/lib/api/queries";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "crm_sidebar_collapsed";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === "true"; } catch { return false; }
  });
  const pathname = usePathname();
  const quickAdd = useQuickAddTask();
  const create = useCreateTask();
  const update = useUpdateTask();

  /* eslint-disable react-hooks/set-state-in-effect -- intentional: synchronizing sidebar open state with pathname change */
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);
  /* eslint-enable react-hooks/set-state-in-effect */

  function toggleSidebar() {
    setCollapsed((c) => !c);
  }

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, String(collapsed)); } catch {}
  }, [collapsed]);

  return (
    <AuthGuard>
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div
        className={cn(
          "fixed inset-y-0 left-0 z-30 transition-all duration-200 lg:relative lg:translate-x-0 lg:z-auto",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          collapsed ? "w-16" : "w-56"
        )}
      >
        <AppSidebar collapsed={collapsed} onToggle={toggleSidebar} />
      </div>

      <OfflineBanner />

      <div className="flex flex-1 flex-col overflow-hidden">
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

        <TaskModal
          open={quickAdd.isOpen}
          title="Create Task"
          onClose={quickAdd.close}
          initialStatus={quickAdd.initialStatus}
          onSubmit={async (data) => {
            await create.mutateAsync({ ...data, status: (data.status as string | undefined) ?? quickAdd.initialStatus });
            quickAdd.close();
          }}
          isSubmitting={create.isPending}
        />
      </div>
    </AuthGuard>
  );
}
