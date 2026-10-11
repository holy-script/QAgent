import pytest

from qagent.browser import launcher
from qagent.browser.launcher import BrowserUnavailable, launch_chromium


class FakeChromium:
    def __init__(self, working):
        self.working, self.calls = working, []

    async def launch(self, **kw):
        key = kw.get("executable_path") or kw.get("channel") or "bundled"
        self.calls.append(key)
        if key not in self.working:
            raise RuntimeError(f"Executable doesn't exist for {key}\nmore")
        return key  # stands in for a Browser


class FakePW:
    def __init__(self, working):
        self.chromium = FakeChromium(working)


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    monkeypatch.setattr(launcher.settings, "browser_path", None)
    monkeypatch.setattr(launcher.settings, "browser_channel", None)


@pytest.mark.asyncio
async def test_prefers_bundled_chromium():
    pw = FakePW({"bundled", "chrome"})
    browser, source = await launch_chromium(pw)
    assert (browser, source) == ("bundled", "playwright-chromium") and pw.chromium.calls == ["bundled"]


@pytest.mark.asyncio
async def test_falls_back_to_installed_chrome_when_bundled_is_missing():
    pw = FakePW({"chrome"})
    browser, source = await launch_chromium(pw)
    assert source == "fallback channel chrome" and pw.chromium.calls == ["bundled", "chrome"]


@pytest.mark.asyncio
async def test_explicit_executable_wins_and_never_falls_back(monkeypatch):
    monkeypatch.setattr(launcher.settings, "browser_path", "/opt/chromium")
    ok = FakePW({"/opt/chromium", "bundled"})
    assert (await launch_chromium(ok))[1] == "executable /opt/chromium" and ok.chromium.calls == ["/opt/chromium"]
    bad = FakePW({"bundled", "chrome"})
    with pytest.raises(BrowserUnavailable, match="QAGENT_BROWSER_PATH"):
        await launch_chromium(bad)
    assert bad.chromium.calls == ["/opt/chromium"]


@pytest.mark.asyncio
async def test_requested_channel_is_used_instead_of_bundled(monkeypatch):
    monkeypatch.setattr(launcher.settings, "browser_channel", "msedge")
    pw = FakePW({"msedge", "bundled"})
    assert (await launch_chromium(pw))[1] == "channel msedge" and pw.chromium.calls == ["msedge"]


@pytest.mark.asyncio
async def test_clear_error_when_nothing_works():
    with pytest.raises(BrowserUnavailable) as err:
        await launch_chromium(FakePW(set()))
    assert "make browsers" in str(err.value) and "bundled" in str(err.value).lower()
