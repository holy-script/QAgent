import argparse
import asyncio
import uuid
from pathlib import Path

from qagent.decision.base import Decider
from qagent.config import settings
from qagent.decision.claude import ClaudeDecider
from qagent.decision.jev import JevDecider
from qagent.decision.stub import StubDecider
from qagent.domain.runspec import FlowSpec, RunSpec
from qagent.domain.schemas import RunMode
from qagent.engine.graph import EngineRunner
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.storage.checkpoint import open_checkpointer
from qagent.storage.persistence_sink import PersistenceSink
from qagent.storage.upload_queue import upload_queue

DEFAULT_PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "checkout-flow.md"


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
    parser.add_argument("--headed", action="store_true", help="Show the browser window")
    args = parser.parse_args(argv)

    parsed = parse_playbook_markdown(args.playbook.read_text(encoding="utf-8"))
    flows = [FlowSpec.model_validate(f) for f in parsed["flows"] if not args.flow or f["key"] in args.flow]
    if not flows:
        raise SystemExit(f"no matching flows in {args.playbook}")

    mode = RunMode(args.mode)
    run_id = str(uuid.uuid4())
    spec = RunSpec(
        run_id=run_id,
        app_id=f"app-{args.app}",
        base_url=args.url or parsed["base_url"],
        mode=mode,
        flows=flows,
    )

    upload_queue.start()
    checkpointer, checkpoint_conn = await open_checkpointer()
    escalator = ClaudeDecider() if mode == RunMode.HYBRID and settings.bedrock_api_key else None
    runner = EngineRunner(spec, build_decider(mode), PersistenceSink(run_id), headless=not args.headed,
                          escalator=escalator, checkpointer=checkpointer)
    print(f"[*] run {run_id} mode={mode.value} flows={[f.key for f in flows]} target={spec.base_url}")
    result = await runner.run()
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
