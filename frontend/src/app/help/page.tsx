import Link from "next/link";
import { Card } from "@/components/ui";
import { GLOSSARY } from "@/lib/terms";

export const metadata = { title: "How QAgent works" };

export default function Help() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">How QAgent works</h1>
        <p className="mt-1 text-muted-foreground">QAgent tests a website the way a careful person would. It opens a real browser, follows the journeys you describe, checks that the right things happen, and hands you a list of real bugs with proof.</p>
      </div>
      <Card className="p-5">
        <h2 className="font-medium">The five-minute path</h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm">
          <li><b>Add your app.</b> Give it a name and the website address.</li>
          <li><b>Write a test plan.</b> List the journeys to try (&ldquo;add 2 items to the cart, open the cart&rdquo;) and what should be true afterwards. No code needed. You can start from the sample or paste rough notes and let AI tidy them.</li>
          <li><b>Run it.</b> Choose Smart mode and press <i>Run now</i>. Watch it live or come back later.</li>
          <li><b>Read what it found.</b> Each problem has screenshots, the exact server calls and the numbers that did not match.</li>
          <li><b>Fix, then repeat.</b> Run again. Bugs that no longer appear are marked Fixed; any that return are marked Came back.</li>
        </ol>
      </Card>
      <Card className="p-5">
        <h2 className="font-medium">Guided setup and tours</h2>
        <p className="mt-1 text-sm text-muted-foreground">The Setup guide on an app&apos;s Overview takes you step by step from nothing to your first results. Tours are short walk-throughs that point at the real screen. Open one here, or press <b>Tour</b> in the top bar on any page to get the tour for that page.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link href="/?tour=home" className="rounded-lg border px-3 py-1.5 text-sm hover:bg-foreground/5">Home and dashboard</Link>
          <span className="self-center text-xs text-muted-foreground">Then open an app, a run, a test plan or a bug and press Tour for the rest.</span>
        </div>
      </Card>
      <section className="space-y-3">
        <h2 className="font-medium">Words you will see</h2>
        <dl className="divide-y rounded-xl border bg-card">
          {GLOSSARY.map((g) => (
            <div key={g.term} className="grid gap-1 px-4 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="text-sm font-medium">{g.term}</dt>
              <dd className="text-sm text-muted-foreground">{g.meaning}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section className="space-y-2 text-sm">
        <h2 className="font-medium">Good to know</h2>
        <ul className="list-disc space-y-1.5 pl-5 text-muted-foreground">
          <li>QAgent only visits your app and the extra sites you allow in Settings, so a run cannot wander off.</li>
          <li>Calculations such as totals are checked by plain code, never guessed by AI. AI is used to choose what to click, to judge things that have no fixed rule, and to write the reports.</li>
          <li>When an AI judges something, the report says so, and the problem is never rated more serious than medium unless a fixed rule also failed.</li>
          <li>A journey can be written two ways: <b>steps</b> (exact clicks) or a <b>goal</b> (&ldquo;sign in and complete the setup&rdquo;), where the AI works out the clicks. Goals are quicker to write and survive small page changes. <b>Create from product document</b> writes goal-based journeys for you.</li>
          <li>Rather talk than type? Press <b>Dictate</b> next to a text box (Chrome, Edge or Safari), then <b>Tidy up with AI</b> to clean it up. You can undo it.</li>
          <li>Press <kbd className="rounded border bg-card px-1">Ctrl</kbd> + <kbd className="rounded border bg-card px-1">K</kbd> anywhere to jump to an app, a run or a bug.</li>
        </ul>
      </section>
    </div>
  );
}
