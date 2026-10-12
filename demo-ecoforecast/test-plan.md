# Playbook: EcoForecast (ForecastIQ) - Agentic Short Term Forecast
base_url: https://ecosystem-forecast.vercel.app

## Requirements
### REQ-1: User authentication and session management
- prd_ref: Section 3
- acceptance: Sign-in with valid credentials lands on Setup; invalid credentials show error message; session token lasts 24 hours; sign out returns to login
- priority: critical

### REQ-2: Forecast horizon selection
- prd_ref: Section 4
- acceptance: User can select from 6, 12, 18, 24 months; horizon is saved to server; configuration shows correct end date
- priority: high

### REQ-3: CSV file upload and parsing
- prd_ref: Section 5.1
- acceptance: Accept .csv files up to 50MB; reject other extensions with alert; show file details after parse; provide sample dataset option
- priority: critical

### REQ-4: Column mapping for required fields
- prd_ref: Section 5.2
- acceptance: Auto-detect and map Date, Region/Ecosystem, Volume, Product columns; enable validation only when all four mapped
- priority: critical

### REQ-5: Six integrity checks validation
- prd_ref: Section 5.4
- acceptance: Run checks for column mapping, date parsing, duplicates, numeric volume, missing values ≤20%, minimum 24 months history
- priority: critical

### REQ-6: AI-powered data fixing
- prd_ref: Section 5.5
- acceptance: Fix duplicates, coerce volume to numbers, normalize dates, fill blanks, clip negatives; show before/after summary
- priority: high

### REQ-7: Data exploration with visualizations
- prd_ref: Section 6
- acceptance: Display ecosystem cards with latest TRx and percentage change; show Raw TRx, Trend, and Seasonal charts for selected ecosystem
- priority: high

### REQ-8: Model benchmarking and evaluation
- prd_ref: Section 7
- acceptance: Automatically benchmark 4 methods (Holt-Winters, SARIMA, Linear Trend, ETS); display evaluation matrix with WAPE and RMSE scores
- priority: high

### REQ-9: Forecasting strategy commitment
- prd_ref: Section 7
- acceptance: Allow selection of single method, ensemble of 2-3 methods, or auto-select best; commit strategy to proceed
- priority: critical

### REQ-10: Forecast generation and visualization
- prd_ref: Section 8
- acceptance: Generate forecasts with 95% confidence intervals; display KPI tiles, multiple views (Chart, Data Table, Treemap); show ecosystem projections
- priority: critical

### REQ-11: PowerPoint deck generation
- prd_ref: Section 8
- acceptance: Generate and download executive-ready .pptx file named forecastiq_<id>.pptx
- priority: high

### REQ-12: Forecast export
- prd_ref: Section 8
- acceptance: "Export Forecast (.csv)" downloads the forecast rows as a CSV file
- priority: high

### REQ-13: Rejected uploads are reported
- prd_ref: Section 5.1
- acceptance: A file that cannot be used (empty, no data rows, missing a required column) is rejected with a plain-words message and no invented data is shown
- priority: critical

## UX rules
### UX-1: No step waits longer than 20 seconds
- check: max_wait
- max_ms: 20000
- severity: medium

## Gotchas
### G-1: The app keeps everything in server memory
- note: Reloading the page or opening the address again returns to the Setup step and forgets the data. Every journey therefore starts at Setup and must do its own upload; never reload mid-journey.

### G-2: The Aria copilot panel is not part of these journeys
- note: Ignore the copilot panel on the right. Do not type into it.

### G-3: Blocked requests from the browser inspector are noise
- ignore_console: ERR_BLOCKED_BY_CLIENT

## Edge cases
### EC-1: A file with only a header row
- applies_to: upload-rejected-files
- expect: The app says the file has no data. It does not show sample rows that are not in the file.
- covers: REQ-13
- test_data: file=header_only.csv

### EC-2: A file without the product column
- applies_to: upload-rejected-files
- expect: The user is told that a required column (product) is missing, or the problem is clearly explained. The page does not just stay silent.
- covers: REQ-4, REQ-13
- test_data: file=missing_product_column.csv

