# Performance of the live site

Site: https://quant-project-2.vercel.app (Vercel Hobby, API region bom1). Measured from one
client in India, so the times include the network. Re-run with `python scripts/measure_latency.py`.

## API response times (F28)

20 requests per endpoint, 27 Nov 2026 18:59 UTC. POSTs vary the share price so cached results
are not what is timed. All requests returned 200.

| Endpoint | p50 (ms) | p95 (ms) |
|---|---|---|
| GET /api/health | 344 | 583 |
| GET /api/defaults | 344 | 391 |
| GET /api/historical | 350 | 392 |
| GET /api/beta | 340 | 416 |
| GET /api/peers | 365 | 395 |
| POST /api/valuation | 350 | 412 |
| POST /api/reverse-dcf | 336 | 419 |
| POST /api/sensitivity | 360 | 478 |
| POST /api/surface | 375 | 417 |
| POST /api/tornado | 364 | 389 |
| POST /api/scenarios | 342 | 359 |
| POST /api/montecarlo (10,000 runs) | 353 | 383 |
| POST /api/export | 378 | 582 |
| POST /api/report | 363 | 451 |

## First request after idle

`GET /api/health`, 27 Nov 2026 18:39 UTC, after about an hour or more without a deploy or a
test from this machine: **2.10 s**. The next request took 0.34 s. One sample only.

## Lighthouse 12

Single runs on 27 Nov 2026 (scores vary between runs).

| | Performance | Accessibility | Best practices | SEO | LCP | Blocking time | Layout shift |
|---|---|---|---|---|---|---|---|
| Mobile | MPERF | 100 | 96 | 100 | MLCP | MTBT | MCLS |
| Desktop | DPERF | DA11Y | 96 | 100 | DLCP | DTBT | DCLS |

Mobile performance is held back by the 3D library and chart code. The 3D scenes now load only
when they are near the screen (mobile score rose from 46 to the value above).
