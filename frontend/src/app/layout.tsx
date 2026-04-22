import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FreightMind",
  description: "Freight analytics and document extraction",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-slate-50">
        <header className="bg-navy shrink-0">
          <div className="max-w-5xl mx-auto px-6 h-14 flex items-center gap-3">
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-blue-300"
            >
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
              <line x1="12" y1="22.08" x2="12" y2="12" />
            </svg>
            <div className="flex-1">
              <p className="text-white text-base font-bold tracking-tight leading-tight">
                FreightMind
              </p>
              <p className="text-blue-300 text-[10px] font-medium tracking-widest uppercase leading-tight">
                Freight Intelligence
              </p>
            </div>
            <nav className="flex items-center gap-1">
              <a
                href="/"
                className="text-xs text-blue-200 hover:text-white px-3 py-1.5 rounded-md hover:bg-white/10 transition-colors"
              >
                Analytics &amp; Docs
              </a>
              <a
                href="/verification"
                className="text-xs text-blue-200 hover:text-white px-3 py-1.5 rounded-md hover:bg-white/10 transition-colors"
              >
                Verification
              </a>
            </nav>
          </div>
        </header>
        <div className="flex-1 flex flex-col">{children}</div>
      </body>
    </html>
  );
}
