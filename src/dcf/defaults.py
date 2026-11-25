"""Assemble default valuation inputs from a snapshot (spec section 6, tables B-F).

Defaults are anchored on history and fetched market data; nothing is typed from memory.
The user can override every number in the app.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dcf import historical, peers
from dcf.config import bounds as config_bounds
from dcf.config import load_config
from dcf.exceptions import DataUnavailableError
from dcf.forecast import OperatingAssumptions
from dcf.loader import CRORE, Snapshot, diluted_shares, latest_value
from dcf.valuation import (
    BridgeInputs,
    TerminalInputs,
    ValuationContext,
    ValuationInputs,
)
from dcf.wacc import BetaResult, compute_wacc, default_wacc_inputs


@dataclass(frozen=True)
class DefaultBundle:
    inputs: ValuationInputs
    historical: historical.Historical
    beta: BetaResult
    sources: dict[str, str]


def _clamp(value: float, limits: list[float]) -> float:
    return min(max(value, limits[0]), limits[1])


def fade(start: float, end: float, years: int) -> tuple[float, ...]:
    """Linear path from ``start`` in year 1 to ``end`` in the last year."""
    if years == 1:
        return (start,)
    return tuple(start + (end - start) * t / (years - 1) for t in range(years))


def build_defaults(
    snap: Snapshot,
    peer_snaps: list[Snapshot] | None = None,
    peers_dir: str | Path | None = None,
    price: float | None = None,
) -> DefaultBundle:
    """Default inputs for ``snap``. ``price`` overrides the snapshot price (live quote)."""
    cfg = load_config()
    b = config_bounds()
    years = cfg["model"]["forecast_years"]
    h = historical.compute_historical(snap)
    s = h.summary

    for key in ("revenue_growth", "ebit_margin", "da_pct", "capex_pct", "nwc_pct"):
        if s[key]["mean"] is None:
            raise DataUnavailableError(
                f"Cannot derive a default for '{key}' from the data; upload more history."
            )

    wacc_in, beta = default_wacc_inputs(snap)
    wacc = compute_wacc(wacc_in).wacc

    g_term = min(
        cfg["model"]["default_terminal_growth"],
        wacc_in.risk_free,
        wacc - 0.02,
        b["terminal_growth"][1],
    )
    g1 = _clamp(float(s["revenue_growth"]["mean"] or 0.0), b["revenue_growth"])
    growth = tuple(_clamp(g, b["revenue_growth"]) for g in fade(g1, g_term, years))
    margin = _clamp(float(s["ebit_margin"]["mean"] or 0.0), b["ebit_margin"])
    tax = _clamp(float(s["tax_rate"]["latest"] or wacc_in.tax_rate), b["tax_rate"])

    base_revenue = latest_value(snap, "income", "revenue")
    if base_revenue is None:
        raise DataUnavailableError("Latest revenue is missing.")
    operating = OperatingAssumptions(
        base_revenue=base_revenue,
        revenue_growth=growth,
        ebit_margin=(margin,) * years,
        tax_rate=tax,
        da_pct=_clamp(float(s["da_pct"]["mean"] or 0.0), b["capex_pct"]),
        capex_pct=_clamp(float(s["capex_pct"]["mean"] or 0.0), b["capex_pct"]),
        nwc_pct=_clamp(float(s["nwc_pct"]["mean"] or 0.0), b["nwc_pct"]),
    )

    shares_count, shares_fy = diluted_shares(snap)
    market_price = price if price is not None else snap["market"].get("price")
    bridge = BridgeInputs(
        debt=latest_value(snap, "balance", "financial_debt") or 0.0,
        leases=latest_value(snap, "balance", "lease_liabilities") or 0.0,
        cash_and_investments=latest_value(snap, "balance", "cash_and_investments") or 0.0,
        minority_interest=latest_value(snap, "balance", "minority_interest") or 0.0,
        diluted_shares=shares_count / CRORE,
        price=market_price,
    )

    if peer_snaps is None and peers_dir is not None:
        peer_snaps = peers.load_peer_snapshots(peers_dir, cfg["peers"])
    exit_multiple: float | None = None
    exit_src = "none"
    if peer_snaps:
        exit_multiple = peers.median_ev_ebitda(snap, peer_snaps)
        exit_src = "median peer EV/EBITDA (latest snapshots)"
    if exit_multiple is None:
        try:
            exit_multiple = peers.company_multiples(snap).ev_ebitda
            exit_src = "the company's own current EV/EBITDA"
        except DataUnavailableError:
            exit_multiple = None
    if exit_multiple is not None:
        exit_multiple = min(exit_multiple, 100.0)

    roics = [r for r in h.roic if r is not None]
    ctx = ValuationContext(
        margin_min=s["ebit_margin"]["min"],
        margin_max=s["ebit_margin"]["max"],
        roic=roics[-1] if roics else None,
        fcf_proxy_latest=next((v for v in reversed(h.fcf_proxy) if v is not None), None),
    )
    inputs = ValuationInputs(
        operating=operating,
        wacc=wacc_in,
        terminal=TerminalInputs(growth=g_term, exit_multiple=exit_multiple),
        bridge=bridge,
        mid_year=cfg["model"]["discounting"] == "mid_year",
        context=ctx,
    )
    fetched = snap["fetched_at"][:10]
    sources = {
        "revenue_growth": f"historical mean growth ({s['revenue_growth']['n']:.0f} yrs) fading to terminal growth",
        "ebit_margin": "historical mean EBIT margin, held flat",
        "tax_rate": "latest effective tax rate",
        "da_pct": "historical mean D&A % revenue",
        "capex_pct": "historical mean CapEx % revenue",
        "nwc_pct": "historical mean NWC % revenue",
        "terminal_growth": "config default, capped at risk-free rate and below WACC",
        "exit_multiple": exit_src,
        "bridge": f"{snap['fiscal_years'][-1]} balance sheet ({snap['source']}, fetched {fetched})",
        "diluted_shares": f"{shares_fy} diluted shares ({snap['source']}, fetched {fetched})",
        "price": "live quote when available, else snapshot price dated "
        + str(snap["market"].get("price_date")),
        **{f"wacc.{k}": v for k, v in wacc_in.sources.items()},
    }
    return DefaultBundle(inputs, h, beta, sources)
