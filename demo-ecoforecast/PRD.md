# EcoForecast (ForecastIQ) – Product Requirements Document

Version: 0.4 beta (as built). Owner: Commercial Analytics. Status: describes the product as it is meant to behave; section 12 lists where the current build differs.

## 1. Purpose and users

EcoForecast (shown on screen as "Chryselys ForecastIQ – Agentic Short Term Forecast") is a web app that turns a file of historical monthly prescription volume (TRx) into a short-term forecast per ecosystem and product, with confidence intervals and a downloadable slide deck. An ecosystem is a commercial territory such as "Northeast Corridor" or "Pacific West".

Users: commercial analysts and brand teams in pharma who need a quick, defensible 6 to 24 month volume outlook without writing code. One shared sign-in is used (no roles, no per-user data).

Goals: (1) get from a CSV to a forecast in under 5 minutes; (2) catch data problems before forecasting and explain them in plain words; (3) let the analyst choose or combine forecasting methods using measured accuracy; (4) produce an executive-ready deck.

## 2. End-to-end workflow

Five steps shown in a progress bar at the top: **Setup, Upload, Explore, Method, Forecast**. A copilot panel ("Aria") sits on the right and can be collapsed ("Copilot Open" button) or resized by dragging its left edge.

1. Sign in. 2. Choose the forecast horizon. 3. Upload a CSV (or load the sample), map columns, run six integrity checks, optionally apply the automatic fix. 4. Explore each ecosystem's history, trend and seasonality. 5. Run a method benchmark, commit a strategy. 6. Read the forecast, switch views, download the deck. "Start New Flow" resets everything.

Data lives in server memory only: restarting the backend or reloading the browser page loses the session and returns to Setup.

## 3. Sign-in

- Any address other than /login redirects to /login when not signed in. Fields: Username, Password, button "Sign in".
- Both empty or one empty: message "Username and password are required." No request is sent.
- Wrong credentials: message "Invalid username or password." and the user stays on /login.
- Correct credentials: lands on Setup. Header shows the username and a "Sign out" button; Sign out returns to /login and protected pages redirect again.
- A session token lasts 24 hours. An invalid or expired token sends the user back to /login.
- Needed values (supplied by the tester, never written into a plan): **ADMIN_USERNAME** and **ADMIN_PASSWORD** of the backend (set in the backend environment; the backend also has built-in development defaults).

## 4. Setup screen (Step 01)

- Title "Chryselys ForecastIQ.", question "Select Forecast Horizon". Four choices: 6, 12, 18, 24 months.
- After choosing, the card changes to "Run Configuration Active" showing Forecast horizon (for example "12 months, through <month year> = today plus the horizon"), Scope "Ecosystem-level", Granularity "Monthly Volume, aggregation: sum", the note ".csv only · max 50MB", a "Change Horizon" link and the button **Upload Historical Data**.
- The horizon is saved to the server (allowed range 1 to 60 months; the screen only offers the four values).

## 5. Upload and validation screen (Step 02)

### 5.1 Getting data in
- Drop zone "Drop your data file here, or click to browse · .csv only · up to 50MB" and a link "Load sample dataset". The sample is the bundled file genentech_portfolio_trx_dirty_v5.csv (939 rows, 3 products, 6 ecosystems, 50 months).
- Only files ending in .csv are accepted. Any other extension shows a browser alert "Unsupported file. Only CSV files (.csv) are allowed." and nothing is uploaded.
- After a successful parse the screen shows the file name, size, row and column counts and "parsed"; a Product Portfolio picker (one toggle per product, "N of M selected"); a preview of the first 5 rows; and a Column mapping panel.
- The backend rejects: non-CSV (415), files over 50 MB (413), unreadable files (422 PARSE_ERROR) and files with no data rows (422 EMPTY_DATASET "File has no data rows"). The user must be told the file was rejected and should be able to try again.

