# M9: Vercel feasibility spike

## Measured locally (macOS arm64, Python 3.14; Vercel Linux numbers must be confirmed on deploy)
| Setup | site-packages | Cold start: imports + full valuation + 10k Monte Carlo + Excel export |
|---|---|---|
| Original plan: numpy, pandas, yfinance, openpyxl, pydantic, fastapi | 198 MB | about 9.5 s for the imports alone |
| Lean runtime (this repo): numpy, openpyxl, pydantic, fastapi, pyyaml | 67 MB (13 MB of that is pip) | 1.9 s for everything |

Decision: the API function does not use pandas or yfinance. The data snapshot job (`scripts/refresh_snapshot.py`, GitHub Action) uses them (`requirements-data.txt`); the live price comes from Yahoo's chart endpoint over plain HTTP with a fallback to the snapshot price. Vercel's Python function limit is 250 MB uncompressed, so the original plan was close to the limit and slow to start; the lean one has about 4x headroom.

## What is in the repo
* `api/index.py`: FastAPI app with `GET /api/health` (reports Python version, import time, snapshot date, whether pandas was loaded).
* `vercel.json`: rewrites `/api/*` to the function and includes `src/`, `data/snapshots/` and `config.yaml` in the bundle (`includeFiles`).
* `requirements.txt`: lean runtime; `requirements-data.txt`: pandas + yfinance for the refresh job; `requirements-dev.txt`: everything plus test tools.

## Still to do (needs your Vercel account)
1. vercel.com/new -> import `Pravin292/Quant_Project-2`, framework preset "Other", root directory = repo root.
2. Open `https://<your-project>.vercel.app/api/health`. Expect `"status": "ok"` and `pandas_loaded: false`.
3. Note the response time of the first request after idle (cold start) and a warm request, and the bundle size in the deployment's Functions tab. Record them in this file.
4. If `includeFiles` is not honoured (health returns a 500 about a missing snapshot or config), tell Claude; the fallback is to host only the API on Render or Railway (SPEC section 2).


## Status 26 Nov 2026
Tried to do the import from the in-app browser: vercel.com showed the signed-out page (Continue with GitHub). Signing in needs your credentials, so the import and the timings are still open. Sign in once in the browser pane and Claude can finish steps 1-3.

## Finding 26 Nov 2026: first deploy returned 500
Runtime log: `ModuleNotFoundError: No module named 'fastapi'`. Vercel installs from `pyproject.toml` when it exists, and ours had no `dependencies`, so `requirements.txt` was ignored. Fix: list the runtime dependencies in `pyproject.toml` (must stay identical to `requirements.txt`).
Second failure: `uv lock` could not resolve numpy 2.5.5 (needs Python 3.12+) against `requires-python >=3.11`. Fix: `requires-python >=3.12` (CI already uses 3.12; Vercel runs 3.12).

## RESULT 26 Nov 2026: spike passed
Deployed at https://quant-project-2.vercel.app (Python 3.12.16, region bom1, Hobby plan). `/api/health` returns 200 with `status: ok`, snapshot TCS.NS 2026-11-25, `pandas_loaded: false`, so `includeFiles` is honoured and the lean runtime works.

| Measure | Value |
|---|---|
| In-function import time (`import_seconds`) | 0.354 s |
| First request after deploy, measured from Pravin's Mac (includes network) | 0.86 s |
| Next two requests | 0.62 s, 0.68 s |
| Build time | 14 s |
| Bundle size | not read from the dashboard |

Decision: Vercel hosts the API; the Render/Railway fallback is not needed.
