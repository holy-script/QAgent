"""Saved sign-in details, the shared sign-in session, failed-sign-in detection and what the page showed after a step."""
import io
import json
import zipfile
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlmodel import select

from qagent.api.seed import DEMO_APP_ID
from qagent.domain import models as m
from qagent.domain.runspec import FlowSpec, RunSpec
from qagent.domain.schemas import CandidateAction, RunMode
from qagent.decision.stub import StubDecider
from qagent.engine.graph import EngineRunner, MissingValue, resolve_fill_value
from qagent.engine.secrets import SecretMasker
from qagent.storage import vault
from qagent.storage.persistence_sink import PersistenceSink
from test_lifecycle import api  # noqa: F401  (fixture)

SECRETS = {"username": "admin", "password": "s3cret-pass"}
SIGN_IN = ["Open /login", "Enter the username", "Enter the password", "Click Sign in"]


def cand(label, input_type="text"):
    return CandidateAction(id=1, tag="input", selector='[data-qagent-id="1"]', label=label, action_type="fill", input_type=input_type)


# ---- what to type ----------------------------------------------------------------------

def test_a_field_gets_the_saved_detail_that_matches_its_name_and_never_an_invented_value():
    f = lambda intent, c, td=None, sec=SECRETS: resolve_fill_value(intent, c, td or {}, sec)  # noqa: E731
    assert f("Enter the username", cand("Enter your username")) == "admin"
    assert f("Enter the password", cand("Enter your password", "password")) == "s3cret-pass"
    assert f("Fill the second box", cand("", "password")) == "s3cret-pass"                    # a password field uses the saved password
    assert f("Enter the password", cand("Enter your password", "password"), {"password": "wrong"}) == "wrong"   # a plan's own value (an edge case) wins
    assert f('Enter "{{password}}" in the password field', cand("x", "password")) == "s3cret-pass"        # explicit reference
    assert f("Enter the password", cand("pw", "password"), {"password": "{{password}}"}) == "s3cret-pass"
    assert f("Enter the password", cand("pw", "password"), {"password": "<fill in>"}) == "s3cret-pass"    # a placeholder yields to the saved detail
    with pytest.raises(MissingValue):
        f("Enter the password", cand("pw", "password"), {"password": "<fill in>"}, sec={})            # nothing saved: say so, do not type the placeholder
    with pytest.raises(MissingValue):
        f('Enter "{{token}}"', cand("x"))
    assert f("Enter the coupon", cand("coupon")) == "test"                                           # unchanged default for unrelated fields


# ---- credentials API -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_credentials_are_stored_encrypted_and_secrets_are_never_shown_again(api: AsyncClient):  # noqa: F811
    base = f"/apps/{DEMO_APP_ID}/credentials"
    assert (await api.get(base)).json() == []
    first = (await api.put(f"{base}/username", json={"value": "admin"})).json()
    assert (first["name"], first["secret"], first["value"]) == ("username", False, "admin") and first["updated_at"]
    r = await api.put(f"{base}/password", json={"value": "s3cret-pass"})
    assert r.status_code == 200 and r.json()["secret"] is True and r.json()["value"] is None
    listed = {c["name"]: c for c in (await api.get(base)).json()}
    assert listed["password"]["value"] is None and listed["username"]["value"] == "admin"
    assert "s3cret-pass" not in (await api.get(base)).text

    async with api.sessions() as s:
        row = (await s.execute(select(m.AppCredential).where(m.AppCredential.name == "password"))).scalar_one()
        assert "s3cret-pass" not in row.ciphertext and vault.decrypt(row.ciphertext) == "s3cret-pass"
    await api.put(f"{base}/PASSWORD", json={"value": "changed-pass"})                     # same name (any case) replaces
    assert len((await api.get(base)).json()) == 2

    assert (await api.put(f"{base}/1bad", json={"value": "x"})).status_code == 422
    assert (await api.put(f"{base}/token", json={"value": ""})).status_code == 422
    assert (await api.delete(f"{base}/username")).status_code == 200 and (await api.delete(f"{base}/username")).status_code == 404
    assert (await api.get("/apps/nope/credentials")).status_code == 404
    assert vault.decrypt("not-a-token") is None


