import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { ScrollRestorer } from "@/components/layout/scroll-restorer";

export const metadata: Metadata = {
  title: "WealthRadar",
  description: "AI Chief of Staff for Financial Advisors",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="flex h-screen overflow-hidden bg-background text-foreground">
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto p-6">
            <ScrollRestorer />
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