### 5.2 Required columns and mapping
Four roles must be mapped, each from a dropdown of the file's columns, and are auto-detected by name: **Date / Time Period** (date, period, month, time), **Region / Ecosystem** (ecosystem_product, region, ecosystem, territory, geo), **Volume** (trx, rx, prescriptions, volume), **Product / Brand** (product, brand, drug, molecule, therapy). When the file has both a product and an ecosystem column the app adds a derived column `ecosystem_product` = "<ecosystem> (<product>)" and maps Region to it, so each product-ecosystem pair is one series.
- The button "Confirm Mapping & Run Validation" is enabled only when all four roles are mapped. A missing required column (no trx, no product) means it cannot be enabled and the user should be told which column is missing.
- Changing a mapping turns the button into "Update Mapping & Re-validate".
- Column headers and cell text are trimmed; fully empty rows are dropped; a UTF-8 BOM is tolerated.

### 5.3 Accepted formats
Date values: YYYY-MM, YYYY-MM-DD (or ISO 8601), DD-MM-YYYY, M/D/YYYY, otherwise parsed with day-first rules. All are reduced to a YYYY-MM month. Volume values must parse as plain numbers; "1,234", "n/a", "tbd", "-" and an em dash count as non-numeric. Blank volume cells count as missing.

### 5.4 The six integrity checks ("6 integrity checks", counter "n/6 pass")
| # | Check | Passes when | Message on failure |
|---|---|---|---|
| 1 | All required columns mapped | date, region, volume, product mapped | one or more unmapped |
| 2 | Date column parseable as monthly periods | fewer than 5% of dates unparseable | unrecognized date format |
| 3 | No duplicate ecosystem-month-product combinations | no repeated (month, ecosystem, product) | "duplicates found" (API: "N duplicate row(s) found") |
| 4 | Volume column contains valid numbers | every non-blank value is numeric | `"trx" has non-numeric values - use AI Fix or re-map` |
| 5 | Missing values within tolerance | worst series has at most 20% blanks; 0-5% shows "minor, will auto-fill", 5-20% "significant, will auto-fill" | "N% missing in worst ecosystem - exceeds 20% threshold" |
| 6 | Minimum 24 months of history | every series has at least 24 distinct months | "N months in worst ecosystem - need 24" |

A clean file shows "6/6 pass" plus a "Validation Report & Data Audit" (ecosystem-product groups, months, "0 missing cells (100% complete)" or "N cells auto-filled (adjacent avg)"). A failing file shows "Issues blocking analysis" listing each failed check, the button "Fix with AI", and "Re-upload different file". "Proceed to Analysis" is disabled until the file passes (or is fixed, see 5.5).
Missing blanks within tolerance are filled by linear interpolation per series (edges use the series mean).

### 5.5 "Fix with AI" (data sanitiser)
One click runs, in order: drop exact duplicate rows; drop duplicate month-ecosystem(-product) keeping the first; coerce volume to numbers (unparseable becomes blank); normalise dates to YYYY-MM (rows with unrecoverable dates are dropped); fill blanks by per-series linear interpolation; clip negative volumes to 0. The result card "Aria Fixed N Issue(s)" shows "before to after rows", a tick per change, expandable lists of removed rows and imputed values (capped at 200), and a RE-VALIDATION list of the six checks. Proceeding after a fix is allowed only if the re-validation passes (see Known gaps).
Footer text: "<file> → <E> ecosystems · <M> months", where E is the number of ecosystem-product series and M the minimum months per series.

### 5.6 Product selection
Each product toggle includes or excludes that product from validation, exploration and the forecast ("2 of 3 selected" etc).

## 6. Explore screen (Step 03)

