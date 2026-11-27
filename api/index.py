"""FastAPI app (F9). Routes only validate input and call src/dcf; no finance logic here."""

from __future__ import annotations

import os
import sys
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_BOOT = time.perf_counter()

from fastapi import FastAPI, Query, Request, Response  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from api import schemas, service  # noqa: E402
from api.middleware import error_response, guard  # noqa: E402
from dcf import (  # noqa: E402
    __version__,
    export,
    montecarlo,
    peers,
    scenarios,
    sensitivity,
    valuation,
)
from dcf.config import load_config  # noqa: E402
from dcf.exceptions import DataUnavailableError, InvalidAssumptionError  # noqa: E402
from dcf.wacc import beta_from_snapshot  # noqa: E402

app = FastAPI(
    title="TCS DCF Valuation API",
    version=__version__,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
_IMPORT_SECONDS = time.perf_counter() - _BOOT

# The dashboard is served from the same origin; other origins must be listed explicitly.
_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
app.middleware("http")(guard)
app.add_middleware(  # added last, so it also wraps the guard's error responses
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(InvalidAssumptionError)
def _invalid(_: Request, exc: InvalidAssumptionError) -> JSONResponse:
    return error_response(422, "INVALID_ASSUMPTION", str(exc))


@app.exception_handler(DataUnavailableError)
def _unavailable(_: Request, exc: DataUnavailableError) -> JSONResponse:
    return error_response(503, "DATA_UNAVAILABLE", str(exc))


@app.exception_handler(RequestValidationError)
def _malformed(_: Request, exc: RequestValidationError) -> JSONResponse:
    parts = []
    for err in exc.errors()[:3]:
        where = ".".join(str(p) for p in err["loc"] if p != "body") or "request"
        parts.append(f"{where}: {err['msg']}")
    return error_response(422, "INVALID_REQUEST", "; ".join(parts))


# Results of POST endpoints are deterministic for a given deployment, so cache them.
_CACHE: OrderedDict[str, Any] = OrderedDict()


def _cached(response: Response, key: str, compute: Callable[[], Any]) -> Any:
    if key in _CACHE:
        _CACHE.move_to_end(key)
        response.headers["X-Cache"] = "hit"
        return _CACHE[key]
    result = service.jsonable(compute())
    _CACHE[key] = result
    while len(_CACHE) > load_config()["api"]["result_cache_entries"]:
        _CACHE.popitem(last=False)
    response.headers["X-Cache"] = "miss"
    return result


def _checked(a: schemas.Assumptions) -> valuation.ValuationInputs:
    """Engine inputs, with the hard bounds enforced before any calculation."""
    inputs = a.to_inputs()
    valuation.validate_inputs(inputs)
    return inputs


def _ticker(value: str | None) -> str:
    return value or service.default_ticker()


TickerQuery = Query(default=None, pattern=r"^[A-Za-z0-9._^&-]{1,20}$")


@app.get("/api/health")
def health() -> dict[str, object]:
    """Liveness plus the facts the deployment check needs."""
    snap = service.snapshot(service.default_ticker())
    return {
        "status": "ok",
        "engine_version": __version__,
        "python": sys.version.split()[0],
        "import_seconds": round(_IMPORT_SECONDS, 3),
        "snapshot": {"ticker": snap["ticker"], "fetched_at": snap["fetched_at"]},
        "pandas_loaded": "pandas" in sys.modules,
    }


@app.get("/api/defaults")
def get_defaults(ticker: str | None = TickerQuery) -> Any:
    """Default assumptions for a company, with the source of every number and the price."""
    return service.jsonable(service.default_bundle(_ticker(ticker)))


@app.get("/api/historical")
def get_historical(ticker: str | None = TickerQuery) -> Any:
    t = _ticker(ticker)
    h = service.history(t)
    return service.jsonable(
        {
            "company": service.company(t),
            "years": h.table(),
            "summary": h.summary,
            "sources": h.sources,
        }
    )


@app.get("/api/beta")
def get_beta(ticker: str | None = TickerQuery) -> Any:
    t = _ticker(ticker)
    snap = service.snapshot(t)
    return service.jsonable(
        {
            "ticker": t,
            "index": snap["prices_weekly"]["index_ticker"],
            "beta": beta_from_snapshot(snap),
        }
    )


@app.get("/api/peers")
def get_peers(ticker: str | None = TickerQuery) -> Any:
    t = _ticker(ticker)
    return service.jsonable(peers.peer_cross_check(service.snapshot(t), service.peer_snapshots(t)))


@app.post("/api/valuation")
def post_valuation(body: schemas.Assumptions, response: Response) -> Any:
    return _cached(
        response,
        "valuation:" + body.model_dump_json(),
        lambda: valuation.run_valuation(body.to_inputs()),
    )


@app.post("/api/reverse-dcf")
def post_reverse_dcf(body: schemas.ReverseDcfRequest, response: Response) -> Any:
    return _cached(
        response,
        "reverse:" + body.model_dump_json(),
        lambda: valuation.reverse_dcf(_checked(body.assumptions), body.target_price),
    )


@app.post("/api/sensitivity")
def post_sensitivity(body: schemas.Assumptions, response: Response) -> Any:
    def compute() -> dict[str, Any]:
        inputs = _checked(body)
        valuation.run_valuation(inputs)  # a clear error if the base case itself is impossible
        return {
            "wacc_growth": sensitivity.wacc_growth_grid(inputs),
            "growth_margin": sensitivity.growth_margin_grid(inputs),
        }

    return _cached(response, "sensitivity:" + body.model_dump_json(), compute)


# Finer steps than the tables, for the 3D surface: WACC +/-3 points, growth +/-2 points.
_SURFACE_WACC = tuple(i * 0.0025 for i in range(-12, 13))
_SURFACE_GROWTH = tuple(i * 0.0025 for i in range(-8, 9))


@app.post("/api/surface")
def post_surface(body: schemas.Assumptions, response: Response) -> Any:
    """Fair value over a fine WACC x terminal growth mesh."""

    def compute() -> dict[str, Any]:
        inputs = _checked(body)
        valuation.run_valuation(inputs)
        return sensitivity.wacc_growth_grid(inputs, _SURFACE_WACC, _SURFACE_GROWTH)

    return _cached(response, "surface:" + body.model_dump_json(), compute)


@app.post("/api/tornado")
def post_tornado(body: schemas.TornadoRequest, response: Response) -> Any:
    def compute() -> dict[str, Any]:
        inputs = _checked(body.assumptions)
        valuation.run_valuation(inputs)
        return sensitivity.tornado(inputs, body.delta)

    return _cached(response, "tornado:" + body.model_dump_json(), compute)


@app.post("/api/scenarios")
def post_scenarios(body: schemas.ScenarioRequest, response: Response) -> Any:
    def compute() -> dict[str, Any]:
        a = body.assumptions
        inputs = _checked(a)
        specs = service.scenario_specs(a.ticker)
        out = scenarios.run_scenarios(inputs, specs, body.probabilities)
        for name, row in out["scenarios"].items():  # the exact inputs behind each case
            adjusted = asdict(scenarios.apply_scenario(inputs, specs[name]))
            row["assumptions"] = {**adjusted, "ticker": a.ticker}
        return out

    return _cached(response, "scenarios:" + body.model_dump_json(), compute)


@app.post("/api/montecarlo")
def post_montecarlo(body: schemas.MonteCarloRequest, response: Response) -> Any:
    def compute() -> dict[str, Any]:
        a = body.assumptions
        inputs = _checked(a)
        t = _ticker(a.ticker)
        bull = service.scenario_specs(t)["bull"]
        cfg = load_config()["monte_carlo"]
        settings = montecarlo.settings_from_context(
            bull.growth_shift,
            bull.margin_shift,
            beta_from_snapshot(service.snapshot(t)).std_error,
            inputs.wacc.equity_risk_premium,
            runs=body.runs or cfg["runs"],
            seed=cfg["seed"] if body.seed is None else body.seed,
        )
        return montecarlo.run_monte_carlo(inputs, settings)

    return _cached(response, "montecarlo:" + body.model_dump_json(), compute)


@app.post("/api/export")
def post_export(body: schemas.ExportRequest) -> Response:
    """The full model as an Excel workbook with live formulas."""
    a = body.assumptions
    inputs = _checked(a)
    t = _ticker(a.ticker)
    company = service.company(t) if a.ticker else {"name": "Custom model", "ticker": ""}
    data = export.export_workbook_bytes(
        inputs, valuation.run_valuation(inputs), {**company, "sources": inputs.wacc.sources}
    )
    stem = "".join(c for c in (a.ticker or "model") if c.isalnum() or c in "._-")
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{stem}_dcf.xlsx"'},
    )
