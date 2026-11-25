# Session 1 verification guide

Everything below can be re-run with `make test` and `.venv/bin/python scripts/run_tcs.py`.

## 1. Chai Corner (SPEC section 7) reproduces
`data/samples/chai_corner.json` holds the inputs (growth 10%, EBIT margin 20%, tax 25%, D&A = CapEx = 5%, NWC 7.5%, WACC 12%, terminal growth 4%, cash 300, 100 shares).

| Item | SPEC | Engine |
|---|---|---|
| FCFF years 1-5 | 157.5, 173.3, 190.6, 209.7, 230.6 | 157.50, 173.25, 190.58, 209.63, 230.60 |
| Sum of PV | 678.5 | 678.46 |
| Terminal value | 2,997.8 | 2,997.74 |
| PV of terminal value | 1,701.0 | 1,701.00 |
| Enterprise value | 2,379.5 | 2,379.46 |
| Equity value | 2,679.5 | 2,679.46 |
| Fair value per share | 26.8 | 26.79 (rounds to 26.8) |

Note: the SPEC's year-4 FCFF (209.7) is 0.07 above the exact 10%-growth value (209.63); the SPEC table was built from rounded spreadsheet numbers. Tests allow 0.1 on those figures and require the per-share value to round to 26.8.

## 2. Compare loaded TCS financials with the annual report (you)
Run `.venv/bin/python scripts/refresh_snapshot.py --print` (or open `data/snapshots/TCS.NS_*.json`). INR crore, consolidated:

| Line | FY2023 | FY2024 | FY2025 | FY2026 |
|---|---|---|---|---|
| Revenue | 225,458 | 240,893 | 255,324 | 267,021 |
| Operating income (EBIT) | 54,377 | 59,425 | 62,293 | 67,022 |
| Tax provision | 14,604 | 15,898 | 16,534 | 16,033 |
| Net income (attributable) | 42,147 | 45,908 | 48,553 | 49,210 |
| Operating cash flow | 41,965 | 44,338 | 48,908 | 52,094 |
| CapEx | 3,100 | 2,674 | 3,937 | 4,146 |

Open TCS's annual report (Integrated Annual Report, consolidated statements) and tick each row. I could not check FY2026 or the cash-flow lines against the report myself; FY2023-FY2025 revenue and FY2025 profit agree with TCS's published results as far as I know. Definitions to compare: EBIT here is "Operating Income" (before other income); lease liabilities are the only "debt" (TCS has no borrowings).

## 3. Hand-check two ratios
* FY2026 revenue growth = 267,021 / 255,324 - 1 = 4.58%
* FY2026 EBIT margin = 67,022 / 267,021 = 25.10%
* FY2026 effective tax rate = 16,033 / 65,487 = 24.48%

## 4. Recompute cost of equity by hand
Risk-free 7.38% (FRED, India 10y, Oct 2026) + beta 0.898 x equity risk premium 7.075% (Damodaran, Jan 2026) = 7.38% + 6.355% = **13.74%**. The beta is the regression estimate (raw 0.847 from 261 weekly returns vs Nifty 50, 95% range 0.67 to 1.03) adjusted toward 1: 2/3 x 0.847 + 1/3 = 0.898. Debt weight is 1.2%, so WACC = 13.68%.

## 5. Python vs Excel
`export_workbook_bytes()` writes a workbook with live formulas and a Reconciliation sheet. `tests/test_export.py` recalculates it with an independent formula engine and compares every FCFF, the terminal value, EV, equity, fair value and all 50 sensitivity cells: they agree to 1e-12 relative. Open the exported workbook in Excel and look at Reconciliation: it should read ALL MATCH; change any blue cell and the numbers follow.

## 6. TCS result on the 25 Nov 2026 snapshot (illustrative, not advice)
Model value about INR 1,755 per share against a price of INR 2,460 (-29%). Bear / base / bull: 1,519 / 1,755 / 2,031. Monte Carlo (10,000 runs): 5th to 95th percentile 1,540 to 2,036; the probability the value exceeds the price is under 1%. Peer medians (P/E 19.0, EV/EBITDA 9.6) imply 2,590 and 1,999 per share. The reverse DCF says the price needs about 16.7% revenue growth a year for 5 years. Terminal value is 67% of EV. WACC is the biggest driver (one point moves value by about 392 per share across the +/-1 point range). The ROIC check warns that year-5 reinvestment (0.6% of NOPAT) is far below what 5% growth needs at a 65% ROIC: CapEx (1.4% of revenue) is below D&A (2.1%) because D&A includes lease amortisation while lease additions are not in CapEx. The value-driver terminal value gives 1,673.

These results mostly say the market is pricing in more growth or a lower discount rate than this model assumes. The 13.7% cost of equity (Indian 10y yield 7.38% plus a 7.1% India ERP) is the most debatable input.
