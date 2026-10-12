"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/lib/theme";
import { useState, type ReactNode } from "react";
import { CommandPalette } from "@/components/command-palette";
import { TourProvider } from "@/components/tour";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

export function Providers({ children }: { children: ReactNode }) {
  const [qc] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: false } } }));
  return (
    // Light is the default; the choice is remembered. `class` toggles the .dark token set.
    <ThemeProvider>
      <QueryClientProvider client={qc}>
        <TooltipProvider delay={150}>
          <TourProvider>{children}</TourProvider>
          <CommandPalette />
          <Toaster richColors closeButton />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
