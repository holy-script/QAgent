// The guided tours. Each step points at an element marked data-tour="…" on the page. Steps whose element is not on
// screen (for example the side list on a phone) are skipped, so the same tour works at any size.

export interface TourStep { target?: string; title: string; text: string; side?: "top" | "bottom" | "left" | "right" }
export interface TourDef { id: string; label: string; steps: TourStep[] }

export const TOURS: Record<string, TourDef> = {
  home: {
    id: "home", label: "Home",
    steps: [
      { title: "Welcome to QAgent", text: "QAgent tests your web app the way a person would: it opens a real browser, clicks through your app and tells you what is broken. This 1-minute tour shows where things are. Press Esc any time to stop." },
      { target: "dashboard", title: "How testing is going", text: "Totals and trends across all your apps: runs, how many were clean, open bugs, and what the AI cost. Use the 7 / 30 / 90 day switch to change the period.", side: "bottom" },
      { target: "app-list", title: "Your apps", text: "Each app is a website you test. Open one to run tests, edit its test plans and see its bugs.", side: "top" },
      { target: "add-app", title: "Add an app", text: "Start here: give QAgent the address of your site. You then describe what to test, and run it.", side: "left" },
      { target: "search", title: "Jump anywhere", text: "Press Ctrl K (or ⌘ K) to search pages, runs and bugs from anywhere.", side: "bottom" },
      { target: "theme", title: "Light or dark", text: "Switch the look, or let it follow your device.", side: "bottom" },
      { target: "help", title: "Need a reminder?", text: "“How it works” explains the ideas in plain words, and the Tour button replays this guide on any page.", side: "bottom" },
    ],
  },
  app: {
    id: "app", label: "An app",
    steps: [
      { title: "An app's workspace", text: "Everything about one app lives here. The list on the left (tabs on a phone) moves between its parts." },
      { target: "guide-progress", title: "Setup guide", text: "New here? This card shows the next step in the recommended order: describe the app, add test files if needed, write a test plan, run it, read the results, then repeat after a fix. It takes you to the right page and points at what to do.", side: "right" },
      { target: "nav-overview", title: "Overview", text: "The summary: recent runs, requirement status, open bugs, and the “Run a test” box.", side: "right" },
      { target: "nav-plans", title: "Test plans", text: "A test plan says what to check: requirements, journeys through the app, and expectations. You write it as simple text, or build it with forms.", side: "right" },
      { target: "nav-runs", title: "Runs", text: "Every time a plan is run is recorded here, with results, speed and cost.", side: "right" },
      { target: "nav-journeys", title: "Journeys", text: "A journey is one path a user takes, like adding to the cart and paying. See how each one has fared run after run.", side: "right" },
      { target: "nav-bugs", title: "Bugs", text: "Problems found, grouped so the same bug across runs counts once. Each has steps to reproduce, screenshots and the server call involved.", side: "right" },
      { target: "nav-requirements", title: "Requirements", text: "Which of your requirements are being tested, and which are failing.", side: "right" },
      { target: "nav-compare", title: "Compare", text: "Put two runs side by side, for example before and after a fix.", side: "right" },
      { target: "nav-settings", title: "Settings", text: "The app's address, test files to upload, how long to keep old runs, and more.", side: "right" },
      { target: "run-launcher", title: "Run a test", text: "Pick a test plan and a mode, then press Run now. Smart is a good default. Tick the planning box if a plan has unclear steps.", side: "left" },
    ],
  },
  run: {
    id: "run", label: "A run",
    steps: [
      { title: "Watching a run", text: "This page shows a test run live, or replays a finished one. Every step the browser took is recorded." },
      { target: "run-metrics", title: "The numbers", text: "Steps taken, problems found, which AI made the decisions, speed, cost and server calls.", side: "bottom" },
      { target: "run-tabs", title: "Different views", text: "Journeys shows each path step by step. How it decided shows the AI loop. AI calls lists every AI call with its cost. Server calls, Timeline and Activity are for digging deeper. Problems lists what failed.", side: "bottom" },
      { target: "report", title: "The report", text: "A readable summary with bugs, what to fix first, and requirement coverage. You can export it.", side: "bottom" },
      { target: "repeat", title: "Repeat exactly", text: "Run the same test again from the recording, with no AI calls and no cost. Good for checking a fix.", side: "bottom" },
    ],
  },
  plan: {
    id: "plan", label: "A test plan",
    steps: [
      { title: "A test plan", text: "This is what QAgent checks. It is plain text with a few sections, and you can edit it either as text or with forms." },
      { target: "editor", title: "Edit it", text: "Choose Edit test plan. Guided mode gives forms for each section; Text mode is the raw plan with colours and line numbers. Problems are underlined on the line they belong to.", side: "top" },
      { target: "versions", title: "Versions", text: "Saving creates a new version. Runs remember which version they used, so results stay comparable.", side: "left" },
    ],
  },
  bug: {
    id: "bug", label: "A bug",
    steps: [
      { title: "A bug report", text: "One bug, tracked across runs. Everything needed to understand and fix it is on this page." },
      { target: "bug-report", title: "What happened", text: "What was expected, what actually happened, how to reproduce it, and screenshots from the moment it failed.", side: "top" },
      { target: "bug-copy", title: "Copy as issue", text: "Paste the whole report into your issue tracker.", side: "left" },
    ],
  },
};

/** Which tour belongs to a page. Pages without their own use the closest one. */
export function tourForPath(path: string): string {
  if (path === "/" || path === "/help") return "home";
  if (/^\/apps\/[^/]+\/runs\/[^/]+/.test(path)) return "run";
  if (/^\/apps\/[^/]+\/issues\/[^/]+/.test(path)) return "bug";
  if (/^\/apps\/[^/]+\/playbooks\/[^/]+/.test(path)) return "plan";
  if (path.startsWith("/apps/") && path !== "/apps/new") return "app";
  return "home";
}
