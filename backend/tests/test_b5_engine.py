import pytest
from qagent.domain.runspec import RunSpec, FlowSpec
from qagent.domain.schemas import RunMode
from qagent.decision.stub import StubDecider
from qagent.storage.persistence_sink import PersistenceSink
from qagent.engine.graph import EngineRunner


@pytest.mark.asyncio
async def test_engine_runner_stub_mode():
    sink = PersistenceSink(run_id="test-engine-run-001")
    spec = RunSpec(
        run_id="test-engine-run-001",
        app_id="app-demo",
        base_url="http://localhost:8001",
        mode=RunMode.STUB,
        flows=[
            FlowSpec(
                key="sample-flow",
                steps=["Open /products", "Add item", "View cart"],
                expect=["Cart has 1 item"],
            )
        ]
    )
    decider = StubDecider()
    runner = EngineRunner(spec, decider, sink)
    
    result = await runner.run()
    assert result["status"] == "passed"
    assert result["total_steps"] == 3
    assert result["duration_s"] > 0
    assert sink._seq >= 10
