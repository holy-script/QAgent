"use client";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { Loading } from "@/components/ui";
import { REQUIRE_LOGIN, auth } from "@/lib/api/auth";

/** Sends signed-out visitors to the sign-in page; renders nothing protected until the session is known. */
export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const hydrated = useSyncExternalStore(() => () => {}, () => true, () => false); // false while the server HTML is adopted
  const { data: session, isPending } = useQuery({ queryKey: ["me"], queryFn: auth.me, enabled: REQUIRE_LOGIN, retry: false, staleTime: 60_000 });

  useEffect(() => {
    if (REQUIRE_LOGIN && !isPending && !session) {
      router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
    }
  }, [isPending, session, router]);

  if (REQUIRE_LOGIN && (!hydrated || !session)) return <Loading label={!hydrated || isPending ? "Checking your session…" : "Taking you to sign in…"} />;
  return <>{children}</>;
}
