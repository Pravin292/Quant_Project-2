# TCS DCF Valuation App

A full-stack web app that values TCS shares with a 5-year Discounted Cash Flow (DCF) model, compares the result with the live market price, and lets anyone stress-test every assumption.

**Status:** planning complete, build starting. See [SPEC.md](SPEC.md) for the full project document: scope, architecture, formulas, milestones, testing plan and final checklist.

## Planned stack

- Backend: Python 3.11+, FastAPI, pandas, numpy, yfinance
- Frontend: Next.js, TypeScript, Tailwind CSS, Recharts
- Hosting: Vercel (frontend and Python API in one project)
- Data: daily JSON snapshot refreshed by GitHub Actions

## Roadmap

| Session | Goal |
| --- | --- |
| 1 | Verified valuation engine (milestones M1 to M8) |
| 2 | Deployed API and dashboard core (M9 to M12) |
| 3 | Excel export, Monte Carlo, peer multiples, shipping (M13 to M17) |

Live demo, screenshots, architecture diagram, validation results and limitations will be added here as the milestones are completed.

## Disclaimer

This is an educational project. Model outputs are estimates based on stated assumptions and public data, not investment, tax or financial advice.
