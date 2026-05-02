import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/lib/components/providers";

export const metadata: Metadata = {
  title: "CRM Dashboard",
  description: "Agent Job CRM System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
