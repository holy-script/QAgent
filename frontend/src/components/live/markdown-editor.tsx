"use client";
import { markdown } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { Diagnostic, linter, lintGutter } from "@codemirror/lint";
import { Extension } from "@codemirror/state";
import { Decoration, EditorView, MatchDecorator, ViewPlugin, ViewUpdate } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import CodeMirror from "@uiw/react-codemirror";
import { useMemo } from "react";
import { useTheme } from "@/lib/theme";

// Colours come from the theme tokens, so the editor follows light and dark mode without its own palette.
const highlight = HighlightStyle.define([
  { tag: t.heading1, color: "var(--brand)", fontWeight: "700", fontSize: "1.1em" },
  { tag: t.heading2, color: "var(--brand)", fontWeight: "700" },
  { tag: t.heading3, color: "var(--primary)", fontWeight: "600" },
  { tag: t.heading4, color: "var(--violet)", fontWeight: "600" },
  { tag: [t.strong], fontWeight: "700" },
  { tag: [t.emphasis], fontStyle: "italic" },
  { tag: [t.monospace, t.processingInstruction], color: "var(--ok)" },
  { tag: [t.list, t.quote], color: "var(--muted-foreground)" },
  { tag: [t.link, t.url], color: "var(--brand)", textDecoration: "underline" },
  { tag: [t.contentSeparator, t.meta], color: "var(--muted-foreground)" },
]);

const theme = EditorView.theme({
  "&": { backgroundColor: "var(--card)", color: "var(--foreground)", fontSize: "13px", borderRadius: "0.5rem", border: "1px solid var(--border)" },
  "&.cm-focused": { outline: "2px solid var(--ring)", outlineOffset: "1px" },
  ".cm-scroller": { fontFamily: "var(--font-geist-mono), ui-monospace, monospace", lineHeight: "1.6" },
  ".cm-content": { caretColor: "var(--foreground)", padding: "8px 0" },
  ".cm-gutters": { backgroundColor: "var(--muted)", color: "var(--muted-foreground)", border: "none", borderRight: "1px solid var(--border)" },
  ".cm-activeLine": { backgroundColor: "var(--accent)" },
  ".cm-activeLineGutter": { backgroundColor: "var(--accent)" },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": { backgroundColor: "var(--brand-soft) !important" },
  ".cm-tooltip": { backgroundColor: "var(--popover)", color: "var(--popover-foreground)", border: "1px solid var(--border)", borderRadius: "0.5rem" },
  ".cm-lint-marker-error": { content: '"●"' },
  ".qa-id": { color: "var(--violet)", fontWeight: "600" },
  ".qa-binding": { color: "var(--brand)" },
  ".qa-key": { color: "var(--muted-foreground)" },
});

/** Highlights what only this format has: item IDs (REQ-1, F-2...), binding sources (api:, ui:, const:) and `- field:` keys. */
const marks = new MatchDecorator({
  regexp: /\b(?:REQ|EC|UX|RX|F|G)-\d+\b|\b(?:api|ui|const):|^\s*-\s+[a-z_]+(?=:)/g,
  decoration: (m) => Decoration.mark({ class: /^\s*-/.test(m[0]) ? "qa-key" : /:$/.test(m[0]) ? "qa-binding" : "qa-id" }),
});
const playbookMarks = ViewPlugin.fromClass(class {
  decorations;
  constructor(view: EditorView) { this.decorations = marks.createDeco(view); }
  update(u: ViewUpdate) { this.decorations = marks.updateDeco(u, this.decorations); }
}, { decorations: (v) => v.decorations });

/** Finds the line a validation message is about: the heading of the item it names, or the section it complains about. */
export function lineForMessage(doc: string, message: string): number | null {
  const lines = doc.split("\n");
  const find = (re: RegExp) => { const i = lines.findIndex((l) => re.test(l)); return i < 0 ? null : i + 1; };
  const key = message.match(/^([A-Z]{1,3}-\d+)\b/)?.[1];
  if (key) return find(new RegExp(`^###\\s+${key}\\b`));
  const flow = message.match(/^flow ([\w#.-]+)/)?.[1];
  if (flow) return find(new RegExp(`^###\\s+Flow:\\s*${flow.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`, "i"));
  const section = message.match(/unknown section '([^']+)'/)?.[1];
  if (section) return find(new RegExp(`^##\\s+${section}\\s*$`));
  const ref = message.match(/'([A-Z]{1,3}-\d+)'/)?.[1];
  if (ref) return find(new RegExp(`\\b${ref}\\b`));
  return null;
}

export interface Problem { message: string; level: "error" | "warning"; line?: number }

function problemLinter(problems: Problem[]): Extension {
  return linter((view): Diagnostic[] => {
    const doc = view.state.doc;
    const out: Diagnostic[] = [];
    for (const p of problems) {
      const n = p.line && p.line > 0 ? p.line : lineForMessage(doc.toString(), p.message);
      if (!n || n > doc.lines) continue;
      const line = doc.line(n);
      out.push({ from: line.from, to: line.to, severity: p.level === "error" ? "error" : "warning", message: p.message });
    }
    return out;
  }, { delay: 0 });
}

/** Markdown editor for test plans: syntax colours, line numbers, and problems underlined on the line they belong to. */
export function MarkdownEditor({ value, onChange, problems = [], readOnly = false, minHeight = "22rem", maxHeight = "34rem", label = "Test plan text" }: {
  value: string; onChange?: (v: string) => void; problems?: Problem[]; readOnly?: boolean; minHeight?: string; maxHeight?: string; label?: string;
}) {
  const { resolvedTheme } = useTheme();
  const extensions = useMemo(() => [
    markdown(), syntaxHighlighting(highlight), theme, playbookMarks, EditorView.lineWrapping,
    lintGutter(), problemLinter(problems),
    EditorView.contentAttributes.of({ "aria-label": label }),
  ], [problems, label]);
  return (
    <CodeMirror value={value} onChange={onChange} extensions={extensions} readOnly={readOnly} editable={!readOnly}
      theme={resolvedTheme} minHeight={minHeight} maxHeight={maxHeight} basicSetup={{ foldGutter: false, highlightActiveLine: !readOnly, lineNumbers: true }} />
  );
}
