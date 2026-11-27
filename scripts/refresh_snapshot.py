"""Fetch fresh data and write dated JSON snapshots for the main ticker and its peers.

Usage: python scripts/refresh_snapshot.py [--print] [--tickers TCS.NS INFY.NS]
Run from the repo root. Used by the daily GitHub Action (refresh-snapshot.yml).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dcf import loader  # noqa: E402
from dcf.exceptions import DataUnavailableError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", nargs="*", help="override tickers from config.yaml")
    parser.add_argument("--print", action="store_true", dest="show", help="print statement tables")
    args = parser.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    tickers = args.tickers or [cfg["company"]["ticker"], *cfg["peers"]]
    out_dir = ROOT / cfg["paths"]["snapshots_dir"]
    index_ticker = cfg["benchmark_index"]

    macro = loader.fetch_macro_inputs()
    try:  # if a macro source is down, reuse the last good value (it keeps its own date and source)
        previous = loader.load_snapshot(cfg["company"]["ticker"], out_dir).get("macro", {})
    except DataUnavailableError:
        previous = {}
    for key in ("risk_free", "equity_risk_premium"):
        if key not in macro and key in previous:
            macro[key] = {**previous[key], "carried_over": True}
            print(f"WARNING: {key} fetch failed; carried over the previous value", file=sys.stderr)
    failures = 0
    for ticker in tickers:
        try:
            raw = loader.fetch_yfinance(ticker, index_ticker)
            snap = loader.build_snapshot(
                ticker, raw, fy_end_month=cfg["company"]["fiscal_year_end_month"]
            )
            snap["macro"] = macro
            path = loader.save_snapshot(snap, out_dir)
            loader.prune_snapshots(ticker, out_dir, cfg["snapshots_to_keep"])
            print(f"saved {path.relative_to(ROOT)} ({len(snap['quality_warnings'])} warnings)")
            if args.show:
                print(loader.format_tables(snap))
        except DataUnavailableError as exc:
            failures += 1
            print(f"FAILED {ticker}: {exc}", file=sys.stderr)
    return 1 if failures == len(tickers) else 0


if __name__ == "__main__":
    raise SystemExit(main())
