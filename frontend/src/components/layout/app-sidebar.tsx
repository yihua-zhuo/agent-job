"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store/auth-store";
import {
  Users, TrendingUp, Ticket, BarChart3, Sparkles, CheckSquare, Bell,
  Activity, UsersRound, Settings as SettingsIcon, Shield, Upload,
  LogOut, UserCog,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { useRouter } from "next/navigation";
import { useNotifications } from "@/lib/api/queries";

const crmItems = [
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/sales", label: "Opportunities", icon: TrendingUp },
  { href: "/tickets", label: "Tickets", icon: Ticket },
  { href: "/tasks", label: "Tasks", icon: CheckSquare },
  { href: "/activities", label: "Activities", icon: Activity },
  { href: "/notifications", label: "Notifications", icon: Bell, badge: true },
  { href: "/team", label: "Team", icon: UsersRound },
  { href: "/sla", label: "SLA", icon: Shield },
];

const systemItems = [
  { href: "/settings", label: "Settings", icon: SettingsIcon },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/ai", label: "AI", icon: Sparkles },
  { href: "/import-export", label: "Import/Export", icon: Upload },
];

function NavGroup({ items, unreadCount }: { items: typeof crmItems; unreadCount: number }) {
  const pathname = usePathname();

  function isActive(href: string) {
    return pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <>
      {items.map(({ href, label, icon: Icon, badge }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "flex cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-all duration-150",
            isActive(href)
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          )}
          aria-label={label}
        >
          <span className="relative flex h-4 w-4 flex-shrink-0">
            <Icon className="h-4 w-4" />
            {badge && unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white leading-none">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </span>
          <span>{label}</span>
        </Link>
      ))}
    </>
  );
}

export function AppSidebar() {
  const { user, clearAuth } = useAuthStore();
  const router = useRouter();
  const { data: notifData } = useNotifications(1, true);
  const unreadCount = (notifData?.data?.total as number) ?? 0;

  const initials = user
    ? (user.full_name ?? user.username ?? "?").slice(0, 2).toUpperCase()
    : "?";

  function handleSignOut() {
    clearAuth();
    router.push("/login");
  }

  function handleSettings() {
    router.push("/settings");
  }

  return (
    <aside className="flex h-screen w-56 flex-col border-r bg-sidebar">
      {/* Header */}
      <div className="flex h-14 items-center border-b px-4">
        <span className="font-bold text-base tracking-tight">CRM Dashboard</span>
      </div>

      {/* Primary CRM navigation */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        <NavGroup items={crmItems} unreadCount={unreadCount} />

        <Separator className="my-2" />

        {/* System settings */}
        <NavGroup items={systemItems} unreadCount={0} />
      </nav>

      {/* User profile footer */}
      <div className="border-t p-3">
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="flex w-full cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted"
            >
              <Avatar className="h-8 w-8 flex-shrink-0">
                <AvatarFallback className="bg-primary text-primary-foreground text-xs font-semibold">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold leading-tight">
                  {user?.full_name ?? user?.username ?? "—"}
                </div>
                <div className="truncate text-xs text-muted-foreground leading-tight capitalize">
                  {user?.role ?? "—"}
                </div>
              </div>
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-48 p-1" align="start" side="top">
            <button
              type="button"
              onClick={handleSettings}
              className="flex w-full cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm transition-colors hover:bg-muted"
            >
              <UserCog className="h-4 w-4 text-muted-foreground" />
              Profile Settings
            </button>
            <Separator className="my-1" />
            <button
              type="button"
              onClick={handleSignOut}
              className="flex w-full cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-destructive transition-colors hover:bg-destructive/5"
            >
              <LogOut className="h-4 w-4" />
              Sign Out
            </button>
          </PopoverContent>
        </Popover>
      </div>
    </aside>
  );
}