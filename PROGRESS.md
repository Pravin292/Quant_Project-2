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
| M9 Vercel spike | done: deployed and measured (docs/m09-vercel-spike.md) |

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

## Session 2
Deployed at https://quant-project-2.vercel.app and checked there (see docs/performance.md).

| Item | State |
|---|---|
| M10 API | done: all endpoints, strict models, 422/503 errors, CORS, size and rate limits, cache, JSON logs |
| M11 frontend shell | done: inputs panel (drawer on phones), Summary, Historical, Forecast tabs, typed client |
| M12 scenarios and charts | done: scenario switch, FCFF chart, waterfall, two heatmaps, tornado (F22), share link (F23) |

Notes: F28 rate limit and cache are per server instance. Set `ALLOWED_ORIGINS` only if another origin must call the API. Tickers are limited to committed snapshots.

## Session 3 (in progress)
| Item | State |
|---|---|
| High-fidelity design and 3D (owner request, beyond SPEC) | done: new theme, hero, 3D valuation surface (Summary, Sensitivity), 3D histogram, 3D peer view; flat tables kept for every 3D view |
| M13 Excel download and ticker field | done; owner to open the file in Excel and confirm live formulas |
| M14 Monte Carlo tab | done: median within a rupee or two of base, percentile table, caveat |
| M15 Peers tab | done: implied values, timestamps |
| M16 ship | next: snapshot Action, README with screenshots and p50/p95, architecture diagram, case study PDF, repo polish, v1.0 |
| Priority A left | F21 football field, probability editing UI (F26), p50/p95 table (F28) |
| Priority B / optional | F24 Methodology tab, F25 PDF report, F29 smoke test, M17 AI explainer (needs an LLM API key), Screener upload in the UI |