# ---- masking ---------------------------------------------------------------------------

def test_the_masker_hides_every_form_of_a_secret(tmp_path: Path):
    mk = SecretMasker({"password": "p@ss w0rd!", "tiny": "ab"})
    assert not SecretMasker({"x": "abc"})                                       # too short to mask safely
    assert mk.text("sent p@ss w0rd! ok") == "sent [hidden] ok"
    assert mk.text("q=p%40ss%20w0rd%21") == "q=[hidden]" and mk.text("q=p%40ss+w0rd%21") == "q=[hidden]"
    assert mk.text('{"password": "p@ss w0rd!"}') == '{"password": "[hidden]"}'
    assert mk.obj({"a": ["x p@ss w0rd!"], "n": 3}) == {"a": ["x [hidden]"], "n": 3}
    assert mk.data(b"..p@ss w0rd!..") == b"..[hidden].."
    z = tmp_path / "trace.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("trace.network", 'POST {"password":"p@ss w0rd!"}')
        zf.writestr("resources/shot.jpeg", b"p@ss w0rd!")                   # binary entries are left alone
    assert mk.scrub_zip(z) == 1
    with zipfile.ZipFile(z) as zf:
        assert b"p@ss" not in zf.read("trace.network") and zf.read("resources/shot.jpeg") == b"p@ss w0rd!"


# ---- running against the demo shop's sign-in page -------------------------------------

_n = iter(range(10_000))


async def run(url, mem_sessions, uploader, flows, secrets=None):
    spec = RunSpec(run_id=f"c{next(_n)}", app_id="app-demo", base_url=url, mode=RunMode.STUB, flows=flows, reset_path="/__reset",
                   secrets=secrets if secrets is not None else dict(SECRETS))
    sink = PersistenceSink(spec.run_id, session_factory=mem_sessions)
    result = await EngineRunner(spec, StubDecider(), sink, uploader=uploader).run()
    async with mem_sessions() as s:
        events = (await s.execute(select(m.EventRecord).where(m.EventRecord.run_id == spec.run_id).order_by(m.EventRecord.seq))).scalars().all()
        findings = (await s.execute(select(m.FindingRecord).where(m.FindingRecord.run_id == spec.run_id))).scalars().all()
    return result, events, findings


def flow_end(events, key):
    return next(e.payload for e in events if e.type == "flow.finished" and e.payload["flow_key"] == key)


def urls_after_steps(events, key):
    return [e.payload["url"] for e in events if e.type == "step.verified" and e.payload["flow_key"] == key]


