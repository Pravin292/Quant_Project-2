"""Peer multiples cross-check (F15): P/E and EV/EBITDA versus similar companies.

    P/E        = Market cap / Net income (latest fiscal year)
    EV/EBITDA  = (Market cap + Debt incl. leases - Cash & investments + Minority) / EBITDA

Leases are treated as debt on both sides (consistent with the DCF bridge). Every figure
carries the snapshot fetch time. Peers differ in size, growth and mix; the UI says so.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dcf.exceptions import DataUnavailableError
from dcf.loader import CRORE, Snapshot, diluted_shares, latest_value, load_snapshot

NOTE = (
    "Peers differ in size, growth, client mix and margins; multiples are a sanity check, "
    "not a target."
)


@dataclass(frozen=True)
class Multiples:
    ticker: str
    name: str
    price: float | None
    market_cap: float  # INR crore
    net_income: float
    ebitda: float
    enterprise_value: float
    pe: float | None
    ev_ebitda: float | None
    fiscal_year: str
    price_date: str | None
    fetched_at: str


def company_multiples(snap: Snapshot) -> Multiples:
    """Multiples of one company from its snapshot."""
    mcap = snap["market"].get("market_cap_crore")
    if not mcap:
        price = snap["market"].get("price")
        shares, _ = diluted_shares(snap)
        if not price:
            raise DataUnavailableError(f"No market data for {snap['ticker']}.")
        mcap = price * shares / CRORE
    ni = latest_value(snap, "income", "net_income")
    ebitda = latest_value(snap, "income", "ebitda")
    if ni is None or ebitda is None:
        raise DataUnavailableError(f"Net income or EBITDA missing for {snap['ticker']}.")
    debt = latest_value(snap, "balance", "total_debt") or 0.0
    cash = latest_value(snap, "balance", "cash_and_investments") or 0.0
    mi = latest_value(snap, "balance", "minority_interest") or 0.0
    ev = mcap + debt - cash + mi
    return Multiples(
        ticker=snap["ticker"],
        name=str(snap.get("name") or snap["ticker"]),
        price=snap["market"].get("price"),
        market_cap=mcap,
        net_income=ni,
        ebitda=ebitda,
        enterprise_value=ev,
        pe=mcap / ni if ni > 0 else None,
        ev_ebitda=ev / ebitda if ebitda > 0 else None,
        fiscal_year=snap["fiscal_years"][-1],
        price_date=snap["market"].get("price_date"),
        fetched_at=snap["fetched_at"],
    )


def _median(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def load_peer_snapshots(directory: str | Path, tickers: list[str]) -> list[Snapshot]:
    out: list[Snapshot] = []
    for t in tickers:
        try:
            out.append(load_snapshot(t, directory))
        except DataUnavailableError:
            continue  # a missing peer must not break the page; the table just omits it
    return out


def peer_cross_check(
    subject: Snapshot, peers: list[Snapshot], dcf_fair_value: float | None = None
) -> dict[str, Any]:
    """Peer table, median multiples and the value per share the subject would have at them."""
    peer_rows = [company_multiples(p) for p in peers if p["ticker"] != subject["ticker"]]
    if not peer_rows:
        raise DataUnavailableError("No peer snapshots available for the cross-check.")
    me = company_multiples(subject)
    med_pe = _median([m.pe for m in peer_rows])
    med_ev = _median([m.ev_ebitda for m in peer_rows])

    shares, _ = diluted_shares(subject)
    shares_cr = shares / CRORE
    debt = latest_value(subject, "balance", "total_debt") or 0.0
    cash = latest_value(subject, "balance", "cash_and_investments") or 0.0
    mi = latest_value(subject, "balance", "minority_interest") or 0.0

    value_pe = med_pe * me.net_income / shares_cr if med_pe is not None else None
    value_ev: float | None = None
    if med_ev is not None:
        value_ev = (med_ev * me.ebitda - debt + cash - mi) / shares_cr
    return {
        "subject": asdict(me),
        "peers": [asdict(m) for m in peer_rows],
        "median_pe": med_pe,
        "median_ev_ebitda": med_ev,
        "value_per_share_at_median_pe": value_pe,
        "value_per_share_at_median_ev_ebitda": value_ev,
        "dcf_fair_value": dcf_fair_value,
        "note": NOTE,
    }


def median_ev_ebitda(subject: Snapshot, peers: list[Snapshot]) -> float | None:
    """Median peer EV/EBITDA, used as the default exit multiple."""
    rows = [company_multiples(p) for p in peers if p["ticker"] != subject["ticker"]]
    return _median([m.ev_ebitda for m in rows])
