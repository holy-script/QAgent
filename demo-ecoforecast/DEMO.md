# Demo runbook: QAgent testing EcoForecast (ForecastIQ)

The demo runs against the deployed EcoForecast, https://ecosystem-forecast.vercel.app, from the deployed QAgent, https://qagent-web-mu.vercel.app. Nothing needs to run on your laptop. (Appendix A is the local copy of the app, if you ever need one.)

## 0. What is already set up in QAgent (app `eco`)
- App **EcoForecast**, base URL `https://ecosystem-forecast.vercel.app`.
- **Allowed hosts**: `ecosystem-forecast.vercel.app, *.sslip.io`. The `*.sslip.io` entry matters: the app's Aria copilot and its fix/benchmark backend live on an `...sslip.io` host, and QAgent blocks any host that is not listed (a journey then looks as if "Fix with AI" does nothing). If a journey seems to miss a feature, open the run's activity log: QAgent now warns "requests to '<host>' were blocked ... add it in the app's settings".
- **Sign-in details**: `username` = admin, `password` saved (encrypted). The sign-in page has USERNAME / PASSWORD fields and a Sign in button.
- **Test files** (Settings > Test files): `ocrevus_trx_data.csv` (clean), `genentech_portfolio_trx_dirty_v5.csv` (the app's own sample), `empty.csv`, `header_only.csv`, `missing_product_column.csv`, `non_numeric_trx.csv`, `short_history_16mo.csv`. More are in `demo-ecoforecast/test-files/`.
- **Test plan** "EcoForecast PRD plan (demo)" (7 journeys + 3 edge-case variants). Its source is `demo-ecoforecast/test-plan.md`: the plan QAgent generates from `PRD.md`, reviewed and tightened (each journey is self-contained because EcoForecast forgets everything on reload; the ETS method is chosen explicitly; expectations are written as facts you can see).

## 1. Demo script (about 15 minutes)
1. **The app (1 min).** Sign in at the EcoForecast address (admin), pick 12 months, upload `ocrevus_trx_data.csv`, show "6/6 pass". This is "working".
2. **Create the plan from the product document (2 min).** In QAgent open EcoForecast, Test plans, *Create from product document*, paste/import `demo-ecoforecast/PRD.md`. It takes about 30 seconds and returns requirements, a sign-in journey (`role: setup`, no credentials in the plan) and goal-driven journeys, with expected outcomes. Point out nothing is written click by click. (If you do not want to wait, the saved plan "EcoForecast PRD plan (demo)" is the reviewed version.)
3. **Run it in Smart mode (10 min for everything, or pick 3 journeys).** Suggested short set: `clean-forecast-end-to-end`, `upload-rejected-files` (with its edge cases) and `export-forecast`. While it runs, show the live view; QAgent finds the file input, the dropdowns and the cards by itself.
4. **Results.** Open the run: each step with the elements the AI could choose (Before picture), what it chose and how sure it was, the server calls, and the problems with screenshots. Open a step (bottom panel) and zoom the screenshot.
5. **Repeat exactly** on the finished run (replays from the recording, no model cost).

## 2. What a full run produces (last verified run: 10 journeys, 65 steps, 10 minutes, about $1.50)
Real problems QAgent reports on the deployed app:
| Journey | Result | Why |
|---|---|---|
| clean-forecast-end-to-end | passes | 6/6 checks, Explore percentages, ETS forecast 6,786 to about 6,889 (+1.5%) all match the PRD |
| fix-with-ai-sample | passes | 939 to 931 rows and 6/6 re-validation |
| short-history-blocked | passes | the 24-month check fails and Proceed is not usable |
| upload-rejected-files (empty.csv) and EC-1 (header only) | **problems** | the server answers 422 (reported as a high server error) but the page shows "parsed" with 144 invented rows |
| EC-2 (no product column) / EC-3 (non-numeric trx) | reported | the user is not told which column is missing; non-numeric values are explained |
| export-forecast | **problem** | "Export Forecast (.csv)" does nothing: no download and no server request. Generating the deck works (about 7 s, flagged as a slow call) |
| custom-curve-honesty | **problems** | with a flat 0% curve the Custom Trend Curve is still ranked first and labelled Best Fit, and Auto-select best picks it |
Also reported every run (noise you can explain): "Step N exceeded 2000 ms" and "Page never settled" (the benchmark and the deck take several seconds).

## 3. Things that are true of this app and affect the demo
- EcoForecast keeps all data in memory: a page reload (or the app backend restarting) starts again at Setup. Every journey therefore logs in and uploads on its own; QAgent runs them one at a time because they share the sign-in.
- Aria (the copilot) works on the deployed app. The plan tells QAgent to ignore it.
- A new run may start while the app's backend is cold: the first step can be slow.
- If a journey fails oddly: check the activity log for "blocked" requests first, then the step list.

## 4. Before you present (checklist)
- [ ] Open https://ecosystem-forecast.vercel.app once to wake it, and sign in to confirm the backend answers.
- [ ] In QAgent, Settings for EcoForecast: Allowed hosts shows both entries; Sign-in details shows username and a saved password.
- [ ] Do one rehearsal of the three journeys you will show (about 4 minutes).
- [ ] Decide whether you present the generated plan or the saved one (see step 2).


## Appendix A. Running EcoForecast locally (only if needed)

```
cd /Users/holyscript/Desktop/projects/QAgent/demo-ecoforecast
ADMIN_USERNAME=admin ADMIN_PASSWORD='<choose one>' ./run.sh start    # backend :8010, frontend :3010
./run.sh status      # pids       ./run.sh stop     # stops both
```
- The first run creates `.venv-eco` and installs packages (several minutes) and builds the frontend (about a minute); later starts take about 5 seconds. Logs: `demo-ecoforecast/.run/`.
- Leave `ADMIN_USERNAME`/`ADMIN_PASSWORD` unset to use the development defaults written in `Ecosystem-Forecast-Backend-main/app/routers/auth.py` (user `admin`, password `forecastiq2025`). Whatever you choose is what you type into QAgent below.
- Check: http://localhost:3010 shows the ForecastIQ sign-in; http://localhost:8010/docs shows the API.
- Env used (set by run.sh): `NEXT_PUBLIC_API_URL=http://localhost:8010`, `NEXT_PUBLIC_WS_URL=ws://localhost:8010/api/agent/ws`, `BACKEND_URL=http://localhost:8010`, backend `ALLOWED_ORIGINS=http://localhost:3010`. State is in memory: restart the backend before each rehearsal for a clean slate.
- The "Aria" chat panel needs AWS Bedrock credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, optional `BEDROCK_MODEL_ID`) exported before `./run.sh start`. Without them Aria prints "Agent error: Unable to locate credentials"; everything else works. Do not demo Aria unless you have supplied them.


Then in QAgent add a second app with base URL `http://localhost:3010` and allowed hosts `localhost,127.0.0.1` (and run QAgent locally: the deployed one cannot reach your laptop).