@pytest.mark.asyncio
async def test_a_journey_signs_in_with_saved_details_and_the_password_goes_nowhere_else(shop, mem_sessions, uploader):
    url, _ = shop
    flow = FlowSpec(key="sign-in", steps=[*SIGN_IN, "Open /account"], severity="high")
    result, events, findings = await run(url, mem_sessions, uploader, [flow])
    assert flow_end(events, "sign-in")["failure_reason"] is None and urls_after_steps(events, "sign-in")[-1].endswith("/account")
    assert findings == []
    # nothing recorded anywhere contains the password: events, stored files, check results, logs
    blob = json.dumps([e.payload for e in events], default=str)
    assert "s3cret-pass" not in blob
    assert uploader.items, "files were uploaded"
    for item in uploader.items:
        data, ctype, key = item["data"], item["content_type"], item["key"]
        if ctype.startswith("text/") or "json" in ctype:
            assert b"s3cret-pass" not in data, key
        if key.endswith("trace.zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                assert all(b"s3cret-pass" not in zf.read(n) for n in zf.namelist() if n.endswith((".trace", ".network")))


@pytest.mark.asyncio
async def test_a_failed_sign_in_stops_the_journey_and_says_so(shop, mem_sessions, uploader):
    url, _ = shop
    flow = FlowSpec(key="sign-in", steps=[*SIGN_IN, "Open /account", "Click Sign in"], test_data={"password": "wrong-pass"}, severity="high")
    _, events, findings = await run(url, mem_sessions, uploader, [flow])
    reason = flow_end(events, "sign-in")["failure_reason"]
    assert reason.startswith("sign-in failed:") and "Invalid username or password" in reason     # the real cause, with the page's own message
    assert len(urls_after_steps(events, "sign-in")) == 4                                          # nothing after the failed sign-in ran
    assert "signin:sign-in" in [f.check_key for f in findings]            # (the 401 from the login call is reported too)
    verified = [e.payload for e in events if e.type == "step.verified"][-1]
    assert verified["observed"]["signin_form_visible"] and verified["observed"]["alerts"] == ["Invalid username or password"]


@pytest.mark.asyncio
async def test_a_setup_journey_signs_in_once_and_the_others_start_signed_in(shop, mem_sessions, uploader):
    url, _ = shop
    setup = FlowSpec(key="sign-in", role="setup", steps=SIGN_IN, severity="high")
    other = FlowSpec(key="account", steps=["Open /account"], severity="high")
    other2 = FlowSpec(key="account-again", steps=["Open /account"], severity="high")
    _, events, _ = await run(url, mem_sessions, uploader, [other, setup, other2])        # order in the plan does not matter
    for key in ("account", "account-again"):
        assert urls_after_steps(events, key) == [f"{url}/account"], key                   # no redirect to /login: already signed in
        assert flow_end(events, key)["failure_reason"] is None
    starts = [e.payload["flow_key"] for e in events if e.type == "flow.started"]
    assert starts[0] == "sign-in"                                                          # the sign-in ran first


@pytest.mark.asyncio
async def test_when_the_setup_journey_fails_the_others_are_not_run(shop, mem_sessions, uploader):
    url, _ = shop
    setup = FlowSpec(key="sign-in", role="setup", steps=SIGN_IN, test_data={"password": "wrong-pass"}, severity="high")
    other = FlowSpec(key="account", steps=["Open /account"], severity="high")
    _, events, _ = await run(url, mem_sessions, uploader, [setup, other])
    assert flow_end(events, "sign-in")["failure_reason"].startswith("sign-in failed")
    skipped = flow_end(events, "account")
    assert skipped["status"] == "failed" and skipped["failure_reason"].startswith("not run: the sign-in journey failed first") and skipped["step_count"] == 0


@pytest.mark.asyncio
async def test_a_step_that_cannot_proceed_names_what_the_page_showed_last(shop, mem_sessions, uploader):
    url, _ = shop
    # the second "Click Sign in" has nothing to click once the first one failed to change the page: say why, not just "no element"
    flow = FlowSpec(key="sign-in", steps=[*SIGN_IN[:3], "Click Sign in", "Click the missing thing"], test_data={"password": "wrong-pass"}, severity="high")
    _, events, _ = await run(url, mem_sessions, uploader, [flow])
    assert "sign-in failed" in flow_end(events, "sign-in")["failure_reason"]


@pytest.mark.asyncio
async def test_missing_test_data_is_reported_instead_of_typed(shop, mem_sessions, uploader):
    url, _ = shop
    flow = FlowSpec(key="sign-in", steps=SIGN_IN, test_data={"username": "<fill in>", "password": "<fill in>"}, severity="high")
    _, events, _ = await run(url, mem_sessions, uploader, [flow], secrets={})
    assert "still <fill in>: fill it in, or save it under Settings > Sign-in details" in flow_end(events, "sign-in")["failure_reason"]


@pytest.mark.asyncio
async def test_what_someone_typed_is_never_used_as_a_fields_name():
    from playwright.async_api import async_playwright
    from qagent.browser.extractor import EXTRACTOR_JS
    from qagent.browser.launcher import launch_chromium
    async with async_playwright() as pw:
        browser, _ = await launch_chromium(pw, True)
        page = await browser.new_page()
        await page.set_content("<input id=a value='typed-secret'><input type=submit value='Sign in'>")
        labels = [c["label"] for c in await page.evaluate(EXTRACTOR_JS)]
        assert "typed-secret" not in labels and "Sign in" in labels
        await browser.close()
