"""
The verifier: for a judged expectation that needs the page to be USED ("navigation elements are clickable and responsive",
"opens the right page"), Claude works on the live browser instead of looking at one screenshot. Each turn it sees the page
(accessibility tree, interactive elements, a screenshot), then either tries something (click, hover, back) and is told what
happened (new URL, messages, console errors), or answers. It is capped at a few actions, and only its final verdict is put on
the tape, so a repeat of the run makes no model calls and touches no browser.
"""
import re
import time
from typing import Any, Callable, Dict, List, Optional

from playwright.async_api import Page

from qagent.browser.executor import BrowserExecutor
from qagent.browser.extractor import EXTRACTOR_JS
from qagent.browser.wait_frames import wait_dom_stable
from qagent.checks.ux_judged import Verdict
from qagent.config import settings
from qagent.decision.charter import with_charter
from qagent.decision.claude import usage_cost
from qagent.domain.schemas import CandidateAction

BEHAVIOUR = re.compile(r"\b(download\w*|export\w*|start\w*|saves?|submit\w*|generat\w*|loads?|chang\w*|updat\w*|respon\w*|react\w*|recalculat\w*|computed|click\w*|clickable|hover\w*|opens?|navigat\w+|toggle\w*|expand\w*|collaps\w*)\b", re.I)

_STOP = {"the", "and", "that", "with", "for", "are", "was", "not", "any", "all", "this", "shows", "show", "page", "from", "has", "have"}

VERIFY_TOOL = {
    "toolSpec": {
        "name": "verify_step",
        "description": "Either try one thing on the live page to gather evidence, or give the final verdict.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["click", "hover", "type", "back", "answer"]},
                "target_id": {"type": "integer", "description": "id of the interactive element (for click, hover or type)"},
                "text": {"type": "string", "description": "only with action=type: the text to type into the field (it replaces what is there)"},
                "verdict": {"type": "string", "enum": ["holds", "does_not_hold", "inconclusive"],
                            "description": "only with action=answer. holds = the statement as written is true; does_not_hold = the statement as written "
                                           "is NOT true (the evidence contradicts it); inconclusive = you tried and cannot tell. It must agree with your reasoning."},
                "confidence": {"type": "number", "description": "0.0-1.0, only with action=answer"},
                "reasoning": {"type": "string", "description": "one or two sentences citing what you saw or did"},
            },
            "required": ["action", "reasoning"],
        }},
    }
}

SYSTEM = (
    "You verify a statement about a web app by using the live page, like a careful tester. You can click or hover an element, type "
    "into a field, go back, or answer. Statements may contain negations (is not, does not, never): answer 'holds' only when the whole statement as written is true and 'does_not_hold' when it is not, and make sure your reasoning agrees with your verdict (if your reasoning says the statement is contradicted, the verdict is does_not_hold). Elements marked [DISABLED] cannot be used right now: use that mark, not how a button looks, to judge enabled or disabled. Gather real evidence: if the statement is about something working (clickable, responsive, navigates, "
    "opens, updates), try it on a few representative elements and look at what happened; to check that something responds to input or is computed from data, change a value (type) and see what else changes. Do not answer 'inconclusive' just "
    "because a screenshot is static: you can act. Answer 'does_not_hold' only when what you saw contradicts the statement (nothing "
    "happened, an error appeared, the wrong page opened); answer 'holds' when your evidence supports it; use 'inconclusive' only "
    "when you tried and still cannot tell. Avoid destructive actions (deleting, paying, submitting real data) and do not repeat "
    "actions that change the journey's state (Fix, Upload, Commit): the steps already done are listed (a step listed only means the action was carried out, not that it had the intended effect: check effects yourself), so judge statements "
    "about an earlier moment (such as before the fix) from that list and the page now, or answer inconclusive. When the statement is about an earlier screen (Upload, Explore, Method...), the text listed under 'Earlier screens' is the evidence for it: facts shown there count, and you must not call the statement false just because the page you are on now is a different screen. Words like 'about' or 'around' allow small differences, so do not fail a statement for being exact; names that mean the same thing (volume and trx) count as the same. If the statement is about changes or reactions (changes, updates, responds, is computed from), you must do it and compare before answering: never answer about what would happen. You have a "
    "limited number of actions, so be efficient and answer as soon as the evidence is clear."
)


async def _aria(page: Page) -> str:
    try:
        return (await page.locator("body").aria_snapshot(timeout=3000))[:3000]
    except Exception:
        return ""


