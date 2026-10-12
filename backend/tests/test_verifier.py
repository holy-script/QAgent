"""The live verifier: expectations that need the page to be used are checked by working on the live browser."""
from urllib.parse import quote

import pytest

from qagent.browser.sandbox import BrowserSandbox
from qagent.checks.expectations import NEEDS_INTERACTION, run_expectation_live
from qagent.checks.ux_judged import Judge, Verdict
from qagent.checks.verifier import verify_live
from qagent.decision.ledger import TapedJudge

PAGE = ("<a href=\"#\" id=nav style='cursor:pointer' onclick=\"document.getElementById('out').textContent='opened';return false\">"
        "Open planner</a><div id=out>closed</div>"
    "<input id=amt value=1 aria-label=Amount>"
    "<div id=dbl>2</div><script>document.getElementById('amt').addEventListener('input', e => { document.getElementById('dbl').textContent = String(Number(e.target.value) * 2); });</script>")


class Script:
    """A scripted 'Claude': answers verify_step calls from a list and remembers what it was shown."""
    model_id = "fake"

    def __init__(self, answers):
        self.answers, self.prompts = list(answers), []

    async def converse_tool(self, system, user, tool, max_tokens=512, images=None, timeout=60.0):
        self.prompts.append(user)
        a = self.answers.pop(0) if self.answers else {"action": "answer", "verdict": "inconclusive", "reasoning": "out of answers"}
        return {"input": a, "usage": {"inputTokens": 400, "outputTokens": 40}}


def click(target, why="try it"):
    return {"action": "click", "target_id": target, "reasoning": why}


def answer(verdict, why="saw it"):
    return {"action": "answer", "verdict": verdict, "confidence": 0.9, "reasoning": why}


async def on_page():
    sb = BrowserSandbox(headless=True)
    page = await sb.start()
    await page.goto("data:text/html," + quote(PAGE))
    return sb, page


@pytest.mark.asyncio
async def test_the_verifier_tries_the_element_and_answers_from_what_happened():
    sb, page = await on_page()
    try:
        client = Script([click(1), answer("true", "clicking Open planner changed the page")])
        verdict = await verify_live(client, page, "Navigation elements are clickable and responsive")
        assert verdict.passed and verdict.cost_usd > 0 and verdict.input_tokens == 800
        assert "checked on the live page" in verdict.reasoning
        assert await page.inner_text("#out") == "opened"                       # it really clicked
        assert "clicked [1] 'Open planner'" in client.prompts[1]               # and was told what happened
        assert "Accessibility tree" in client.prompts[0] and "Open planner" in client.prompts[0]
    finally:
        await sb.stop()


@pytest.mark.asyncio
async def test_inconclusive_or_endless_trying_reports_nothing():
    sb, page = await on_page()
    try:
        assert await verify_live(Script([answer("inconclusive")]), page, "x") is None
        assert await verify_live(Script([click(1)] * 10), page, "x", max_actions=2) is None   # forced to answer, never did
    finally:
        await sb.stop()


class Quick(Judge):
    """Quick one-shot judge with a fixed answer; the live verifier is the scripted client above."""
    def __init__(self, passes, client):
        super().__init__(None, client)
        self.passes, self.asked = passes, 0

    async def ask(self, question, page_text, screenshots=None, hints=None, examples=None):
        self.asked += 1
        return Verdict(self.passes, 0.9 if self.passes else 0.1, "claude", 0.9, "quick", model_version="fake")


@pytest.mark.asyncio
async def test_statements_about_things_working_go_straight_to_the_live_check():
    assert NEEDS_INTERACTION.search("All navigation elements are clickable and responsive")
    assert not NEEDS_INTERACTION.search("The page shows the forecast total of 120")
    sb, page = await on_page()
    try:
        judge = Quick(False, Script([click(1), answer("true")]))
        out = await run_expectation_live(judge, "f", 1, "All navigation elements are clickable", "high", [], "page", [], [], [], page)
        assert out.passed and judge.asked == 0                        # the quick judge was never needed
    finally:
        await sb.stop()


@pytest.mark.asyncio
async def test_a_quick_no_is_double_checked_live_before_it_is_reported():
    sb, page = await on_page()
    try:
        text = "The forecast total shows 120"
        out = await run_expectation_live(Quick(False, Script([answer("true", "the page does show it")])), "f", 1, text, "high", [], "page", [], [], [], page)
        assert out.passed                                             # the live check overruled the screenshot judgement
        out = await run_expectation_live(Quick(False, Script([answer("false", "no total anywhere")])), "f", 1, text, "high", [], "page", [], [], [], page)
        assert not out.passed and "no total anywhere" in out.actual
        assert await run_expectation_live(Quick(False, Script([answer("inconclusive")])), "f", 1, text, "high", [], "page", [], [], [], page) is None
        # a quick yes is accepted as it is
        judge = Quick(True, Script([]))
        assert (await run_expectation_live(judge, "f", 1, text, "high", [], "page", [], [], [], page)).passed
    finally:
        await sb.stop()


@pytest.mark.asyncio
async def test_the_live_verdict_is_on_the_tape_and_a_repeat_costs_nothing():
    sb, page = await on_page()
    sent = []

    async def emit(call):
        sent.append(call)
    try:
        live = TapedJudge(Quick(False, Script([click(1), answer("true")])))
        live.bind(emit)
        first = await live.verify("Is it clickable?", "page text", page)
        assert first.passed and sent[0]["purpose"] == "judge" and sent[0]["cost_usd"] > 0 and not sent[0]["replayed"]

        replay = TapedJudge(Quick(False, Script([])), tape={sent[0]["input_hash"]: sent[0]["response"]})
        replay.bind(emit)
        again = await replay.verify("Is it clickable?", "page text", page)
        assert again.passed and sent[1]["replayed"] and sent[1]["cost_usd"] == 0.0
        with pytest.raises(LookupError):                              # not recorded and nobody to ask: the caller falls back
            await TapedJudge(None, tape={}).verify("other", "page text", page)
    finally:
        await sb.stop()


@pytest.mark.asyncio
async def test_the_verifier_is_told_when_a_click_made_no_server_requests():
    sb, page = await on_page()
    try:
        client = Script([click(1), answer("false", "nothing was requested")])
        await verify_live(client, page, "The link loads data", network_calls=[])
        assert "no server requests were made" in client.prompts[1]
    finally:
        await sb.stop()


def type_into(target, text):
    return {"action": "type", "target_id": target, "text": text, "reasoning": "change the value and watch what else changes"}


@pytest.mark.asyncio
async def test_the_verifier_can_type_into_a_field_and_sees_earlier_screens():
    sb, page = await on_page()
    try:
        client = Script([type_into(2, "21"), answer("true", "the doubled value follows the input")])
        snaps = [{"seq": 4, "intent": "Click Confirm Mapping", "url": "https://x/upload", "text": "Validation 6/6 pass\n6 ecosystems · 52 months"},
                 {"seq": 9, "intent": "Click Proceed", "url": "https://x/forecast", "text": "Forecast screen only"}]
        verdict = await verify_live(client, page, "Validation shows 6/6 pass and 6 ecosystems", snapshots=snaps)
        assert verdict.passed and await page.inner_text("#dbl") == "42"                   # it really typed, and the page reacted
        assert "typed '21' into [2]" in client.prompts[1]
        assert "After step 4" in client.prompts[0] and "6/6 pass" in client.prompts[0] and "Forecast screen only" not in client.prompts[0]
    finally:
        await sb.stop()
