"use client";
import { Check, Laptop, Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";
import { useSyncExternalStore } from "react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { id: "light", label: "Light", icon: Sun },
  { id: "dark", label: "Dark", icon: Moon },
  { id: "system", label: "Match my device", icon: Laptop },
] as const;

/** Light / dark / system switcher. The app defaults to light. */
export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(() => () => {}, () => true, () => false); // false during SSR, true in the browser
  const Icon = mounted && resolvedTheme === "dark" ? Moon : Sun;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Change theme" className={cn(buttonVariants({ variant: "ghost", size: "icon" }))}>
        <Icon className="size-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        {OPTIONS.map(({ id, label, icon: I }) => (
          <DropdownMenuItem key={id} onClick={() => setTheme(id)}>
            <I className="size-4" />{label}{mounted && theme === id && <Check className="ml-auto size-4" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
