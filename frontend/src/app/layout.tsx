import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Activity } from "lucide-react";
import { Providers } from "@/components/providers";
import { THEME_SCRIPT } from "@/lib/theme";
import { ThemeToggle } from "@/components/theme-toggle";
import { TourButton } from "@/components/tour";
import { UserMenu } from "@/components/user-menu";
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
      <head><script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} /></head>
      <body className="flex min-h-full flex-col">
        <Providers>
          <header className="bg-hero on-blue sticky top-0 z-30 shadow-md">
            <div className="mx-auto flex h-14 max-w-[110rem] items-center gap-4 px-4 sm:px-6 2xl:px-10">
              <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
                <span className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground shadow"><Activity className="size-[18px]" /></span>
                <span className="text-base">QAgent</span>
              </Link>
              <span className="ml-auto flex items-center gap-3 text-xs text-white/95">
                <Link href="/help" className="hover:text-white hover:underline" data-tour="help">How it works</Link>
                <TourButton />
                <kbd className="hidden rounded-md border bg-card px-1.5 py-0.5 font-sans sm:inline" data-tour="search">Ctrl K to search</kbd>
                <span className="hidden sm:inline">{USE_MOCK ? "Demo data" : "Connected"}</span>
                <span data-tour="theme"><ThemeToggle /></span>
                <UserMenu />
              </span>
            </div>
          </header>
          <main className="mx-auto w-full max-w-[110rem] flex-1 px-4 py-5 sm:px-6 2xl:px-10">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