async def _look(page: Page, with_image: bool = True) -> Dict[str, Any]:
    await wait_dom_stable(page, quiet_ms=300, max_ms=2000)
    try:
        raw = await page.evaluate(EXTRACTOR_JS)
    except Exception:
        raw = []
    candidates = [CandidateAction.model_validate(c) for c in raw[:60]]
    try:
        text = (await page.evaluate("document.body ? document.body.innerText : ''"))[:1800]
        title = await page.title()
    except Exception:
        text, title = "", ""
    shot = None
    if with_image:
        try:
            shot = await page.screenshot(type="jpeg", quality=60)
        except Exception:
            shot = None
    return {"url": page.url, "title": title, "text": text, "aria": await _aria(page), "candidates": candidates, "shot": shot}


def _earlier(statement: str, snapshots: List[Dict[str, Any]]) -> str:
    """Page text after earlier steps that mention what the statement talks about, so a statement about an earlier screen can be judged."""
    words = {w for w in re.findall(r"[a-z0-9%/.,]{3,}", statement.lower()) if w not in _STOP}
    scored = sorted(((sum(w in snap['text'].lower() for w in words), snap) for snap in snapshots), key=lambda t: -t[0])
    picks = sorted((snap for sc, snap in scored[:3] if sc >= 2), key=lambda snap: snap['seq'])
    out = []
    for snap in picks:
        t = snap['text']
        out.append(f"After step {snap['seq']} ({snap['intent'][:60]}) the page at {snap['url']} showed:\n" + (t if len(t) <= 2400 else t[:1200] + ' ... ' + t[-1200:]))
    return "\n\n".join(out)


def _prompt(statement: str, journey: str, hints: List[str], seen: Dict[str, Any], trail: List[str], left: int, earlier: str = "") -> str:
    elements = "\n".join(f"[{c.id}] <{c.tag}> {c.label!r}" + (" [DISABLED]" if c.disabled else "") for c in seen["candidates"]) or "(no interactive elements)"
    return (
        f"Statement to verify: {statement}\n"
        + (f"What the journey was doing: {journey}\n" if journey else "")
        + ("Known traps in this app:\n" + "\n".join(f"- {h}" for h in hints[:3]) + "\n" if hints else "")
        + f"\nWhat you did so far:\n" + ("\n".join(trail) if trail else "(nothing yet)")
        + f"\n\nActions left: {left}" + (" (answer now)" if left <= 0 else "")
        + (f"\nEarlier screens of this journey (what the page showed after those steps):\n{earlier}\n" if earlier else "")
        + f"\nPage: {seen['url']}\nTitle: {seen['title']}\n\nAccessibility tree:\n{seen['aria'] or '(unavailable)'}\n\n"
        + f"Visible text (excerpt):\n{seen['text']}\n\nInteractive elements:\n{elements}"
    )


