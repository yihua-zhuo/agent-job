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
                  var t = localStorage.getItem('crm_theme');
                  if (!t) t = 'system';
                  if (t === 'dark') {
                    document.documentElement.classList.add('dark');
                  } else if (t === 'light') {
                    document.documentElement.classList.remove('dark');
                  } else {
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
