# TCS DCF Valuation App

A full-stack web app that values TCS shares with a 5-year Discounted Cash Flow (DCF) model, compares the result with the live market price, and lets anyone stress-test every assumption.

**Live:** https://quant-project-2.vercel.app

**Status:** Sessions 1 and 2 built: valuation engine, API, and the dashboard (Summary, Historical, Forecast, Valuation bridge and Sensitivity tabs, scenarios, tornado chart, shareable link). Session 3 adds Monte Carlo and Peers tabs, downloads, the case study and the v1.0 release. See [PROGRESS.md](PROGRESS.md) and [SPEC.md](SPEC.md).

## Stack

- Backend: Python 3.12, FastAPI, numpy, openpyxl (pandas and yfinance only in the data refresh job)
- Frontend: Next.js, TypeScript, Tailwind CSS, Recharts
- Hosting: Vercel (frontend and Python API in one project)
- Data: dated JSON snapshots committed to the repo

## Disclaimer

This is an educational project. Model outputs are estimates based on stated assumptions and public data, not investment, tax or financial advice.

## Run locally

```bash
make install        # Python venv and npm packages
make run            # API on http://127.0.0.1:8000
make web            # dashboard on http://localhost:3000 (second terminal)
make check          # lint, types and tests for Python
make check-web      # lint, build and types for the frontend
.venv/bin/python scripts/refresh_snapshot.py --print   # refresh data (needs network)
```

API reference: `/api/docs`. Verification steps for the engine are in [docs/verification.md](docs/verification.md).
