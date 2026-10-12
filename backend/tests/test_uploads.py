"""Upload steps: choosing the file, the app's test files API, and a real run against the demo shop's avatar page."""
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlmodel import select

from qagent.api.seed import DEMO_APP_ID
from qagent.browser import uploads
from qagent.checks.edge_cases import expand_flows, spec_items
from qagent.checks.ux_judged import Verdict
from qagent.decision.stub import StubDecider
from qagent.domain import models as m
from qagent.domain.runspec import RunSpec
from qagent.domain.schemas import RunMode
from qagent.engine.graph import EngineRunner
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.storage.objects import object_store
from qagent.storage.persistence_sink import PersistenceSink
from test_lifecycle import api  # noqa: F401  (fixture)

UPLOADS_MD = Path(__file__).parents[2] / "playbooks" / "uploads.md"
AVAILABLE = ["sample.png", "sample.txt", "invoice.pdf"]


def test_which_file_a_step_uploads():
    pick = lambda intent, label="Choose file (file upload)", data=None: uploads.choose_files(intent, label, data or {}, AVAILABLE)  # noqa: E731
    assert pick("Choose the avatar image", data={"file": "sample.txt"}) == ["sample.txt"]          # test data wins
    assert pick("Choose the avatar", data={"files": "invoice.pdf, sample.png"}) == ["invoice.pdf", "sample.png"]
    assert pick("Upload INVOICE.PDF as the invoice") == ["invoice.pdf"]                              # named in the step
    assert pick('Upload "report.docx"') == ["report.docx"]                                           # unknown: reported later
    assert pick("Choose the document", label="Resume (file upload, accepts .pdf)") == ["invoice.pdf"]  # field's accept list
    assert pick("Choose an image", label="Avatar (file upload, accepts image/*)") == ["sample.png"]
    assert pick("Attach something") == ["sample.png"]                                                # first available
    # a description instead of a file name is matched to the app's files by type and shared words
    files = ["genentech_portfolio_trx_dirty_v5.csv", "ocrevus_trx_data.csv", "sample.png", "sample.csv"]
    by = lambda value, key="file": uploads.choose_files("Upload the file", "Choose file (file upload, accepts .csv)", {key: value}, files)  # noqa: E731
    assert by("attached CSV file") == ["genentech_portfolio_trx_dirty_v5.csv"]                        # the app's own csv comes first
    assert by("the ocrevus data file") == ["ocrevus_trx_data.csv"]
    assert by("the dirty CSV", key="csv_file") == ["genentech_portfolio_trx_dirty_v5.csv"]
    assert by("ocrevus_trx_data.csv") == ["ocrevus_trx_data.csv"] and by("missing.csv") == ["missing.csv"]  # real names stay as asked
    assert pick("Attach something", data={}) and uploads.choose_files("x", "", {}, []) == []


def test_built_in_samples_are_real_files():
    assert uploads.BUILTIN["sample.png"][0].startswith(b"\x89PNG") and uploads.BUILTIN["sample.pdf"][0].startswith(b"%PDF")
    assert all(0 < len(b) < 2000 for b, _ in uploads.BUILTIN.values())
    assert uploads.guess_type("a.CSV") == "text/csv" and uploads.guess_type("noext") == "application/octet-stream"


@pytest.mark.asyncio
async def test_test_files_api(api: AsyncClient):  # noqa: F811
    listed = (await api.get(f"/apps/{DEMO_APP_ID}/files")).json()
    assert {f["name"] for f in listed} == set(uploads.BUILTIN) and all(f["builtin"] for f in listed)

    r = await api.post(f"/apps/{DEMO_APP_ID}/files", params={"name": "invoice.pdf"}, content=b"%PDF-1.4 hello")
    assert r.status_code == 201 and r.json()["size_bytes"] == 14 and r.json()["content_type"] == "application/pdf"
    again = await api.post(f"/apps/{DEMO_APP_ID}/files", params={"name": "INVOICE.pdf"}, content=b"%PDF-1.4 hello, longer")
    assert again.json()["id"] == r.json()["id"] and again.json()["size_bytes"] == 22      # same name replaces

    # an app's own file hides the built-in of the same name
    await api.post(f"/apps/{DEMO_APP_ID}/files", params={"name": "sample.png"}, content=b"\x89PNG custom")
    names = {f["name"]: f for f in (await api.get(f"/apps/{DEMO_APP_ID}/files")).json()}
    assert not names["sample.png"]["builtin"] and names["invoice.pdf"]["size_bytes"] == 22

    assert (await api.post(f"/apps/{DEMO_APP_ID}/files", params={"name": ".."}, content=b"x")).status_code == 422
    empty = await api.post(f"/apps/{DEMO_APP_ID}/files", params={"name": "e.txt"}, content=b"")   # allowed: "upload an empty file" is an edge case
    assert empty.status_code == 201 and empty.json()["size_bytes"] == 0
    await api.delete(f"/apps/{DEMO_APP_ID}/files/{empty.json()['id']}")
    big = b"x" * (uploads.MAX_FILE_BYTES + 1)
    assert (await api.post(f"/apps/{DEMO_APP_ID}/files", params={"name": "big.bin"}, content=big)).status_code == 413
    assert (await api.post("/apps/nope/files", params={"name": "a.txt"}, content=b"x")).status_code == 404

    fid = r.json()["id"]
    assert (await api.delete(f"/apps/{DEMO_APP_ID}/files/{fid}")).status_code == 200
    assert (await api.delete(f"/apps/{DEMO_APP_ID}/files/{fid}")).status_code == 404
    assert object_store.get_bytes(f"apps/{(await _app_id(api))}/files/{fid}/invoice.pdf") is None


