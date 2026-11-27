# Live response times

Single requests from one client in India to https://quant-project-2.vercel.app on 27 Nov 2026, just after a deploy, including network time. All returned 200. A p50 / p95 table (F28) comes in Session 3.

| Endpoint | Seconds |
|---|---|
| GET /api/defaults (live price) | 0.66 |
| GET /api/historical | 0.62 |
| GET /api/beta | 0.76 |
| GET /api/peers | 0.62 |
| POST /api/valuation | 0.37 |
| POST /api/reverse-dcf | 0.36 |
| POST /api/sensitivity | 0.46 |
| POST /api/tornado | 0.55 |
| POST /api/scenarios | 0.38 |
| POST /api/montecarlo (10,000 runs) | 0.48 |
| POST /api/export | 0.68 |

Not measured: a first request after a long idle period.
