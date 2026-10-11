import argparse
import asyncio
import uuid
from pathlib import Path

from qagent.decision.base import Decider
from qagent.config import settings
from qagent.decision.claude import ClaudeDecider
from qagent.decision.jev import JevDecider
from qagent.decision.stub import StubDecider
from qagent.checks.edge_cases import expand_flows, spec_items
from qagent.checks.ux_judged import Judge
from qagent.domain.runspec import RunSpec
from qagent.domain.schemas import RunMode
from qagent.engine.graph import EngineRunner
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.storage.checkpoint import open_checkpointer
from qagent.storage.persistence_sink import PersistenceSink
from qagent.storage.upload_queue import upload_queue

DEFAULT_PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "checkout.md"


def build_decider(mode: RunMode) -> Decider:
    if mode == RunMode.STUB:
        return StubDecider()
    if mode == RunMode.HYBRID:
        return JevDecider()
    if not settings.bedrock_api_key:
        raise SystemExit("baseline mode needs BEDROCK_API_KEY")
    return ClaudeDecider()


async def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QAgent CLI Runner")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument("--app", default="demo-shop", help="Target app slug")
    parser.add_argument("--mode", choices=["stub", "hybrid", "baseline"], default="stub", help="Execution mode")
    parser.add_argument("--url", default=None, help="Target base URL (default: the playbook's base_url)")
    parser.add_argument("--playbook", type=Path, default=DEFAULT_PLAYBOOK, help="Markdown playbook to run")
    parser.add_argument("--flow", action="append", help="Only run this flow key (repeatable)")
    parser.add_argument("--no-edge-cases", action="store_true", help="Skip edge-case variants")
    parser.add_argument("--reset-path", default="/__reset", help="POST here before the run (empty to disable)")
    parser.add_argument("--no-report", action="store_true", help="Skip issue sync and report generation")
    parser.add_argument("--headed", action="store_true", help="Show the browser window")
    args = parser.parse_args(argv)

    parsed = parse_playbook_markdown(args.playbook.read_text(encoding="utf-8"))
    if parsed["errors"]:
        raise SystemExit("playbook has errors:\n  " + "\n  ".join(parsed["errors"]))
    flows = expand_flows(parsed, args.flow, not args.no_edge_cases)
    if not flows:
        raise SystemExit(f"no matching flows in {args.playbook}")

    mode = RunMode(args.mode)
    run_id = str(uuid.uuid4())
    app_id = f"app-{args.app}"
    if not args.no_report:
        from sqlmodel import select
        from qagent.domain.models import App
        from qagent.storage import db
        async with db.async_session_factory() as session:
            app = (await session.execute(select(App).where(App.slug == args.app))).scalar_one_or_none()
        if app is None:
            raise SystemExit(f"app '{args.app}' is not registered; start the API once (it seeds the demo app) "
                             f"or pass --no-report")
        app_id = app.id
    spec = RunSpec(
        run_id=run_id,
        app_id=app_id,
        base_url=args.url or parsed["base_url"],
        mode=mode,
        flows=flows,
        reset_path=args.reset_path or None,
        inject_traceparent=settings.qagent_inject_traceparent,
        **spec_items(parsed),
    )

    upload_queue.start()
    checkpointer, checkpoint_conn = await open_checkpointer()
    escalator = ClaudeDecider() if mode == RunMode.HYBRID and settings.bedrock_api_key else None
    sink = PersistenceSink(run_id)
    runner = EngineRunner(spec, build_decider(mode), sink, headless=not args.headed,
                          escalator=escalator, checkpointer=checkpointer,
                          judge=None if mode == RunMode.STUB else Judge.from_settings(use_jev=mode == RunMode.HYBRID))
    print(f"[*] run {run_id} mode={mode.value} flows={[f.key for f in flows]} target={spec.base_url}")
    result = await runner.run()
    if not args.no_report:
        from qagent.api.seed import seed_demo
        from qagent.reports.pipeline import _default_claude, generate_reports
        from qagent.storage import db
        await upload_queue.drain()
        report = await generate_reports(db.async_session_factory, run_id, _default_claude(mode.value))
        issues = {k: len(v) for k, v in report["issues"].items()}
        print(f"[+] reports: run report {report['run_report_id']}, {len(report['bug_reports'])} bug reports, "
              f"issues {issues}, manifest {report['manifest_hash'][:12]}")
    await sink.flush()
    await upload_queue.stop()
    if checkpoint_conn is not None:
        await checkpoint_conn.close()

    print(f"[+] status={result['status']} steps={result['total_steps']} "
          f"findings={result['findings_count']} duration={result['duration_s']:.1f}s")
    for key, status in result["flows"].items():
        print(f"    {key}: {status}")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
