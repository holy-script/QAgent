# Demo runbook: QAgent testing EcoForecast (ForecastIQ)

## 0. Decide first: where does QAgent run?
EcoForecast runs on your machine (`localhost:3010`). QAgent's deployed copy (Vercel + Codespace) cannot see your laptop's localhost.
- Easiest: run QAgent locally too (API on 8000, web on 3100, as in CONTEXT.md) and add EcoForecast as `http://localhost:3010`.
- Otherwise EcoForecast must be reachable from the Codespace (forward ports 3010 and 8010 as Public in the same Codespace, and rebuild the frontend with `NEXT_PUBLIC_API_URL` pointing at the public 8010 URL). Not tried here.

## 1. Start EcoForecast
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

## 2. Add the app in QAgent
- Name: `EcoForecast (ForecastIQ)`   Base URL: `http://localhost:3010`
- Allowed hosts: `localhost,127.0.0.1` (matched by hostname, so the API on :8010 is covered; Google Fonts is blocked, which only changes the font).
- Settings > Sign-in details: username `admin`, password = your ADMIN_PASSWORD. The sign-in page has fields USERNAME and PASSWORD and a "Sign in" button; a wrong password shows "Invalid username or password."
- Settings > Test files (attach from `demo-ecoforecast/test-files/`): `ocrevus_trx_data.csv`, `clean_valid_3eco_36mo.csv`, `genentech_portfolio_trx_clean.csv`, `genentech_portfolio_trx_dirty.csv`, `duplicates_and_negatives.csv`, `short_history_16mo.csv`, `missing_trx_column.csv`, `empty.csv`, `not_a_csv.txt`. (Each file max 10 MB; the others in the folder are optional.)

## 3. Demo script (about 15 minutes)
1. Show the app for 1 minute: sign in (user from section 2), pick a horizon, upload `ocrevus_trx_data.csv`, show 6/6 checks. Then sign out. This is what "working" looks like.
2. In QAgent open the app, choose **Create from product document**, import `demo-ecoforecast/PRD.md`. Wait for the plan (a minute or two).
3. Review the plan: a sign-in journey (role: setup) with no credentials in it; 3 to 8 goal-driven journeys (horizon and upload, validation and auto-fix, explore, method and forecast, export, bad files); edge cases (empty file, wrong type, missing column, short history); Test data lines marked `<fill in>` must be filled, for example `file: ocrevus_trx_data.csv`. Point out that nothing was written step by step.
4. Run the plan in **Smart** mode (Jev picks elements, Claude steps in when unsure). Allow roughly 10 to 20 minutes for the whole plan; for a live demo run 2 or 3 journeys (happy path, dirty file, short history).
5. While it runs: show the live view and decisions. Afterwards open the results and report: pass/fail per requirement, findings with screenshots, server calls and steps to reproduce.
6. Show Repeat exactly (replay from the tape, no model cost) on a finished run.

## 4. Real bugs QAgent should surface (all reproduced)
1. Rejected upload shows fabricated data: upload `empty.csv` or `header_only.csv`; the server says 422 but the page shows a "parsed" file with invented Mountain West / Tecentriq rows. A 58 MB file (413) likewise shows no error.
2. Fix bypass: upload `short_history_16mo.csv`, Confirm mapping, click "Fix with AI": re-validation still shows "Minimum 24 months" failed, yet "Proceed to Analysis" is enabled.
3. Method screen hangs after that: "Running parallel model benchmark…" forever while the browser spams failing requests (visible as repeated 422 and 404 `/api/benchmarks/undefined` in the server calls).
4. Wrong counts: after "Fix with AI" the footer says "926 ecosystems · 1 months" (dirty file) or "312 ecosystems" (it shows the row count).
5. `genentech_portfolio_trx_dirty.csv`: after the fix 3 of 6 checks still fail, product tabs multiply (10 tabs: "Ocrevus Iv", "hemlibra", "TECENTRIQ"...), cards show ▲ 99580.0% / ▼ 99.9%, explored range runs to 2028-07; proceeding gives a forecast with start 2024-11 and +404.9%.
6. "Export Forecast (.csv)" button in the Aria panel (Forecast step) does nothing; no download.
7. "Custom Trend Curve" is always "Best Fit" with made-up scores (Test WAPE 4.6%, RMSE 512, AIC 1,876) and drags "Auto-select best" and the ensemble.
8. Missing `trx`/`product` column (`missing_trx_column.csv`): the confirm button is disabled with no explanation.
9. Negative values (`duplicates_and_negatives.csv`) pass undetected until the fix silently clips them; `missing_30pct.csv` is "blocked" but the fix fills 96 values anyway.
10. Accessibility: login labels are not tied to their inputs.
Expected passes worth showing: login errors, wrong file type alert, duplicates and non-numeric detection, 24-month rule, KPI numbers (6,786 to 6,889, +1.5% for ETS, 12 months, `ocrevus_trx_data.csv`), deck download.

## 5. Likely failure points and recovery
- Port busy or servers stale: `./run.sh stop` then `./run.sh start`. Each start needs ports 8010 and 3010 free.
- QAgent cannot open the app (blocked host or unreachable): see section 0; check Allowed hosts includes `localhost`.
- "Network error. Make sure the backend is running on port 8000." on the login page: it means the backend is down (the text always says 8000 even though we use 8010). Run `./run.sh status`.
- Login fails in QAgent: ADMIN_PASSWORD you started with differs from the saved sign-in details. Restart with the right one or update Settings.
- Backend restarted mid-run: the wizard session is gone (in memory); start the journey again from Setup.
- Aria shows "Agent error": expected without AWS credentials; collapse the panel (the "Copilot Open" button) or ignore it. A journey that tries the chat may be reported as failed.
- First run is slow (installs/build): do `./run.sh start` once the day before, then `./run.sh stop`.
- Plan import produced `<fill in>` test data or a missing upload file name: fill the file name from the Test files list before running.
- Upload steps in QAgent choose files by name; if a journey picks the wrong file, name it in the Test data (`file: duplicates_and_negatives.csv`).
- Goal journeys run out of step budget (default 25 steps / 90 s per flow): the wizard has 5 screens; split long goals or raise the budget.
- Behaviour that is deterministic but looks odd (not a QAgent fault): benchmark takes 3 to 5 s; Pacific West shows ▼ 12.9% under ETS 12 months while history is rising.
