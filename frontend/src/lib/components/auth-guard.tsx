"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuthStore } from "@/lib/store/auth-store";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const isHydrated = useAuthStore((s) => s.isHydrated);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated());

  useEffect(() => {
    if (isHydrated && !isAuthenticated) router.push("/login");
  }, [isHydrated, isAuthenticated, router]);

  if (!isHydrated || !isAuthenticated) return null;
  return <>{children}</>;
}