### EC-3: Volume values that are not numbers
- applies_to: upload-rejected-files
- expect: Validation fails and the message names the volume column as having non-numeric values.
- covers: REQ-5
- test_data: file=non_numeric_trx.csv

## Flows
### Flow: sign-in
- covers: REQ-1
- severity: critical
- role: setup

#### Goal
Sign in with the saved sign-in details and reach the Setup screen.

#### Expect
- The Setup screen shows the forecast horizon choices (6, 12, 18, 24 months)
- The header shows the username and a Sign out button

### Flow: clean-forecast-end-to-end
- covers: REQ-2, REQ-3, REQ-4, REQ-5, REQ-7, REQ-8, REQ-9, REQ-10
- checks: UX-1
- severity: critical

#### Goal
Pick a 12 month horizon, upload the clean data file from the test data, confirm the column mapping and validation, go through Explore and Method (let the benchmark finish, then select the ETS row in the Model Evaluation Matrix and use Use selected method), and reach the Forecast screen.

#### Expect
- Validation shows 6/6 pass and the footer says 6 ecosystems and 52 months
- On Explore the Great Lakes card shows an increase of about 45.6% and the Pacific West card about 35.8%
- The benchmark finishes with status ready and the Model Evaluation Matrix lists the four fitted methods (Holt-Winters, SARIMA, Linear Trend + Seasonality, ETS) with WAPE scores
- The Forecast screen shows the method ETS, a national baseline of 6,786 and a projected horizon of about 6,889, a net growth of about 1.5%
- The Chart, Data Table and Treemap views can all be opened

#### Test data
- file: ocrevus_trx_data.csv

### Flow: export-forecast
- covers: REQ-11, REQ-12
- severity: high

#### Goal
Reach the Forecast screen with the clean data file from the test data and a 12 month horizon (select the ETS row and use Use selected method), then use Generate Deck (.pptx) and Export Forecast (.csv).

#### Expect
- Generate Deck (.pptx) starts a download of a .pptx file
- Export Forecast (.csv) starts a download of a CSV file

#### Test data
- file: ocrevus_trx_data.csv

### Flow: upload-rejected-files
- covers: REQ-3, REQ-13
- severity: critical

#### Goal
On the Upload screen (after choosing a 12 month horizon), upload the file named in the test data and see how the app reacts. Stop once the app has shown a result or an error.

#### Expect
- The app tells the user in plain words that the file was rejected or has no data
- The screen does not show a parsed preview with rows that are not in the file

#### Test data
- file: empty.csv

### Flow: fix-with-ai-sample
- covers: REQ-5, REQ-6
- severity: high

#### Goal
After choosing a 12 month horizon, load the built-in sample dataset on the Upload screen, confirm the column mapping so validation runs, then use Fix with AI and read the result.

#### Expect
- The fix summary shows the row count going down from 939 to 931 rows and the re-validation list shows 6/6 pass
- Proceed to Analysis is enabled after the fix

### Flow: short-history-blocked
- covers: REQ-5, REQ-6
- severity: high

#### Goal
After choosing a 12 month horizon, upload the file from the test data, confirm the column mapping so validation runs, then click Fix with AI and look at what the screen allows.

#### Expect
- The check for at least 24 months of history is reported as failed
- Proceed to Analysis stays disabled while any integrity check still fails

#### Test data
- file: short_history_16mo.csv

### Flow: custom-curve-honesty
- covers: REQ-8, REQ-9
- severity: medium

#### Goal
Reach the Method screen with the clean data file from the test data and a 12 month horizon, wait for the benchmark, then in the custom month-on-month table click Reset All (0%), look at the Custom Trend Curve row of the Model Evaluation Matrix, then click Set Baseline (+2%) and look at that row again.

#### Expect
- With a flat 0% curve the Custom Trend Curve is ranked below the data-driven methods and is not labelled Best Fit
- Changing the percentages changes the Custom Trend Curve's Test WAPE, Test RMSE and AIC, because they are computed from the data and the curve
- Auto-select best chooses a data-driven method, not the Custom Trend Curve

#### Test data
- file: ocrevus_trx_data.csv