Header: product name (and "+N more"), number of territories, period range ("2022-01 → 2026-04"), "horizon · 12mo", buttons "← Back to Upload" and "Proceed to Method". With several products a "SELECT PRODUCT TAB" row appears.
- One card per ecosystem: name, latest monthly Trx, and a badge with the percentage change from the first to the last month (▲ green up, ▼ down). Clicking a card makes it "viewing".
- Three charts for the selected ecosystem: **Raw Trx** (area chart), **Trend** (12-month centred moving average; the first 6 and last 6 months are blank), **Seasonal** (additive monthly effect; effects sum to about 0). Side facts: PERIOD, TRX RANGE (min to max), MONTHS.

## 7. Method screen (Step 04)

- On entry a benchmark starts automatically: the last 6 months are held out, four methods are fitted to every series (Holt-Winters, SARIMA(1,1,1)(1,1,1)12, Linear Trend + Seasonality (OLS with monthly dummies), ETS) and scored. Status shows "benchmarking models..." then "status · ready" (about 3 to 5 seconds for 6 series). A series needs at least holdout + 12 months.
- Model Evaluation Matrix (click a header to sort, default sorted by Test WAPE ascending): TRAIN WAPE, TEST WAPE, TRAIN RMSE, TEST RMSE, AIC per method. WAPE = sum of absolute errors divided by sum of actuals.
- Custom Month-on-Month table: one percentage input per forecast month (labels start the month after the last actual). "Reset All (0%)" sets every input to 0; "Set Baseline (+2%)" sets every input to 2. A custom curve starts from the last actual of each series and compounds the percentages.
- Chart "Model Trajectories": observed history vs hold-out predictions and forecast per method, territory chips to switch series, method toggles to show or hide curves.
- "Commit Forecasting Strategy" (applies to all products): **Use selected method** (needs a row selected), **Combine top 2-3 (Ensemble)**, **Auto-select best** (lowest Test WAPE). Committing opens the Forecast step. The top-right "Proceed to Forecast" stays disabled until a strategy is committed.
- Rules enforced by the API: ensemble needs 2 or 3 methods; single/auto needs exactly 1; unknown method ids are rejected (422).

## 8. Forecast screen (Step 05)

- Header: HORIZON (months and range, for example "12 Months (2026-04 → 2027-04)"), Engine (method label, for ensembles "Ensemble · A + B"), status · complete, "← Back to Methods", **Generate Deck (.pptx)**.
- KPI tiles: NATIONAL BASELINE TRX (sum over all series at the last actual month), PROJECTED HORIZON TRX (sum of forecasts at the last forecast month), NET PORTFOLIO TRAJECTORY (percent change, ▲ GROWTH or ▼ DECLINE, "Aggregated across N product(s)").
- Views: Chart View (history, forecast and 95% CI band for the chosen ecosystem, "FORECAST START" marker), Data Table ("Tabular Data Export": Period, Type History/Forecast, Trx (point), Lower 95% CI, Upper 95% CI; rows = history months + horizon months), Treemap View (tile area proportional to horizon volume; at most 16 tiles, the rest grouped as "+N others"), Consolidated Comparison, and product tabs when several products are selected.
- Ecosystem Projections cards: percent change, horizon-end volume, "was <baseline>"; clicking a card selects that ecosystem.
- Generate Deck downloads a PowerPoint file named forecastiq_<id>.pptx (takes about 1 second; the app shows progress steps).
- The side panel on this step offers "Export Forecast (.csv)" and "Start New Flow".

## 9. Forecasting methods, parameters and formulas (checkable)

- Forecast generation uses the full history of each product-ecosystem series; output is `horizon` rows per series (6 series x 12 months = 72 forecast rows) with point, lower, upper, all rounded to whole numbers; lower and point are never below 0.
- Single method: that method's point and 95% interval.
- Ensemble: point = equal-weight mean of members; lower = minimum of members' lowers; upper = maximum of members' uppers. Example (6-month horizon, Great Lakes (Ocrevus IV), first month): ETS 1,179 and Linear 1,296 give 1,238 (1,237.5 rounded).
- Custom curve: point(k) = point(k-1) x (1 + m_k/100), starting from the last actual. Example: Great Lakes last actual 1,184 with +5% every month gives 1,243 for 2026-05.
- Method label mapping: holt-winters = "Holt-Winters", sarima = "SARIMA", linear = "Linear Trend + Seasonality", ets = "ETS", custom-curve = "Custom Trend Curve".
- Decomposition: trend(t) = mean of the 12 values centred on t. Example: Northeast Corridor, 2022-07 trend = 1,135.33 = mean of its first 12 months.
- KPI formula: pct = (horizon_end_total - latest_total) / latest_total x 100.

