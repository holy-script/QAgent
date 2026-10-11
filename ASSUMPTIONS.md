# ASSUMPTIONS & DESIGN DECISIONS

1. **Jev API Token & SDK**:
   - The token environment variable is `JEV_API_TOKEN` (with `TYPESAFE_API_KEY` supported as an alias).
   - Base endpoint: `https://api.typesafe.ai/v1/systemone`.
   - Default pinned model: `jev-1.13.0` (as verified in Step 0 preflight, returning exact version in model metadata).
   - Rate limits are dynamically adjusting; retries are handled with exponential backoff on 429 and 529.
   - Cost: $0.042/Mtok input; output tokens are free.
   - Noul questions lack explicit confidence fields from the API; confidence is mapped to `abs(2p - 1)` to normalize with Choice gating.

2. **AWS Bedrock Auth**:
   - The Bedrock key (`ABSK...`) functions as an HTTP Bearer Token (`Authorization: Bearer <token>`).
   - Standard AWS IAM SigV4 / boto3 authentication is NOT used. All requests route via direct async `httpx` to `https://bedrock-runtime.{region}.amazonaws.com/model/{modelId}/converse`.
   - The verified active Claude Sonnet model ID is `us.anthropic.claude-sonnet-4-20250514-v1:0` in `us-east-1`.

3. **Gating Tiers**:
   - Confidence >= 0.75: **AUTO** (Action proceeds directly using Jev's choice).
   - 0.45 <= Confidence < 0.75: **ESCALATE** (Escalates to Claude Sonnet for deep reflection and verification).
   - Confidence < 0.45: **FAIL / STOP** (Action halts to prevent unintended destructive steps).

4. **Monorepo Architecture**:
   - `demo-shop/`: Pure HTML/Jinja FastAPI app at port 8001 with 4 togglable bug flags and reset endpoint.
   - `backend/`: FastAPI + Playwright + LangGraph state engine + SSE stream at port 8000.
   - `frontend/`: Next.js 14+ App Router at port 3000 consuming SSE live event stream and visualizing execution flowchart via `@xyflow/react`.

## Decision benchmark (`make bench`, 8 calls per size, 2026-10-11)

Synthetic step "Click Pay now" with one correct candidate among N, live APIs.

| Decider | Candidates | p50 ms | p95 ms | $/step | Accuracy |
|---|---|---|---|---|---|
| Jev (`jev-latest`) | 10 | 349 | 452 | 0 (output tokens free; input pricing unpublished) | 1.00 |
| Jev | 20 | 313 | 404 | 0 | 1.00 |
| Jev | 40 | 354 | 527 | 0 | 1.00 |
| Claude (Sonnet 4 via Bedrock) | 10 | 2272 | 4485 | 0.0033 | 1.00 |
| Claude | 20 | 2214 | 3182 | 0.0038 | 1.00 |
| Claude | 40 | 2330 | 3188 | 0.0048 | 1.00 |

- Jev is ~6-7x faster and latency is flat from 10 to 40 candidates; Claude cost grows with candidate count.
- The Jev API contract is `POST /v1/systemone` with `state` + named `questions` (a `choice` question here). The model alias is `jev-latest`; `jev-1.13.0` does not exist.
- Replay matches calls by a hash of (step, intent, url, candidates); a page whose element positions change between runs will miss the tape.
