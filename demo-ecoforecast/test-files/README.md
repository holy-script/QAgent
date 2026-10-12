# EcoForecast test files (all verified in the running app, UI at http://localhost:3010)

One line each: file, what it is for, what the app should do (and what it does today where that differs).

- `ocrevus_trx_data.csv`: clean, 1 product x 6 ecosystems x 52 months (312 rows). Should parse, map automatically, pass 6/6, forecast end to end (ETS 12 months: 6,786 to 6,889, +1.5%).
- `clean_valid_3eco_36mo.csv`: clean, 3 ecosystems x 36 months (108 rows). Should pass 6/6 ("3 ecosystems · 36 months"); quick happy-path file.
- `genentech_portfolio_trx_clean.csv`: clean, 3 products x 6 ecosystems x 52 months (936 rows). Should pass 6/6; use it for the multi-product pickers, product tabs and treemap.
- `genentech_portfolio_trx_dirty.csv`: very dirty (name variants, mixed dates, blanks, duplicates, negatives, 2028 dates; 944 rows). Should fail validation, say what is wrong and not forecast nonsense. Today "Fix with AI" leaves 3/6 failing yet allows Proceed (a planted-bug showcase).
- `duplicates_and_negatives.csv`: ocrevus data with 3 duplicate rows and 2 negative values (315 rows). Should flag duplicates (5/6) and, after "Fix with AI", show "315 to 312 rows", 6/6 and "Clipped 2 negative TRx value(s) to 0". Negatives are not flagged before the fix.
- `non_numeric_trx.csv`: two bad volume cells ("1,234" and "n/a"). Should fail the numbers check (5/6); the fix blanks them and interpolates.
- `missing_3pct.csv` / `missing_10pct.csv`: random blanks (12 and 30 cells). Should pass with a warning "will auto-fill" and report cells auto-filled.
- `missing_30pct.csv`: 30.8% blanks in the worst series. Should block ("exceeds 20% threshold"); today the fix fills 96 values anyway.
- `short_history_16mo.csv`: only 16 months (96 rows). Should fail "Minimum 24 months" and never reach a benchmark; today Fix then Proceed is allowed and the Method screen hangs on "Running parallel model benchmark…".
- `missing_trx_column.csv`: no `trx` column. Should say the volume column is missing; today "Confirm Mapping & Run Validation" is just disabled.
- `missing_product_column.csv`: no `product` and no ecosystem name column. Same expectation and behaviour as above (Product / Brand unmapped).
- `empty.csv`: zero bytes. Should show an error (server says 422 "File has no data rows"); today the screen shows invented rows.
- `header_only.csv`: header and no rows. Same as `empty.csv`.
- `not_a_csv.txt`, `fake_excel.xlsx`: wrong types. Should be refused: a browser alert "Unsupported file. Only CSV files (.csv) are allowed." and no upload (works).
- `clean_qc_test_data.csv`: the backend's own QC fixture (588 rows, 7 ecosystems, 5 products, 28 months, 2024-01 to 2026-04); not run through the UI here.

Not included (too big): a file over 50 MB. Make one by repeating the data rows of `ocrevus_trx_data.csv` about 3,500 times (58 MB worked): the server answers 413 and the app shows no error.
The built-in "Load sample dataset" button is a further test file (939 rows, 5/6 pass, fixable to 6/6) and needs no attachment.
