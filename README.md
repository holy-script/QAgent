# QAgent

QAgent is an intelligent, high-speed automated QA agent that tests web applications end-to-end.

## Core Architecture
- **Fast Decision Layer**: TypeSafe AI Jev (`jev-1.13.0`) makes low-latency, cheap DOM action choices (~400ms).
- **Reasoning Layer**: Anthropic Claude Sonnet 4 via AWS Bedrock Converse (Bearer Token auth) for plan synthesis, recovery, and deep validation.
- **Execution Layer**: Playwright for Python executing actions inside an instrumented sandbox.
- **State & Graph**: LangGraph with SQLite checkpointing and streaming telemetry via Server-Sent Events (SSE).
- **Frontend Dashboard**: Next.js App Router with `@xyflow/react` visualizing execution flowcharts in real time.

## Quickstart
1. Ensure `backend/.env` contains your `JEV_API_TOKEN` and `BEDROCK_API_KEY`.
2. Run health preflight:
   ```bash
   make doctor
   ```
3. Run test suite:
   ```bash
   make test
   ```
4. Start dev servers:
   ```bash
   make dev
   ```
