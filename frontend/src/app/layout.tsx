import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/lib/components/providers";

export const metadata: Metadata = {
  title: "CRM Dashboard",
  description: "Agent Job CRM System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var raw = localStorage.getItem('crm_theme');
                  var theme = 'system';
                  if (raw) {
                    try {
                      var parsed = JSON.parse(raw);
                      theme = parsed.state && parsed.state.theme ? parsed.state.theme : 'system';
                    } catch {
                      if (raw === 'light' || raw === 'dark') theme = raw;
                    }
                  }
                  if (theme === 'dark') {
                    document.documentElement.classList.add('dark');
                  } else if (theme === 'system') {
                    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
                      document.documentElement.classList.add('dark');
                    }
                  }
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
