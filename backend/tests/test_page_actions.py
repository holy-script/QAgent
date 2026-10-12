"""Dropdowns and page actions that are not clicks: choosing the option, scroll, wait, go back, press a key."""
from urllib.parse import quote

import pytest

from qagent.browser.executor import BrowserExecutor
from qagent.browser.extractor import EXTRACTOR_JS
from qagent.browser.sandbox import BrowserSandbox
from qagent.browser.selecting import choose_option, parse_utility, run_utility
from qagent.domain.schemas import CandidateAction

OPTIONS = ["— select column —", "date", "month_label", "ecosystem_id", "ecosystem_name", "product", "trx"]


def test_the_option_a_step_asks_for():
    pick = lambda intent, label="DATE / TIME PERIOD", data=None: choose_option(intent, label, OPTIONS, data)  # noqa: E731
    assert pick("Select date in the DATE / TIME PERIOD dropdown") == "date"
    assert pick("Select ecosystem_name in the REGION / ECOSYSTEM dropdown", "REGION / ECOSYSTEM") == "ecosystem_name"
    assert pick("Select 'trx' from the Volume dropdown", "VOLUME") == "trx"
    assert pick("Set Volume to trx", "VOLUME") == "trx"
    assert pick("Choose the product column", "PRODUCT / BRAND") == "product"                       # longest mention, label words removed
    assert pick("Pick one", "VOLUME", {"volume": "trx"}) == "trx"                                    # from the journey's test data
    assert pick("Select something else in the dropdown") is None


def test_page_actions_are_recognised():
    assert parse_utility("Scroll down to see the validation results") == "@scroll:down"
    assert parse_utility("Scroll up") == "@scroll:up" and parse_utility("Scroll to the top of the page") == "@scroll:top"
    assert parse_utility("Scroll to the bottom") == "@scroll:bottom"
    assert parse_utility("Wait for the file parsing to complete") == "@wait"
    assert parse_utility("Go back") == "@back" and parse_utility("Press Escape") == "@press:Escape"
    assert parse_utility("Press the Enter key") == "@press:Enter" and parse_utility("Press Page Down") == "@press:PageDown"
    assert parse_utility("Click Sign in") is None and parse_utility("Press Save") is None and parse_utility("Scrolling gallery") is None


PAGE = ("<meta charset=utf-8><label>Volume<select id=v><option>— select column —</option><option>date</option><option>trx</option></select></label>"
        "<div style='height:3000px'>tall</div><button id=end onclick=\"document.title='keyed'\">End</button>"
        "<script>document.addEventListener('keydown', e => { if (e.key === 'Escape') document.title = 'escaped'; });</script>")


@pytest.mark.asyncio
async def test_a_dropdown_is_found_chosen_and_the_page_actions_run():
    sb = BrowserSandbox(headless=True)
    page = await sb.start()
    try:
        await page.goto("data:text/html," + quote(PAGE))
        found = [CandidateAction.model_validate(c) for c in await page.evaluate(EXTRACTOR_JS)]
        sel = next(c for c in found if c.action_type == "select")
        assert sel.label.startswith("Volume") and sel.options == ["— select column —", "date", "trx"] and sel.tag == "select"
        assert (await BrowserExecutor(page).execute(sel, "trx"))["status"] == "success"
        assert await page.eval_on_selector("#v", "e => e.value") == "trx"

        assert await run_utility(page, "@scroll:down") == "Scrolled down" and await page.evaluate("window.scrollY") > 0
        await run_utility(page, "@scroll:top")
        assert await page.evaluate("window.scrollY") == 0
        await run_utility(page, "@press:Escape")
        assert await page.title() == "escaped"
        assert await run_utility(page, "@wait") == "Waited for the page to settle"
    finally:
        await sb.stop()


def test_allowed_hosts_accept_a_domain_wildcard_and_web_fonts():
    sb = BrowserSandbox(headless=True, allowed_hosts=["app.example.com", "*.sslip.io"])
    assert sb._host_allowed("https://app.example.com/x") and sb._host_allowed("https://abc.1.2.3.4.sslip.io/api")
    assert sb._host_allowed("https://fonts.gstatic.com/f.woff2") and not sb._host_allowed("https://evil.example.org/")
    assert not sb._host_allowed("https://sslip.io/") and sb._host_allowed("data:text/plain,hi")


@pytest.mark.asyncio
async def test_charts_and_repeated_labels_do_not_break_reading_the_page():
    """SVG chart parts have no innerText: reading a page with a clickable chart and two same-named buttons must still work."""
    html = ("<svg width=200 height=100><g style='cursor:pointer'><rect width=50 height=50></rect></g></svg>"
            "<div><button>Edit</button> first row</div><div><button>Edit</button> second row</div>")
    sb = BrowserSandbox(headless=True)
    page = await sb.start()
    try:
        await page.goto("data:text/html," + quote(html))
        found = [CandidateAction.model_validate(c) for c in await page.evaluate(EXTRACTOR_JS)]
        labels = [c.label for c in found]
        assert any("first row" in lab for lab in labels) and any("second row" in lab for lab in labels)
        assert all(c.tag != "g" and c.tag != "rect" for c in found)
    finally:
        await sb.stop()
