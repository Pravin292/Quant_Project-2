"""Monte Carlo simulation (F14): the model run thousands of times with random assumptions.

Random inputs (each centred on the base case):
  * revenue growth shift (all years)  triangular(-d, 0, +d), d = half the historical spread
  * EBIT margin shift (all years)     triangular(-m, 0, +m), m = half the historical spread
  * WACC                              normal(base, sd); sd from the beta standard error
  * terminal growth                   triangular(g - 1pt, g, g + 1pt)

Draws where terminal growth >= WACC (or year-5 FCFF <= 0) are discarded and redrawn.
The seed is fixed so results are reproducible. Fully vectorised with numpy.

The output is only as good as the input ranges; the UI says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from dcf.exceptions import InvalidAssumptionError
from dcf.valuation import ValuationInputs, run_valuation

CAVEAT = (
    "This range is only as good as the input ranges: it shows how the answer moves when the "
    "assumptions move, not the probability of any real-world outcome."
)
PERCENTILES = (5, 25, 50, 75, 95)


@dataclass(frozen=True)
class McSettings:
    runs: int = 10_000
    seed: int = 42
    growth_swing: float = 0.015  # half-range of the revenue-growth shift
    margin_swing: float = 0.015
    wacc_sd: float = 0.01
    terminal_growth_swing: float = 0.01
    bins: int = 40


def _triangular(
    rng: np.random.Generator, low: float, mode: float, high: float, size: int
) -> np.ndarray:
    """Triangular draws; a zero-width range collapses to the mode (numpy needs low < high)."""
    if high <= low:
        return np.full(size, mode)
    out: np.ndarray = rng.triangular(low, mode, high, size)
    return out


def vector_fair_values(
    inputs: ValuationInputs,
    growth_shift: np.ndarray,
    margin_shift: np.ndarray,
    wacc: np.ndarray,
    terminal_growth: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Fair value per share for many draws at once, plus a validity mask.

    Mirrors the scalar engine step by step (SPEC section 7); tests compare the two.
    """
    op, br = inputs.operating, inputs.bridge
    n_years = op.years
    g = np.asarray(op.revenue_growth)[None, :] + growth_shift[:, None]
    m = np.asarray(op.ebit_margin)[None, :] + margin_shift[:, None]
    revenue = op.base_revenue * np.cumprod(1.0 + g, axis=1)
    prior = np.concatenate([np.full((len(wacc), 1), op.base_revenue), revenue[:, :-1]], axis=1)
    nopat = revenue * m * (1.0 - op.tax_rate)
    fcff = nopat + revenue * op.da_pct - revenue * op.capex_pct - op.nwc_pct * (revenue - prior)

    t = np.arange(1, n_years + 1)[None, :] - (0.5 if inputs.mid_year else 0.0)
    disc = (1.0 + wacc[:, None]) ** (-t)
    sum_pv = (fcff * disc).sum(axis=1)
    valid = (terminal_growth < wacc) & (fcff[:, -1] > 0) & (wacc > 0)
    safe_denominator = np.where(valid, wacc - terminal_growth, 1.0)
    tv = fcff[:, -1] * (1.0 + terminal_growth) / safe_denominator
    ev = sum_pv + tv * disc[:, -1]
    equity = ev - br.debt - br.leases + br.cash_and_investments - br.minority_interest
    fair = equity / br.diluted_shares
    return np.where(valid, fair, np.nan), valid


def run_monte_carlo(inputs: ValuationInputs, settings: McSettings | None = None) -> dict[str, Any]:
    """Simulate ``settings.runs`` valid draws and summarise the fair-value distribution."""
    s = settings or McSettings()
    if s.runs < 100 or s.runs > 100_000:
        raise InvalidAssumptionError("Monte Carlo runs must be between 100 and 100,000.")
    base = run_valuation(inputs)
    rng = np.random.default_rng(s.seed)
    g0 = inputs.terminal.growth

    kept: list[np.ndarray] = []
    total_drawn = 0
    needed = s.runs
    for _ in range(20):  # resample until enough valid draws
        batch = int(needed * 1.3) + 100
        dg = _triangular(rng, -s.growth_swing, 0.0, s.growth_swing, batch)
        dm = _triangular(rng, -s.margin_swing, 0.0, s.margin_swing, batch)
        w = rng.normal(base.wacc_used, s.wacc_sd, batch)
        tg = np.maximum(
            _triangular(rng, g0 - s.terminal_growth_swing, g0, g0 + s.terminal_growth_swing, batch),
            0.0,
        )
        fv, valid = vector_fair_values(inputs, dg, dm, w, tg)
        total_drawn += batch
        kept.append(fv[valid])
        needed -= int(valid.sum())
        if needed <= 0:
            break
    values = np.concatenate(kept)[: s.runs]
    if len(values) < s.runs:
        raise InvalidAssumptionError(
            "Too many random draws were invalid (terminal growth too close to WACC)."
        )
    pct = {f"p{p}": float(np.percentile(values, p)) for p in PERCENTILES}
    counts, edges = np.histogram(values, bins=s.bins)
    price = inputs.bridge.price
    return {
        "runs": s.runs,
        "seed": s.seed,
        "discarded_draws": total_drawn - s.runs,
        "base_fair_value": base.fair_value_per_share,
        "mean": float(values.mean()),
        "std": float(values.std()),
        "percentiles": pct,
        "probability_above_price": float((values > price).mean()) if price else None,
        "price": price,
        "histogram": {"counts": counts.tolist(), "edges": edges.tolist()},
        "ranges": {
            "growth_swing": s.growth_swing,
            "margin_swing": s.margin_swing,
            "wacc_sd": s.wacc_sd,
            "terminal_growth_swing": s.terminal_growth_swing,
        },
        "caveat": CAVEAT,
    }


def settings_from_context(
    growth_swing: float, margin_swing: float, beta_std_error: float | None, erp: float, **kw: Any
) -> McSettings:
    """Ranges tied to history: swings come from the scenario spread, WACC sd from beta's SE."""
    wacc_sd = max(0.0025, (beta_std_error or 0.0) * erp) if beta_std_error else 0.01
    return McSettings(growth_swing=growth_swing, margin_swing=margin_swing, wacc_sd=wacc_sd, **kw)
