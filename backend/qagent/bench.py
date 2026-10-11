"""make bench: decision latency, cost/step and accuracy as the candidate list grows (10, 20, 40)."""
import argparse
import asyncio
import random
import statistics
from typing import Dict, List

from qagent.config import settings
from qagent.decision.base import Decider
from qagent.decision.claude import ClaudeDecider
from qagent.decision.jev import JevDecider
from qagent.domain.schemas import CandidateAction, DecisionRequest

LABELS = ["Home", "Products", "Cart", "Checkout", "Sign in", "Help", "Wishlist", "Search", "Contact", "About",
          "Track order", "Returns", "Gift cards", "Deals", "Newsletter", "Terms", "Privacy", "Careers", "Blog",
          "Support", "Language", "Currency", "Compare", "Reviews", "Store locator", "FAQ", "Press", "Partners",
          "Shipping info", "Size guide", "Accessibility", "Sitemap", "Feedback", "Apply Coupon", "Save address",
          "Remove item", "Update quantity", "Continue shopping", "View details", "Add to wishlist"]
TARGET = "Pay now"


def make_request(n: int, seed: int) -> tuple[DecisionRequest, int]:
    rng = random.Random(seed)
    labels = rng.sample(LABELS, n - 1) + [TARGET]
    rng.shuffle(labels)
    cands = [CandidateAction(id=i + 1, tag="button", selector=f"#c{i}", label=l) for i, l in enumerate(labels)]
    target_id = next(c.id for c in cands if c.label == TARGET)
    return DecisionRequest(step_seq=1, intent="Click Pay now", url="http://localhost:8001/checkout",
                           candidates=cands), target_id


def pct(values: List[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


async def bench_decider(name: str, decider: Decider, sizes: List[int], runs: int) -> List[Dict]:
    rows = []
    for n in sizes:
        lat, cost, correct, errors = [], [], 0, 0
        for i in range(runs):
            req, target = make_request(n, seed=n * 1000 + i)
            try:
                res = await decider.decide(req)
            except Exception:
                errors += 1
                continue
            lat.append(res.latency_ms)
            cost.append(res.cost_usd)
            correct += res.selected_action_id == target
        ok = len(lat)
        rows.append({
            "decider": name, "candidates": n, "calls": ok, "errors": errors,
            "p50_ms": round(statistics.median(lat)) if ok else None,
            "p95_ms": round(pct(lat, 95)) if ok else None,
            "cost_per_step_usd": round(statistics.mean(cost), 5) if ok else None,
            "accuracy": round(correct / ok, 2) if ok else None,
        })
    return rows


def to_markdown(rows: List[Dict]) -> str:
    head = "| Decider | Candidates | Calls | Errors | p50 ms | p95 ms | $/step | Accuracy |\n|---|---|---|---|---|---|---|---|\n"
    return head + "\n".join(
        f"| {r['decider']} | {r['candidates']} | {r['calls']} | {r['errors']} | {r['p50_ms']} | {r['p95_ms']} | "
        f"{r['cost_per_step_usd']} | {r['accuracy']} |" for r in rows)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=8, help="calls per candidate size")
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 20, 40])
    args = ap.parse_args()

    rows: List[Dict] = []
    if settings.active_jev_token:
        rows += await bench_decider("jev", JevDecider(), args.sizes, args.runs)
    else:
        print("[skip] Jev: no TYPESAFE_API_KEY")
    if settings.bedrock_api_key:
        rows += await bench_decider("claude", ClaudeDecider(), args.sizes, args.runs)
    else:
        print("[skip] Claude: no BEDROCK_API_KEY")
    print(to_markdown(rows))


if __name__ == "__main__":
    asyncio.run(main())
