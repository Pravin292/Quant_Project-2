"""Glue between HTTP routes and the engine: snapshot lookup, caching, JSON clean-up.

No finance formulas live here; every number comes from ``src/dcf``.
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dcf import defaults, historical, loader, peers, scenarios
from dcf.config import load_config
from dcf.exceptions import DataUnavailableError
from dcf.loader import Snapshot

ROOT = Path(__file__).resolve().parent.parent
_PRICE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def jsonable(value: Any) -> Any:
    """Plain JSON: dataclasses to dicts, tuples to lists, NaN and infinity to null."""
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def snapshots_dir() -> Path:
    return ROOT / str(load_config()["paths"]["snapshots_dir"])


def default_ticker() -> str:
    return str(load_config()["company"]["ticker"])


@lru_cache(maxsize=16)
def snapshot(ticker: str) -> Snapshot:
    """Latest committed snapshot. Only tickers that have a snapshot file are accepted."""
    available = loader.list_snapshot_tickers(snapshots_dir())
    if ticker not in available:
        raise DataUnavailableError(
            f"No data for {ticker}. Available tickers: {', '.join(available)}."
        )
    return loader.load_snapshot(ticker, snapshots_dir())


def peer_snapshots(ticker: str) -> list[Snapshot]:
    cfg = load_config()
    group = [default_ticker(), *cfg["peers"]]
    return peers.load_peer_snapshots(snapshots_dir(), [t for t in group if t != ticker])


def live_price(ticker: str) -> dict[str, Any]:
    """Live quote with snapshot fallback, cached briefly to avoid hammering the source."""
    ttl = load_config()["api"]["price_cache_seconds"]
    hit = _PRICE_CACHE.get(ticker)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    quote = loader.fetch_live_price(ticker, snapshot(ticker))
    _PRICE_CACHE[ticker] = (time.monotonic(), quote)
    return quote


def history(ticker: str) -> historical.Historical:
    return historical.compute_historical(snapshot(ticker))


def scenario_specs(ticker: str | None) -> dict[str, scenarios.ScenarioSpec]:
    return scenarios.build_specs(history(ticker or default_ticker()))


def company(ticker: str) -> dict[str, Any]:
    snap = snapshot(ticker)
    return {
        "ticker": ticker,
        "name": snap.get("name") or ticker,
        "source": snap.get("source"),
        "fetched_at": snap.get("fetched_at"),
        "fiscal_years": snap["fiscal_years"],
        "quality_warnings": snap.get("quality_warnings", []),
    }


def default_bundle(ticker: str) -> dict[str, Any]:
    snap = snapshot(ticker)
    quote = live_price(ticker)
    bundle = defaults.build_defaults(snap, peer_snapshots(ticker), price=quote["price"])
    return {
        "company": company(ticker),
        "assumptions": {**asdict(bundle.inputs), "ticker": ticker},
        "sources": bundle.sources,
        "price": quote,
        "week_52": {k: snap["market"].get(k) for k in ("week52_low", "week52_high")},
        "beta": bundle.beta,
        "scenarios": scenarios.build_specs(bundle.historical),
        "bounds": load_config()["bounds"],
        "tickers": loader.list_snapshot_tickers(snapshots_dir()),
    }