## 10. Reference data and expected numbers

**ocrevus_trx_data.csv** (clean): 312 rows, columns date, month_label, year, month, ecosystem_id, ecosystem_name, product, trx; one product (Ocrevus IV), 6 ecosystems x 52 months (2022-01 to 2026-04).
- Upload shows "312 rows · 9 columns" (the derived ecosystem_product column counts), validation "6/6 pass", footer "6 ecosystems · 52 months".
- First to last month per ecosystem and Explore badge: Great Lakes 813 to 1,184 (▲ 45.6%); Mountain West 374 to 581 (▲ 55.3%); Northeast Corridor 1,006 to 1,485 (▲ 47.6%); Pacific West 1,215 to 1,650 (▲ 35.8%); Southeast 698 to 1,063 (▲ 52.3%); Southwest 550 to 823 (▲ 49.6%). National total 2026-04 = 6,786.
- Benchmark, 6-month holdout (train WAPE / test WAPE / test RMSE): ETS 1.85% / 5.42% / 63.44; SARIMA 4.82% / 5.7% / 62.16; Holt-Winters 2.8% / 8.32% / 92.03; Linear 2.91% / 12% / 140.54. ETS is the best of the four fitted methods.
- ETS, 12-month horizon: baseline 6,786, projected 6,889, net +1.5%; Great Lakes ▲ 5.4% to 1,248; Mountain West ▲ 3.4% to 601; Northeast Corridor ▲ 9.2% to 1,622; Pacific West ▼ 12.9% to 1,437; Southeast ▲ 4.4% to 1,110; Southwest ▲ 5.8% to 871. Data Table for one ecosystem shows 52 history + 12 forecast = 64 rows.

**genentech_portfolio_trx_dirty.csv** (dirty): 944 rows, 11 columns (adds therapeutic_area, nrx, nbrx), 3 products, 6 ecosystems. Planted problems: ecosystem names in many spellings (for example "NE Corridor", "Gt. Lakes", "Pac West", "PACIFIC WEST"), product names with stray spaces and case variants, five negative trx values, about 40 blank trx and one "—", exact duplicate rows, mixed date formats (2025-03-01, 07-01-2025, 01/02/2026) and four rows dated in 2028. Expected on upload: validation fails (duplicates, non-numeric, missing tolerance, history) and the analyst is told what is wrong.

**genentech_portfolio_trx_dirty_v5.csv** (the built-in sample): 939 rows, 18 ecosystem-product groups, 50 months. Validation shows "5/6 pass" (duplicates found; 5 cells missing, 2.0%, will auto-fill). "Fix with AI" removes 2 exact and 6 key duplicates (939 → 931 rows), fills 5 values, and re-validation shows 6/6.

## 11. Non-functional expectations and edge cases

