import type { Metadata } from "next";
import "./globals.css";
import { SidebarNav } from "@/components/nav";

export const metadata: Metadata = {
  title: "Grasmere Routes",
  description: "Delivery route platform for Grasmere Farm",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB">
      <body className="min-h-screen bg-background font-sans antialiased">
        <div className="grid min-h-screen grid-cols-[220px_1fr]">
          <aside className="border-r bg-card">
            <div className="flex h-14 items-center gap-2 border-b px-4">
              <span className="text-lg font-semibold">Grasmere Routes</span>
            </div>
            <SidebarNav />
          </aside>
          <main className="overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
