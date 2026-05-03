"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store/auth-store";
import { Users, TrendingUp, Ticket, BarChart3, Sparkles, LogOut, CheckSquare, Bell, Activity, UsersRound, Settings as SettingsIcon, Shield, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const navItems = [
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/sales", label: "Opportunities", icon: TrendingUp },
  { href: "/tickets", label: "Tickets", icon: Ticket },
  { href: "/tasks", label: "Tasks", icon: CheckSquare },
  { href: "/activities", label: "Activities", icon: Activity },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/team", label: "Team", icon: UsersRound },
  { href: "/sla", label: "SLA", icon: Shield },
  { href: "/settings", label: "Settings", icon: SettingsIcon },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/ai", label: "AI", icon: Sparkles },
  { href: "/import-export", label: "Import/Export", icon: Upload },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { user, clearAuth } = useAuthStore();

  return (
    <aside className="flex h-screen w-56 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center border-b px-4">
        <span className="font-semibold text-base">CRM Dashboard</span>
      </div>
      <nav className="flex-1 space-y-0.5 p-2">
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              pathname?.startsWith(href)
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>
      <div className="border-t p-3">
        {user && (
          <div className="mb-2 text-xs">
            <div className="font-medium">{user.full_name ?? user.username}</div>
            <div className="text-muted-foreground">{user.role}</div>
          </div>
        )}
        <Button variant="ghost" size="sm" onClick={() => { clearAuth(); window.location.href = "/login"; }}>
          <LogOut className="h-3.5 w-3.5" />
          Sign Out
        </Button>
      </div>
    </aside>
  );
}