- Response times observed: sign-in and page changes under 1 s; upload parse and validation under 3 s for files up to 1,000 rows; Fix with AI about 3 s; benchmark about 3 to 5 s; forecast under 2 s; deck download about 1 s. No step should exceed 30 s for the reference files.
- Errors are shown in the page in plain words, never as a blank screen, spinner that never ends, or fabricated data.
- Backend API errors are JSON ({detail} or {error:{code,message}}); wrong or missing token gives 401; unknown ids give 404; a forecast before dataset, mapping, method and horizon exist gives 422 with the missing item named.
- Accessibility: every form field has a visible label that is programmatically tied to its input; buttons have readable names; the disabled "Proceed" buttons have visible contrast; the page language is English.
- Edge cases to test: empty file; header-only file; wrong extension (.txt, .xlsx); file over 50 MB; file missing the volume or product column; non-numeric volume ("1,234", "n/a"); duplicate rows; negative volume (clipped to 0 by the fix); 3%, 10% and 30% blanks (auto-fill, auto-fill, blocked); fewer than 24 months (blocked, benchmark refuses with INSUFFICIENT_HISTORY); mixed or ambiguous dates; ensemble with one method; custom curve with blank, negative or non-numeric percentages; backend unavailable; session lost after backend restart.
- Test files: see test-files/README.md. Needed values by name: ADMIN_USERNAME, ADMIN_PASSWORD; files to attach under Settings > Test files: the CSVs listed there. Sign-in is the only login; no other test data is needed.

## 12. Known gaps (the PRD says it should; the current build does not)

1. **Rejected uploads are hidden.** For an empty file, a header-only file, a file over 50 MB or any 422/413 from the server, no error is shown. The screen shows "parsed", and for empty and header-only files it shows invented sample rows (for example a "144 rows" preview of Mountain West / Tecentriq data that is not in the file); for a 58 MB file it shows the local preview "1,092,000 rows" with empty mapping.
2. **Missing required column gives no message.** "Confirm Mapping & Run Validation" is simply disabled.
3. **A failed check can be bypassed.** After "Fix with AI", "Proceed to Analysis" becomes enabled even when the re-validation still shows a red cross (16-month file: 5/6; dirty file: 3/6).
4. **Wrong counts after the fix.** The footer shows the row count as ecosystems ("926 ecosystems · 1 months", "312 ecosystems · 52 months").
5. **Name variants are not merged.** The dirty file produces 10 product tabs and 18 "territories" for one product, with badges such as ▲ 99580.0% and ▼ 99.9%; the fix reports success but leaves 3 of 6 checks failing.
6. **Dates.** "07-01-2025" (month_label Jul-25) is read as January 2025 (day-first); years such as 2028 are accepted, so the explored range becomes 2022-01 → 2028-07 and the forecast reports history_end 2028-07, forecast start 2024-11 and +404.9%.
7. **Benchmark failure never surfaces.** If the benchmark is refused (for example 16 months of data) the Method screen stays on "Running parallel model benchmark…" while the browser repeats the failing request forever (POST 422, GET /api/benchmarks/undefined 404).
8. **Custom Trend Curve scores are invented.** Its Test WAPE is computed as 4.6 minus 0.1 x average MoM, RMSE 512 and AIC 1,876 whatever the data, so it is labelled "Best Fit" ahead of ETS (5.42%) and wins "Auto-select best" and "Combine top 2-3" with a flat 0% curve.
9. **"Export Forecast (.csv)" does nothing** (it clicks an element that does not exist). The CSV exists only at GET /api/forecast-runs/{id}/export.csv (columns Month, Ecosystem, Actual TRx, Forecasted TRx, Lower Bound, Upper Bound).
10. **Negative volumes are not flagged** by any of the six checks; they are only clipped silently by the fix. "1,234" is turned into a blank (then interpolated) rather than 1234. The 20% missing-data limit is also bypassed by the fix (30% blanks are filled).
11. **Copilot needs cloud credentials.** Without AWS Bedrock credentials every Aria message answers "Agent error: Unable to locate credentials" (shown twice on load). Aria's behaviour with credentials was not verified.
12. **Workflow vision not built.** Forecast Workflow Plan describes forecast configuration, drafts, publish, branch, event modeler, audit log and a PostgreSQL store; none of it exists in this build.
13. Smaller items: the login error for an unreachable backend always says "port 8000"; horizon choices are 6/12/18/24 though the API allows 1 to 60; prophet is accepted by the API but silently returns Holt-Winters numbers; the backend README and FRONTEND_API_DOCS describe other endpoints and file types.
