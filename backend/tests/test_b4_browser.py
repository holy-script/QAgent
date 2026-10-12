import pytest
from qagent.browser.extractor import extract_candidates_from_html


def test_extract_candidates_from_sample_html():
    sample_html = """
    <html>
        <body>
            <header>
                <a href="/home" id="nav-home">Home</a>
                <a href="/cart" data-testid="cart-link">Cart (0)</a>
            </header>
            <main>
                <h1>Products</h1>
                <div class="product">
                    <span>Wireless Headphones - $99</span>
                    <button id="add-headphones" data-testid="add-btn-1">Add to Cart</button>
                </div>
                <div class="product">
                    <span>Mechanical Keyboard - $149</span>
                    <button class="btn primary" data-testid="add-btn-2">Add to Cart</button>
                </div>
                <form>
                    <input type="text" name="coupon" placeholder="Coupon Code" />
                    <button type="submit">Apply Coupon</button>
                </form>
            </main>
        </body>
    </html>
    """

    candidates = extract_candidates_from_html(sample_html)
    assert len(candidates) >= 5
    assert len(candidates) <= 40

    # Ensure IDs are 1-based sequential integers
    assert [c.id for c in candidates] == list(range(1, len(candidates) + 1))

    # Verify attributes
    labels = [c.label for c in candidates]
    assert any("Home" in l for l in labels)
    assert any("Add to Cart" in l for l in labels)
    assert any(c.tag == "input" and c.action_type == "fill" for c in candidates)


@pytest.mark.asyncio
async def test_two_fields_with_the_same_class_each_get_their_own_text():
    """Regression: on a login page both inputs matched `input.w-full`, so the password was typed into the username field."""
    from playwright.async_api import async_playwright
    from qagent.browser.executor import BrowserExecutor
    from qagent.browser.extractor import EXTRACTOR_JS
    from qagent.browser.launcher import launch_chromium
    from qagent.domain.schemas import CandidateAction

    html = ("<input class='w-full' placeholder='Enter your username' autocomplete='username'>"
            "<input class='w-full' type='password' placeholder='Enter your password'>"
            "<button class='w-full' onclick=\"document.title=document.querySelectorAll('input')[1].value\">Sign in</button>")
    async with async_playwright() as pw:
        browser, _ = await launch_chromium(pw, True)
        page = await browser.new_page()
        await page.set_content(html)
        cands = [CandidateAction.model_validate(c) for c in await page.evaluate(EXTRACTOR_JS)]
        user, pwd, login = cands
        assert user.selector != pwd.selector and user.alt_selector == pwd.alt_selector == "input.w-full"   # the page's own selector is ambiguous
        ex = BrowserExecutor(page)
        assert (await ex.execute(user, "admin"))["status"] == "success"
        assert (await ex.execute(pwd, "s3cret!"))["status"] == "success"
        values = await page.evaluate("[...document.querySelectorAll('input')].map(i => i.value)")
        assert values == ["admin", "s3cret!"]
        assert (await ex.execute(login))["status"] == "success" and await page.title() == "s3cret!"

        # a field that rejects the typed text is reported, not ignored
        await page.set_content("<input id=a class='x'><script>a.addEventListener('input', () => a.value = '')</script>")
        bad = CandidateAction.model_validate((await page.evaluate(EXTRACTOR_JS))[0])
        res = await ex.execute(bad, "hello")
        assert res["status"] == "failed" and "did not keep the text" in res["error"]

        # two alike fields and no stamp: refuse to guess
        await page.set_content("<input class='x'><input class='x'>")
        ambiguous = CandidateAction(id=1, tag="input", selector="input.x", label="x", action_type="fill")
        res = await ex.execute(ambiguous, "v")
        assert res["status"] == "failed" and "exactly one field" in res["error"]
        await browser.close()
