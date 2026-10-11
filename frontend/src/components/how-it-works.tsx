import { FileText, Globe, Play, Search } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui";

const STEPS = [
  { icon: Globe, title: "Add your app", text: "Give QAgent the address of a website or web app." },
  { icon: FileText, title: "Describe what to test", text: "Write a test plan in plain words: journeys to try and what should be true afterwards." },
  { icon: Play, title: "Run it", text: "A real browser works through your plan while AI chooses what to click." },
  { icon: Search, title: "See what broke", text: "Every problem comes with screenshots and proof, and is tracked until it is fixed." },
];

/** Four-step explainer shown above the app list. */
export function HowItWorks() {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-baseline gap-3"><h2 className="font-medium">How it works</h2><Link href="/help" className="text-xs text-brand hover:underline">Read the full guide →</Link></div>
      <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand"><s.icon className="size-4" /></span>
            <div><div className="text-sm font-medium">{i + 1}. {s.title}</div><div className="text-xs text-muted-foreground">{s.text}</div></div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
