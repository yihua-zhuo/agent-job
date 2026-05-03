"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState, useEffect } from "react";
import { Toaster } from "sonner";
import { useThemeStore } from "@/lib/store/theme-store";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 60 * 1000, retry: 1 },
          mutations: { retry: 0 },
        },
      })
  );
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeEffect />
      {children}
      <Toaster position="bottom-right" richColors />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

function ThemeEffect() {
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
      root.setAttribute("data-theme", "dark");
    } else if (theme === "light") {
      root.classList.remove("dark");
      root.setAttribute("data-theme", "light");
    } else {
      root.removeAttribute("data-theme");
      if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
        root.classList.add("dark");
      } else {
        root.classList.remove("dark");
      }
    }
  }, [theme]);

  return null;
}
