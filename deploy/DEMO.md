# Demo runbook

## Before the day
1. `make migrate` (applies the `model_calls` and retention columns to your Neon database).
2. `make setup` once on the demo machine (installs the pinned Chromium), then `make doctor`: every line should be green.
3. Use a dedicated Neon branch for the demo (Neon console > Branches > create "demo" from main) and put that branch's connection strings in `backend/.env`.
4. Do one full rehearsal (below) the day before. Run `make bench` and note the Smart vs Thorough numbers.

## Neon free plan: the database sleeps after ~5 minutes idle
The first query after a sleep takes a second or two longer; nothing breaks. To avoid it live:
- Two minutes before you start, run `make doctor` (it queries the database and wakes it), or just open the app and click around once.
- Keep the app open during the demo; every page load keeps it awake.

## The demo (about 5 minutes)
1. `make dev`, open http://localhost:3000, sign in (`admin@chryselys.com`).
2. Open **Demo Shop** > Overview > choose **Smart** > **Run now**. Watch the journeys fill in; open a step to show what the AI saw and chose.
3. When it finishes: **Problems** tab (the planted bugs), open the **checkout 500** bug: steps to reproduce, screenshots, the server call, **Copy as issue**.
4. **AI calls** tab: every AI call in order with its cost. Say: "the fast AI did most steps; the strong AI was only asked when unsure."
5. **Repeat exactly**: the same run again from the recording, no AI cost, same result. Show the "from recording" badges.
6. **Requirements** tab: which requirement each bug breaks. **Compare** two runs.
7. To show Smart vs Thorough: run again in **Thorough** and compare time and cost on the Runs list.

If something goes wrong live: refresh; `make doctor`; as a fallback `make dev-mock` shows the same screens on built-in demo data (no backend).

## Try the planner live (once)
1. `make dev`. Open Demo Shop > Overview. In **Run a test**, choose **Smart** and tick **Let the strong AI plan each journey first**. Run now.
2. Open the run > **Activity** tab: one line per journey from source `planner` ("plan: ... (N step notes)"). Failures show as "planning skipped"; the run still goes ahead.
3. **AI calls** tab > **Plan** section: one call per journey with its cost (about a cent each).
4. Press **Repeat exactly**: the plan is answered from the recording ("from recording", no cost).
5. Judge for yourself: run the same plan with and without the tick and compare how many steps needed the strong AI (Overview "Fast AI / Strong AI" metric).

## Hosting on Vercel + FastAPI Cloud: what to know first
- **Browser**: the backend drives Chromium. Confirm FastAPI Cloud can run Playwright (a Chromium download and roughly 1 GB of memory per run). If `fastapi deploy` works but `make doctor`-style checks fail on the browser, the backend needs a container host instead (Render, Railway, Fly.io, or the one-machine `docker-compose.yml`).
- **One instance**: live run events are kept in memory, so the backend must stay at one instance. Turn autoscaling off / max instances to 1.
- **Cookies across sites**: the sign-in cookie only works if the web app and API share a registrable domain (for example `app.example.com` on Vercel and `api.example.com` on the backend). Set on the backend: `CORS_ORIGINS=https://app.example.com`, `AUTH_COOKIE_SECURE=true`, `AUTH_SECRET=<random>`. On different domains (`*.vercel.app` and `*.fastapicloud.dev`) browsers block the cookie; set `AUTH_COOKIE_SAMESITE=none` and expect Safari and Chrome's third-party cookie rules to break sign-in sometimes.
- **Vercel**: Root Directory `frontend`; `frontend/vercel.json` sets the install command (`--legacy-peer-deps`). Environment variable `NEXT_PUBLIC_API_URL=https://api.example.com` (set before building).
- **Long runs and streaming**: the browser connects straight to the API for live events, so Vercel's function time limits do not apply to them.
