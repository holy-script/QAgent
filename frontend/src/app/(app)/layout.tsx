import type { ReactNode } from "react";
import { AuthGate } from "@/components/auth-gate";

// Every page in this group needs a signed-in user, which is only known in the browser. That makes the pages
// impossible to render ahead of time, so they opt out of Next's instant-navigation validation on purpose.
export const instant = false;

export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return <AuthGate>{children}</AuthGate>;
}
