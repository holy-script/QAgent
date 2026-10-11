import argparse
import asyncio
import sys
from qagent.domain.runspec import RunSpec, FlowSpec
from qagent.domain.schemas import RunMode
from qagent.decision.stub import StubDecider
from qagent.decision.jev import JevDecider
from qagent.storage.persistence_sink import PersistenceSink
from qagent.storage.upload_queue import upload_queue
from qagent.engine.graph import EngineRunner


async def main():
    parser = argparse.ArgumentParser(description="QAgent CLI Runner")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument("--app", default="demo-shop", help="Target app slug")
    parser.add_argument("--mode", choices=["stub", "hybrid", "baseline"], default="stub", help="Execution mode")
    parser.add_argument("--url", default="http://localhost:8001", help="Target app base URL")
    args = parser.parse_args()

    upload_queue.start()

    mode = RunMode(args.mode)
    decider = StubDecider() if mode == RunMode.STUB else JevDecider()
    sink = PersistenceSink(run_id="cli-run-001")

    spec = RunSpec(
        run_id="cli-run-001",
        app_id=f"app-{args.app}",
        base_url=args.url,
        mode=mode,
        flows=[
            FlowSpec(
                key="checkout-flow",
                steps=["Open /products", "Add item to cart", "Go to /cart"],
                expect=["Cart has 1 item"],
            )
        ]
    )

    runner = EngineRunner(spec, decider, sink)
    print(f"[*] Starting QAgent CLI run in mode: {mode.value}...")
    result = await runner.run()
    print(f"[+] Run finished: status={result['status']}, steps={result['total_steps']}, duration={result['duration_s']:.2f}s")
    
    await upload_queue.stop()


if __name__ == "__main__":
    asyncio.run(main())
