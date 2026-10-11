"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { buttonVariants } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { REQUIRE_LOGIN, auth } from "@/lib/api/auth";
import { cn } from "@/lib/utils";

export function UserMenu() {
  const qc = useQueryClient();
  const router = useRouter();
  const { data: session } = useQuery({ queryKey: ["me"], queryFn: auth.me, enabled: REQUIRE_LOGIN, retry: false, staleTime: 60_000 });
  if (!REQUIRE_LOGIN || !session) return null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account" className={cn(buttonVariants({ variant: "ghost", size: "icon" }))}><User className="size-4" /></DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup><DropdownMenuLabel className="truncate font-normal text-muted-foreground">{session.email}</DropdownMenuLabel></DropdownMenuGroup>
        <DropdownMenuItem onClick={async () => { await auth.logout(); qc.clear(); router.replace("/login"); }}><LogOut className="size-4" />Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
