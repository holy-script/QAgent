import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Activity } from "lucide-react";
import { Providers } from "@/components/providers";
import { ThemeToggle } from "@/components/theme-toggle";
import { USE_MOCK } from "@/lib/api/client";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "QAgent", template: "%s · QAgent" },
  description: "Autonomous QA runs for web apps: Claude plans, Jev decides, Playwright drives.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <Providers>
          <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
            <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
              <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
                <span className="grid size-7 place-items-center rounded-lg bg-primary text-primary-foreground"><Activity className="size-4" /></span>
                QAgent
              </Link>
              <span className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
                <Link href="/help" className="hover:text-foreground">How it works</Link>
                <kbd className="hidden rounded-md border bg-card px-1.5 py-0.5 font-sans sm:inline">Ctrl K to search</kbd>
                <span className="hidden sm:inline">{USE_MOCK ? "Demo data" : "Connected"}</span>
                <ThemeToggle />
              </span>
            </div>
          </header>
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
