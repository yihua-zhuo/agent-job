"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store/auth-store";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const IDLE_TIMEOUT_MS = 25 * 60 * 1000;   // 25 min — warning appears
const LOGOUT_TIMEOUT_MS = 30 * 60 * 1000; // 30 min — forced logout

export function SessionTimeoutGuard() {
  const { isAuthenticated, clearAuth } = useAuthStore();
  const router = useRouter();
  const [showWarning, setShowWarning] = useState(false);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleWarning = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    idleTimerRef.current = setTimeout(() => setShowWarning(true), IDLE_TIMEOUT_MS);
    logoutTimerRef.current = setTimeout(() => {
      clearAuth();
      router.push("/login");
    }, LOGOUT_TIMEOUT_MS);
    setShowWarning(false);
  }, [clearAuth, router]);

  useEffect(() => {
    if (!isAuthenticated()) return;
    scheduleWarning();

    function onActivity() { scheduleWarning(); }
    window.addEventListener("mousemove", onActivity);
    window.addEventListener("mousedown", onActivity);
    window.addEventListener("keydown", onActivity);
    window.addEventListener("touchstart", onActivity);
    window.addEventListener("scroll", onActivity, { passive: true });

    return () => {
      window.removeEventListener("mousemove", onActivity);
      window.removeEventListener("mousedown", onActivity);
      window.removeEventListener("keydown", onActivity);
      window.removeEventListener("touchstart", onActivity);
      window.removeEventListener("scroll", onActivity);
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    };
  }, [isAuthenticated, scheduleWarning]);

  return (
    <Dialog open={showWarning} onOpenChange={() => {}}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Session Expiring</DialogTitle>
          <DialogDescription className="pt-2">
            You&apos;ve been inactive for a while. For your security, you&apos;ll be logged out
            in less than 5 minutes.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="destructive"
            size="sm"
            onClick={() => {
              clearAuth();
              router.push("/login");
            }}
          >
            Log Out Now
          </Button>
          <Button size="sm" onClick={scheduleWarning}>
            Stay Logged In
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
