import json
from pathlib import Path
from typing import List, Dict, Any

FIXTURES_DIR = Path(__file__).parent


def get_mock_run_events() -> List[Dict[str, Any]]:
    events_path = FIXTURES_DIR / "run_events.jsonl"
    if not events_path.exists():
        return _generate_default_fixture_events()
    
    events = []
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


def _generate_default_fixture_events() -> List[Dict[str, Any]]:
    return [
        {
            "run_id": "run-demo-001",
            "seq": 1,
            "type": "RUN_STARTED",
            "payload": {
                "target_url": "http://localhost:8001",
                "app_name": "Demo E-Commerce Shop",
                "mode": "hybrid",
                "flow_count": 1,
            },
            "ts": "2026-10-11T12:00:00Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 2,
            "type": "FLOW_STARTED",
            "payload": {
                "flow_key": "add-to-cart",
                "severity": "high",
                "total_steps": 3,
            },
            "ts": "2026-10-11T12:00:01Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 3,
            "type": "STEP_OBSERVED",
            "payload": {
                "step_seq": 1,
                "url": "http://localhost:8001/products",
                "page_title": "Products Catalog - Demo Shop",
                "candidates_count": 12,
                "screenshot_url": "/api/artifacts/run-demo-001/steps/1/screenshot.jpg"
            },
            "ts": "2026-10-11T12:00:02Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 4,
            "type": "DECISION_MADE",
            "payload": {
                "step_seq": 1,
                "decider": "jev",
                "model_version": "jev-1.13.0",
                "selected_action_id": 4,
                "action_label": "Add to Cart (Wireless Headphones)",
                "confidence": 0.94,
                "tier": "AUTO",
                "latency_ms": 340.2,
                "cost_usd": 0.0004
            },
            "ts": "2026-10-11T12:00:02.340Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 5,
            "type": "GATE_TRIGGERED",
            "payload": {
                "step_seq": 1,
                "tier": "AUTO",
                "reason": "Confidence 0.94 >= 0.75 threshold"
            },
            "ts": "2026-10-11T12:00:02.345Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 6,
            "type": "ACTION_EXECUTED",
            "payload": {
                "step_seq": 1,
                "action_id": 4,
                "status": "success",
                "duration_ms": 115.0
            },
            "ts": "2026-10-11T12:00:02.460Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 7,
            "type": "NETWORK_CALL",
            "payload": {
                "step_seq": 1,
                "method": "POST",
                "url": "http://localhost:8001/api/cart/items",
                "status": 200,
                "duration_ms": 85.0,
                "is_api": True
            },
            "ts": "2026-10-11T12:00:02.500Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 8,
            "type": "STEP_OBSERVED",
            "payload": {
                "step_seq": 2,
                "url": "http://localhost:8001/products",
                "page_title": "Products Catalog - Demo Shop",
                "candidates_count": 12,
                "screenshot_url": "/api/artifacts/run-demo-001/steps/2/screenshot.jpg"
            },
            "ts": "2026-10-11T12:00:03.000Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 9,
            "type": "DECISION_MADE",
            "payload": {
                "step_seq": 2,
                "decider": "jev",
                "model_version": "jev-1.13.0",
                "selected_action_id": 7,
                "action_label": "View Cart",
                "confidence": 0.88,
                "tier": "AUTO",
                "latency_ms": 310.5,
                "cost_usd": 0.0004
            },
            "ts": "2026-10-11T12:00:03.310Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 10,
            "type": "ACTION_EXECUTED",
            "payload": {
                "step_seq": 2,
                "action_id": 7,
                "status": "success",
                "duration_ms": 140.0
            },
            "ts": "2026-10-11T12:00:03.450Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 11,
            "type": "STEP_OBSERVED",
            "payload": {
                "step_seq": 3,
                "url": "http://localhost:8001/cart",
                "page_title": "Shopping Cart - Demo Shop",
                "candidates_count": 8,
                "screenshot_url": "/api/artifacts/run-demo-001/steps/3/screenshot.jpg"
            },
            "ts": "2026-10-11T12:00:04.000Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 12,
            "type": "FINDING_DISCOVERED",
            "payload": {
                "step_seq": 3,
                "severity": "high",
                "kind": "dom",
                "title": "Cart badge count mismatch",
                "expected": "Cart badge displays '1'",
                "actual": "Cart badge displays '0'",
                "evidence": {
                    "badge_text": "0",
                    "cart_items_count": 1
                }
            },
            "ts": "2026-10-11T12:00:04.200Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 13,
            "type": "FLOW_FINISHED",
            "payload": {
                "flow_key": "add-to-cart",
                "status": "passed_with_findings",
                "duration_ms": 3200.0,
                "findings_count": 1
            },
            "ts": "2026-10-11T12:00:04.500Z"
        },
        {
            "run_id": "run-demo-001",
            "seq": 14,
            "type": "RUN_FINISHED",
            "payload": {
                "run_id": "run-demo-001",
                "outcome": "COMPLETED",
                "total_steps": 3,
                "total_cost_usd": 0.0008,
                "duration_s": 4.5,
                "findings_count": 1
            },
            "ts": "2026-10-11T12:00:04.510Z"
        }
    ]
