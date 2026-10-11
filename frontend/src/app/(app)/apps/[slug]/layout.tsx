import type { ReactNode } from "react";
import { AppShellLayout } from "./app-shell";

// Data for these pages is fetched in the browser after sign-in, so they cannot be pre-rendered for instant navigation.
export const instant = false;

export default function Layout({ children }: { children: ReactNode }) {
  return <AppShellLayout>{children}</AppShellLayout>;
}
