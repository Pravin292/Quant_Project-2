# Progress and handoff

Read SPEC.md first. Work one milestone at a time on branch `mNN-name`; merge to `main` when its checks pass.

**Working copy:** Session 1 was built in a temporary clone, not in a local project folder. Start the next session by cloning `https://github.com/Pravin292/Quant_Project-2.git`, then `make install` (Python 3.11+; tested on 3.14 locally, 3.12 in CI).

## Session plan (rebalanced so nothing is cut)
- **Session 1:** M1-M8 engine (every module in `src/dcf`), plus the M9 Vercel spike code.
- **Session 2:** full API (all endpoints, thin routes over the engine), Next.js dashboard core tabs, charts, tornado, share link, Vercel deploy, API performance work (F28 backend).
- **Session 3:** Monte Carlo / Peers / Football field / Methodology tabs, Excel and PDF download, ticker input, README, case study, smoke test, snapshot Action, AI explainer, v1.0 release.

## Status
| Milestone | State |
|---|---|
| M1 skeleton, CI | done |
| M2 loader (F1) | done: yfinance, Screener upload parser, dated snapshots for TCS + 4 peers, FX handling, quality checks |
| M3 historical (F2) | done, incl. invested capital and ROIC |
| M4 forecast (F3) | done, Chai Corner reproduces |
| M5 WACC (F4, F19) | done, regression beta with 95% range, Blume adjustment, sources logged |
| M6 terminal + bridge (F5, F6, F18, F20) | done: Gordon, exit multiple, ROIC check, value-driver TV, reverse DCF, warnings |
| M7 sensitivity (F7, F22) | done: two grids, tornado, scenarios (F10, F26 weights) |
| M8 validation (F8, F27) | done: Monte Carlo (F14), peers (F15), Excel export with live formulas (F12), reconciliation, property tests |
| M9 Vercel spike | code and local measurements done; live URL needs you (see docs/m09-vercel-spike.md) |

## Decisions made in Session 1 (all documented in code and docs)
* EBIT = "Operating Income" (before treasury other income; cash goes in the bridge). Leases are debt in the bridge.
* NWC = receivables + inventory - payables; NWC % is the level over revenue and dNWC = NWC% x change in revenue.
* Risk-free = FRED/OECD India 10y (monthly); ERP = Damodaran India total ERP; both fetched, stored with source and date in each snapshot. Beta by regression on 5 years of weekly returns vs Nifty 50.
* Defaults: growth = historical mean fading linearly to terminal growth; margin = historical mean; terminal growth 5% (config), capped by the risk-free rate and WACC - 2 points; exit multiple = median peer EV/EBITDA.
* Scenario swings = half the historical spread with a 1.5 point floor and 5 point cap; WACC fixed. Monte Carlo WACC sd comes from beta's standard error.
* API runtime is lean (no pandas/yfinance) for Vercel; `requirements-data.txt` is for the refresh job.

## Known limits to carry forward
* Screener parser tested on a synthetic workbook that mimics the Data Sheet layout, not a real download.
* Infosys statements come in USD from Yahoo (converted with fiscal-year-average rates); HCLTech is mislabelled USD (detected by P/E sanity check).
* TCS default valuation flags the ROIC reinvestment warning (lease amortisation inside D&A but lease additions outside CapEx). See docs/verification.md.
* Live-quote endpoint (Yahoo chart API) is unofficial; fallback to the snapshot price exists.

## Next: Session 2
M10 API (all endpoints: historical, valuation, sensitivity, scenarios, montecarlo, peers, export, plus reverse DCF, tornado, beta), M11 Next.js shell, M12 scenarios and charts, F22 tornado chart, F23 shareable link, F28 backend (cache, logs, rate limit), Vercel deploy.
