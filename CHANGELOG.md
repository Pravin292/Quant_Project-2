# Changelog

## 1.0.0 (28 November 2026)

### Added
- Valuation engine: loader, historical ratios, forecast, WACC and regression beta, terminal value,
  bridge, warnings, reverse DCF, sensitivity, tornado, scenarios, Monte Carlo, peers.
- Excel export with live formulas and a two-page PDF report.
- FastAPI endpoints with validation, caching, rate limit and structured logs.
- Next.js dashboard: eight tabs, 3D views, football field, editable probabilities, share link,
  Screener.in upload.
- Daily data refresh, CI, live-site smoke test, case study, architecture diagram.

### Fixed
- Vercel build: dependencies declared in `pyproject.toml`, Python 3.12.
- Data refresh on cloud runners when Yahoo omits the market value.

### Not included
- AI annual-report explainer (M17, optional).