async def _app_id(api):
    async with api.sessions() as s:
        return (await s.get(m.App, DEMO_APP_ID)).id


class AvatarJudge:
    """Says the page shows an error only if it does not claim the avatar was updated."""

    async def ask(self, question, page_text, screenshots=None, hints=None, examples=None):
        shows_error = "Avatar updated" not in page_text
        ok = shows_error if "error" in question.lower() else "Avatar updated" in page_text
        return Verdict(ok, 0.95 if ok else 0.05, "jev", 0.9, "fake")


async def run_uploads(url, mem_sessions, uploader, run_id, files=None, edge=True):
    parsed = parse_playbook_markdown(UPLOADS_MD.read_text())
    spec = RunSpec(run_id=run_id, app_id="app-demo", base_url=url, mode=RunMode.STUB, reset_path="/__reset",
                   flows=expand_flows(parsed, None, edge), files=files or {}, **spec_items(parsed))
    sink = PersistenceSink(run_id, session_factory=mem_sessions)
    await EngineRunner(spec, StubDecider(), sink, uploader=uploader, judge=AvatarJudge()).run()
    async with mem_sessions() as s:
        events = (await s.execute(select(m.EventRecord).where(m.EventRecord.run_id == run_id))).scalars().all()
        findings = (await s.execute(select(m.FindingRecord).where(m.FindingRecord.run_id == run_id))).scalars().all()
    uploaded = {e.payload["flow_key"]: e.payload["uploaded"] for e in events
                if e.type == "action.executed" and e.payload.get("uploaded")}
    return uploaded, findings, events


@pytest.mark.asyncio
async def test_a_run_uploads_the_chosen_file_and_catches_the_missing_validation(shop, mem_sessions, uploader):
    url, set_bugs = shop
    uploaded, findings, _ = await run_uploads(url, mem_sessions, uploader, "u1")
    assert uploaded["upload-avatar"][0]["name"] == "sample.png" and uploaded["upload-avatar"][0]["content_type"] == "image/png"
    assert uploaded["upload-avatar#EC-1"][0]["name"] == "sample.txt"       # the edge case swaps the file through test data
    # bug 6 is on: the shop accepted the text file, so the "error" expectation fails for the variant only
    assert [f.flow_key if hasattr(f, "flow_key") else f.check_key for f in findings] and any("EC-1" in f.check_key for f in findings)
    assert not any(f.check_key.startswith("expect:upload-avatar:") for f in findings)

    set_bugs(bug6=False)
    _, fixed, _ = await run_uploads(url, mem_sessions, uploader, "u2")
    assert fixed == []


@pytest.mark.asyncio
async def test_a_run_can_upload_the_apps_own_file_and_reports_a_missing_one(shop, mem_sessions, uploader, monkeypatch):
    url, set_bugs = shop
    set_bugs(bug6=False)
    key = "apps/app-demo/files/f1/mine.png"
    object_store.put_object(key, b"\x89PNG mine-bytes", "image/png")
    parsed_md = UPLOADS_MD.read_text().replace("file: sample.png", "file: mine.png")
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: parsed_md if self == UPLOADS_MD else open(self).read())
    uploaded, findings, _ = await run_uploads(url, mem_sessions, uploader, "u3", files={"mine.png": {"key": key, "content_type": "image/png"}}, edge=False)
    assert uploaded["upload-avatar"] == [{"name": "mine.png", "size": 15, "content_type": "image/png"}]

    missing = parsed_md.replace("file: mine.png", "file: nope.png")
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: missing if self == UPLOADS_MD else open(self).read())
    _, _, events = await run_uploads(url, mem_sessions, uploader, "u4", edge=False)
    logs = [e.payload for e in events if e.type == "log"] + [e.payload for e in events if e.type == "flow.finished"]
    assert any("nope.png" in str(p) for p in logs)
