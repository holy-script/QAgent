import type { ReactNode } from "react";

// Pages in this group sit behind the sign-in gate (see each page.tsx). The session is only known in the browser, so
// they cannot be rendered ahead of time and opt out of instant-navigation validation on purpose.
export const instant = false;

export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return children;
}