async def verify_live(client: Any, page: Page, statement: str, journey: str = "", hints: Optional[List[str]] = None,
                      examples: Optional[List[Dict[str, Any]]] = None, console_logs: Optional[List[Dict[str, Any]]] = None,
                      state_js: Optional[str] = None, max_actions: Optional[int] = None,
                      network_calls: Optional[List[Dict[str, Any]]] = None,
                      snapshots: Optional[List[Dict[str, Any]]] = None) -> Optional[Verdict]:
    """A Verdict from working on the live page, or None when the evidence stays inconclusive."""
    hints = hints or []
    limit = settings.verify_max_actions if max_actions is None else max_actions
    system = with_charter(SYSTEM)
    if examples:
        from qagent.decision.fewshot import render_examples
        system += "\n\nHow to reason about tricky situations:\n" + render_examples(examples)
    started = time.perf_counter()
    start_url, moved = page.url, 0
    executor = BrowserExecutor(page)
    downloads: List[str] = []
    on_download = lambda d: downloads.append(d.suggested_filename)  # noqa: E731
    page.on("download", on_download)
    trail: List[str] = []
    nudged = False
    in_tok = out_tok = 0
    cost = 0.0
    verdict: Optional[Verdict] = None
    try:
        for turn in range(limit + 2):
            left = limit - len([t for t in trail if t.startswith("-")])
            seen = await _look(page)
            out = await client.converse_tool(system, _prompt(statement, journey, hints, seen, trail, left, _earlier(statement, snapshots or [])), VERIFY_TOOL,
                                             max_tokens=500, images=[seen["shot"]] if seen["shot"] else None)
            usage = out.get("usage", {})
            in_tok += usage.get("inputTokens", 0)
            out_tok += usage.get("outputTokens", 0)
            cost += usage_cost(usage)
            a = out["input"]
            action, why = a.get("action"), str(a.get("reasoning", "")).strip()
            if action == "answer" and not trail and not nudged and BEHAVIOUR.search(statement):
                nudged = True   # a statement about behaviour needs evidence from doing it
                trail.append("(you answered without trying anything. The statement is about behaviour: do it first (click or type), then answer)")
                continue
            if action == "answer" or left <= 0:
                v = a.get("verdict") if action == "answer" else "inconclusive"
                if v in ("holds", "does_not_hold", "true", "false"):
                    holds = v in ("holds", "true")
                    conf = max(0.0, min(1.0, float(a.get("confidence", 0.7))))
                    verdict = Verdict(holds, conf if holds else 1 - conf, "claude", conf,
                                      f"[checked on the live page] {why}", model_version=client.model_id)
                break
            cursor, net_cursor = len(console_logs or []), len(network_calls or [])
            downloads.clear()
            note = ""
            if action == "back":
                try:
                    await page.go_back(timeout=5000)
                    moved = max(0, moved - 1)
                    note = f"went back to {page.url}"
                except Exception as exc:
                    note = f"could not go back ({type(exc).__name__})"
            else:
                target = next((c for c in seen["candidates"] if c.id == a.get("target_id")), None)
                if target is None:
                    note = f"there is no element [{a.get('target_id')}]"
                elif action == "type":
                    if target.action_type != "fill":
                        note = f"[{target.id}] {target.label!r} is not a text field"
                    else:
                        res = await executor.execute(target, str(a.get("text", "")))
                        await wait_dom_stable(page, quiet_ms=300, max_ms=2000)
                        note = f"typed {str(a.get('text', ''))[:40]!r} into [{target.id}] {target.label!r}" + (f": it failed ({res['error']})" if res["status"] != "success" else "")
                elif action == "hover":
                    try:
                        loc = await executor._locate(target)
                        if loc is None:
                            raise RuntimeError("element not found")
                        await loc.hover(timeout=3000)
                        note = f"hovered [{target.id}] {target.label!r}"
                    except Exception as exc:
                        note = f"hover on [{target.id}] {target.label!r} failed: {str(exc).splitlines()[0][:100]}"
                else:
                    before = page.url
                    res = await executor.execute(target)
                    await wait_dom_stable(page, quiet_ms=300, max_ms=2500)
                    if page.url != before:
                        moved += 1
                    note = (f"clicked [{target.id}] {target.label!r}: " + (f"it failed ({res['error']})" if res["status"] != "success"
                            else f"URL {'changed to ' + page.url if page.url != before else 'did not change'}"))
            extra = []
            if state_js:
                try:
                    alerts = (await page.evaluate(state_js)).get("alerts") or []
                    if alerts:
                        extra.append("page shows: " + " | ".join(alerts)[:200])
                except Exception:
                    pass
            await page.wait_for_timeout(300)   # a download or request started by the action may land just after it
            if downloads:
                extra.append("a file download started: " + ", ".join(downloads[:3]))
            requests = [f"{c['method']} {c['status']} {c['url'].split('?')[0][-70:]}" for c in (network_calls or [])[net_cursor:]
                        if c.get("is_api") or c["status"] >= 400]
            if requests:
                extra.append("requests: " + "; ".join(requests[:5]))
            elif network_calls is not None and action in ("click",):
                extra.append("no server requests were made")
            errors = [e["text"][:100] for e in (console_logs or [])[cursor:] if e.get("type") in ("error", "pageerror")]
            if errors:
                extra.append("console errors: " + "; ".join(errors[:3]))
            trail.append(f"- {note}" + (f" ({'; '.join(extra)})" if extra else "") + (f" [you said: {why}]" if why else ""))
    finally:
        page.remove_listener("download", on_download)
        for _ in range(min(moved, 5)):   # leave the page where the journey ended, for the next expectation
            if page.url == start_url:
                break
            try:
                await page.go_back(timeout=3000)
            except Exception:
                break
    if verdict is not None:
        verdict.latency_ms = (time.perf_counter() - started) * 1000.0
        verdict.input_tokens, verdict.output_tokens, verdict.cost_usd = in_tok, out_tok, cost
    return verdict
