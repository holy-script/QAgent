"""Which option a step picks from a dropdown, and the page actions that are not clicks (scroll, wait, back, press a key)."""
import re
from typing import Any, Dict, List, Optional

_SELECT_FROM = re.compile(r"^\s*(?:select|choose|pick|set)\s+(?:the\s+)?[\"'`]?(.+?)[\"'`]?\s+(?:in|from|for|as|on|under)\b", re.IGNORECASE)
_SELECT_TO = re.compile(r"\b(?:to|as)\s+[\"'`]?([^\"'`]+?)[\"'`]?\s*$", re.IGNORECASE)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def choose_option(intent: str, label: str, options: List[str], test_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """The dropdown option this step asks for, or None. Order: the option named first in "Select <option> in <dropdown>", the
    option named last in "Set <dropdown> to <option>", a value from the journey's test data named like the dropdown, then the
    longest option mentioned anywhere in the step once the dropdown's own name is taken out of it."""
    by_norm = {_norm(o): o for o in options if _norm(o)}
    for rx in (_SELECT_FROM, _SELECT_TO):
        m = rx.search(intent)
        if m and _norm(m.group(1)) in by_norm:
            return by_norm[_norm(m.group(1))]
    lab = _norm(label.split(" (")[0])
    for key, value in (test_data or {}).items():
        if _norm(str(value)) in by_norm and (_norm(key) in lab or lab in _norm(key) or _norm(key) in _norm(intent)):
            return by_norm[_norm(str(value))]
    rest = f" {_norm(intent)} "
    for part in lab.split():
        rest = rest.replace(f" {part} ", " ")
    hits = [o for n, o in by_norm.items() if f" {n} " in rest] or [o for n, o in by_norm.items() if f" {n} " in f" {_norm(intent)} "]
    return max(hits, key=lambda o: len(_norm(o))) if hits else None


_SCROLL = re.compile(r"^\s*scroll\b(?P<rest>.*)$", re.IGNORECASE)
_WAIT = re.compile(r"^\s*(?:wait|pause)\b", re.IGNORECASE)
_BACK = re.compile(r"^\s*(?:go back|navigate back|press (?:the )?back(?: button)?|browser back)\s*$", re.IGNORECASE)
_PRESS = re.compile(r"^\s*press (?:the )?(?P<key>enter|return|escape|esc|tab|space|arrow (?:up|down|left|right)|page ?(?:up|down)|home|end)\b", re.IGNORECASE)
_KEYS = {"enter": "Enter", "return": "Enter", "escape": "Escape", "esc": "Escape", "tab": "Tab", "space": "Space",
         "home": "Home", "end": "End", "pageup": "PageUp", "pagedown": "PageDown", "arrow up": "ArrowUp",
         "arrow down": "ArrowDown", "arrow left": "ArrowLeft", "arrow right": "ArrowRight"}


def parse_utility(intent: str) -> Optional[str]:
    """'Scroll down...', 'Wait for...', 'Go back', 'Press Escape' are done by the engine itself, with no element to choose.
    Returns "@scroll:down|up|top|bottom", "@wait", "@back" or "@press:<Key>"; None for an ordinary step."""
    m = _SCROLL.match(intent)
    if m:
        rest = m.group("rest").lower()
        if re.search(r"\b(top|up|above)\b", rest) and "down" not in rest:
            return "@scroll:top" if "top" in rest else "@scroll:up"
        return "@scroll:bottom" if "bottom" in rest or "end of" in rest else "@scroll:down"
    if _WAIT.match(intent):
        return "@wait"
    if _BACK.match(intent):
        return "@back"
    m = _PRESS.match(intent)
    if m:
        return "@press:" + _KEYS[re.sub(r"\s+", " ", m.group("key").lower()).replace("page ", "page")]
    return None


async def run_utility(page: Any, target: str) -> str:
    """Performs one of the actions above; returns a short description of what was done."""
    kind, _, arg = target[1:].partition(":")
    if kind == "scroll":
        if arg in ("top", "bottom"):
            await page.evaluate("(to) => { const e = document.scrollingElement || document.body; e.scrollTo(0, to === 'top' ? 0 : e.scrollHeight); }", arg)
        else:
            await page.mouse.move(640, 450)
            await page.mouse.wheel(0, -700 if arg == "up" else 700)
        await page.wait_for_timeout(300)
        return f"Scrolled {arg}"
    if kind == "wait":
        from qagent.browser.wait_frames import wait_dom_stable
        await page.wait_for_timeout(1000)
        await wait_dom_stable(page, quiet_ms=500, max_ms=4000)
        return "Waited for the page to settle"
    if kind == "back":
        await page.go_back(timeout=8000)
        return "Went back"
    if kind == "press":
        await page.keyboard.press(arg)
        return f"Pressed {arg}"
    raise ValueError(f"unknown page action {target}")
