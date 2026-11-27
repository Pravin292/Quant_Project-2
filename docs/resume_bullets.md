# Resume bullets (measured on 27 Nov 2026)

- Built and deployed a full-stack DCF valuation app for TCS (Next.js, FastAPI, Python) on Vercel
  with a 5-year free-cash-flow model, WACC calculator and terminal-value cross-checks;
  live at https://quant-project-2.vercel.app
- Wrote 131 unit, property-based and API tests plus 3 end-to-end tests, and reconciled the model
  to an Excel rebuild recalculated by an independent formula engine, matching to about 1e-12
- Implemented a 10,000-run Monte Carlo simulation (vectorised NumPy) that reports fair value as a
  percentile range; median API response about 0.35 s
- Added peer-multiple cross-checks against 4 IT-services companies and a sensitivity heatmap over
  WACC and terminal growth, with a daily automated data refresh

Only claim what you can explain: go through section 7 and the questions in section 14.2 of SPEC.md.
