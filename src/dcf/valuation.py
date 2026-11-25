"""Valuation bridge (F6), sanity warnings and reverse DCF (F18).

Spec section 7, steps 7-11:

    PV_t   = FCFF_t / (1 + WACC)^t                       (mid-year toggle: t - 0.5)
    EV     = sum PV_t + PV(TV)
    Equity = EV - Debt - Leases + Cash & investments - Minority interest
    FV     = Equity / Diluted shares ;  Upside = FV / Price - 1

Lease treatment (documented choice): lease liabilities are treated as debt in the bridge,
so EBIT is before lease interest. Money is in one unit (INR crore); ``diluted_shares`` is in
the matching unit (crore of shares), so FV comes out in rupees per share.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from dcf import terminal as tv_mod
from dcf.config import bounds as config_bounds
from dcf.config import load_config
from dcf.exceptions import InvalidAssumptionError
from dcf.forecast import ForecastResult, OperatingAssumptions, run_forecast
from dcf.wacc import WaccInputs, WaccResult, compute_wacc


@dataclass(frozen=True)
class TerminalInputs:
    growth: float
    exit_multiple: float | None = None  # EV/EBITDA, used for the cross-check only


@dataclass(frozen=True)
class BridgeInputs:
    debt: float  # financial borrowings
    leases: float  # lease liabilities (treated as debt)
    cash_and_investments: float
    minority_interest: float
    diluted_shares: float  # same unit as money (crore of shares for INR crore)
    price: float | None = None  # market price per share, for upside and comparisons


@dataclass(frozen=True)
class ValuationContext:
    """Optional historical facts used only for warnings and the ROIC check."""

    margin_min: float | None = None
    margin_max: float | None = None
    roic: float | None = None
    fcf_proxy_latest: float | None = None  # operating cash flow - capex, latest year


@dataclass(frozen=True)
class ValuationInputs:
    operating: OperatingAssumptions
    wacc: WaccInputs
    terminal: TerminalInputs
    bridge: BridgeInputs
    mid_year: bool = False
    wacc_override: float | None = None  # used by sensitivity grids; replaces computed WACC
    context: ValuationContext | None = None


@dataclass(frozen=True)
class ModelWarning:
    code: str
    severity: str  # "warning" or "info"
    message: str


@dataclass(frozen=True)
class ValuationResult:
    forecast: ForecastResult
    wacc: WaccResult
    wacc_used: float
    discount_factors: tuple[float, ...]
    pv_fcff: tuple[float, ...]
    sum_pv_fcff: float
    terminal_value: float
    pv_terminal_value: float
    enterprise_value: float
    terminal_value_share: float
    bridge: dict[str, float]
    equity_value: float
    fair_value_per_share: float
    price: float | None
    upside: float | None
    exit_cross_check: dict[str, float | None] | None
    roic_check: tv_mod.RoicCheck | None
    value_driver_cross_check: dict[str, float] | None
    warnings: list[ModelWarning] = field(default_factory=list)


# --------------------------------------------------------------------------- discounting
def discount_factor(rate: float, t: float, mid_year: bool = False) -> float:
    """1 / (1 + rate)^t, or ^(t - 0.5) with the mid-year convention."""
    exponent = t - 0.5 if mid_year else t
    return float(1.0 / (1.0 + rate) ** exponent)


def present_values(
    cash_flows: tuple[float, ...], rate: float, mid_year: bool = False
) -> tuple[float, ...]:
    """Step 7: PV_t = FCFF_t x discount factor_t for t = 1..N."""
    return tuple(
        cf * discount_factor(rate, t, mid_year) for t, cf in enumerate(cash_flows, start=1)
    )


# --------------------------------------------------------------------------- validation
def _check(name: str, value: float, limits: list[float], pct: bool = True) -> None:
    low, high = limits
    if not low <= value <= high:
        lo, hi = (f"{low:.0%}", f"{high:.0%}") if pct else (f"{low:g}", f"{high:g}")
        raise InvalidAssumptionError(f"{name} must be between {lo} and {hi}.")


def validate_inputs(inputs: ValuationInputs, bounds: dict[str, list[float]] | None = None) -> None:
    """Enforce the hard bounds from config.yaml. Raises InvalidAssumptionError with a plain sentence."""
    b = bounds or config_bounds()
    o = inputs.operating
    for g in o.revenue_growth:
        _check("Revenue growth", g, b["revenue_growth"])
    for m in o.ebit_margin:
        _check("EBIT margin", m, b["ebit_margin"])
    _check("Tax rate", o.tax_rate, b["tax_rate"])
    _check("CapEx % of revenue", o.capex_pct, b["capex_pct"])
    _check("D&A % of revenue", o.da_pct, b["capex_pct"])
    _check("Working capital % of revenue", o.nwc_pct, b["nwc_pct"])
    w = inputs.wacc
    _check("Risk-free rate", w.risk_free, b["risk_free"])
    _check("Equity risk premium", w.equity_risk_premium, b["equity_risk_premium"])
    _check("Beta", w.beta, b["beta"], pct=False)
    _check("Terminal growth", inputs.terminal.growth, b["terminal_growth"])
    br = inputs.bridge
    if br.diluted_shares <= 0:
        raise InvalidAssumptionError("Diluted shares must be positive.")
    for label, v in (
        ("Debt", br.debt),
        ("Lease liabilities", br.leases),
        ("Cash and investments", br.cash_and_investments),
        ("Minority interest", br.minority_interest),
    ):
        if v < 0:
            raise InvalidAssumptionError(f"{label} cannot be negative.")
    if br.price is not None and br.price <= 0:
        raise InvalidAssumptionError("Share price must be positive.")
    em = inputs.terminal.exit_multiple
    if em is not None and not 0 < em <= 100:
        raise InvalidAssumptionError("Exit multiple must be between 0 and 100.")
    if inputs.wacc_override is not None and inputs.wacc_override <= 0:
        raise InvalidAssumptionError("WACC must be positive.")


# --------------------------------------------------------------------------- the valuation
def run_valuation(inputs: ValuationInputs, validate: bool = True) -> ValuationResult:
    """Steps 1-11 plus warnings. Raises InvalidAssumptionError for impossible inputs."""
    if validate:
        validate_inputs(inputs)
    fc = run_forecast(inputs.operating)
    wacc_res = compute_wacc(inputs.wacc)
    wacc = inputs.wacc_override if inputs.wacc_override is not None else wacc_res.wacc
    n = fc.years
    g = inputs.terminal.growth

    dfs = tuple(discount_factor(wacc, t, inputs.mid_year) for t in range(1, n + 1))
    pvs = present_values(fc.fcff, wacc, inputs.mid_year)
    if fc.fcff[-1] <= 0:
        raise InvalidAssumptionError(
            "Year-5 free cash flow is not positive, so a perpetuity value is meaningless. "
            "Raise the EBIT margin or lower CapEx and working-capital needs."
        )
    tv = tv_mod.gordon_terminal_value(fc.fcff[-1], wacc, g)
    tv_df = discount_factor(wacc, n, inputs.mid_year)  # Gordon follows the cash-flow timing
    pv_tv = tv * tv_df
    sum_pv = sum(pvs)
    ev = sum_pv + pv_tv

    br = inputs.bridge
    equity = ev - br.debt - br.leases + br.cash_and_investments - br.minority_interest
    fair = equity / br.diluted_shares
    price = br.price
    upside = fair / price - 1.0 if price else None

    ebitda_n = fc.ebit[-1] + fc.da[-1]
    exit_check = _exit_cross_check(inputs, fc, tv, wacc, ebitda_n)
    ctx = inputs.context
    rc = tv_mod.roic_check(fc.nopat[-1], fc.fcff[-1], wacc, g, ctx.roic if ctx else None)
    vd_check: dict[str, float] | None = None
    if rc.value_driver_terminal_value is not None:  # TV if growth must be paid for at the ROIC
        ev_vd = sum_pv + rc.value_driver_terminal_value * tv_df
        eq_vd = ev_vd - br.debt - br.leases + br.cash_and_investments - br.minority_interest
        vd_check = {
            "terminal_value": rc.value_driver_terminal_value,
            "enterprise_value": ev_vd,
            "fair_value_per_share": eq_vd / br.diluted_shares,
        }

    result = ValuationResult(
        forecast=fc,
        wacc=wacc_res,
        wacc_used=wacc,
        discount_factors=dfs,
        pv_fcff=pvs,
        sum_pv_fcff=sum_pv,
        terminal_value=tv,
        pv_terminal_value=pv_tv,
        enterprise_value=ev,
        terminal_value_share=pv_tv / ev if ev > 0 else float("nan"),
        bridge={
            "enterprise_value": ev,
            "less_debt": -br.debt,
            "less_leases": -br.leases,
            "plus_cash_and_investments": br.cash_and_investments,
            "less_minority_interest": -br.minority_interest,
            "equity_value": equity,
        },
        equity_value=equity,
        fair_value_per_share=fair,
        price=price,
        upside=upside,
        exit_cross_check=exit_check,
        roic_check=rc,
        value_driver_cross_check=vd_check,
    )
    result.warnings.extend(sanity_warnings(inputs, result))
    return result


def _exit_cross_check(
    inputs: ValuationInputs, fc: ForecastResult, tv: float, wacc: float, ebitda_n: float
) -> dict[str, float | None] | None:
    """Terminal value by exit multiple, next to the perpetuity-growth one."""
    br = inputs.bridge
    n = fc.years
    out: dict[str, float | None] = {
        "implied_exit_multiple": tv_mod.implied_exit_multiple(tv, ebitda_n),
        "ebitda_year_n": ebitda_n,
    }
    em = inputs.terminal.exit_multiple
    if em is None:
        return out
    tv_exit = tv_mod.exit_multiple_terminal_value(ebitda_n, em)
    pv_exit = tv_exit * discount_factor(wacc, n, mid_year=False)  # exit value sits at year-end
    ev_exit = sum(present_values(fc.fcff, wacc, inputs.mid_year)) + pv_exit
    equity_exit = ev_exit - br.debt - br.leases + br.cash_and_investments - br.minority_interest
    fair_exit = equity_exit / br.diluted_shares
    out.update(
        {
            "exit_multiple": em,
            "terminal_value": tv_exit,
            "pv_terminal_value": pv_exit,
            "enterprise_value": ev_exit,
            "equity_value": equity_exit,
            "fair_value_per_share": fair_exit,
            "implied_perpetual_growth": tv_mod.implied_perpetual_growth(tv_exit, fc.fcff[-1], wacc),
        }
    )
    return out


def sanity_warnings(inputs: ValuationInputs, r: ValuationResult) -> list[ModelWarning]:
    """Warnings shown on every valuation (SPEC section 9)."""
    w = load_config()["warnings"]
    out: list[ModelWarning] = []
    if r.terminal_value_share > w["terminal_value_share_max"]:
        out.append(
            ModelWarning(
                "TV_SHARE_HIGH",
                "warning",
                f"Terminal value is {r.terminal_value_share:.0%} of enterprise value "
                f"(above {w['terminal_value_share_max']:.0%}); the result leans heavily on the "
                "terminal assumptions.",
            )
        )
    g, rf = inputs.terminal.growth, inputs.wacc.risk_free
    if g > rf:
        out.append(
            ModelWarning(
                "TERMINAL_GROWTH_HIGH",
                "warning",
                f"Terminal growth ({g:.2%}) is above the risk-free rate ({rf:.2%}), a proxy for "
                "long-run nominal growth.",
            )
        )
    ctx = inputs.context
    if ctx and ctx.margin_min is not None and ctx.margin_max is not None:
        gap = w["margin_gap_vs_history"]
        lo, hi = ctx.margin_min - gap, ctx.margin_max + gap
        if any(m < lo or m > hi for m in inputs.operating.ebit_margin):
            out.append(
                ModelWarning(
                    "MARGIN_OUTSIDE_HISTORY",
                    "warning",
                    f"Forecast EBIT margin is far outside the historical range "
                    f"({ctx.margin_min:.1%} to {ctx.margin_max:.1%}).",
                )
            )
    lo_w, hi_w = w["wacc_band"]
    if not lo_w <= r.wacc_used <= hi_w:
        out.append(
            ModelWarning(
                "WACC_OUTSIDE_BAND",
                "warning",
                f"WACC ({r.wacc_used:.2%}) is outside the plausible band {lo_w:.0%} to {hi_w:.0%}.",
            )
        )
    if r.price:
        ratio = r.fair_value_per_share / r.price
        if ratio > w["fair_value_ratio_high"] or ratio < w["fair_value_ratio_low"]:
            out.append(
                ModelWarning(
                    "FAIR_VALUE_FAR_FROM_PRICE",
                    "warning",
                    f"Model value is {ratio:.1f}x the market price; check the assumptions "
                    "before trusting it.",
                )
            )
    if r.roic_check is not None and not r.roic_check.plausible:
        out.append(ModelWarning("ROIC_FREE_GROWTH", "warning", r.roic_check.message))
    if ctx and ctx.fcf_proxy_latest and ctx.fcf_proxy_latest > 0:
        ratio = r.forecast.fcff[0] / ctx.fcf_proxy_latest
        if not 0.5 <= ratio <= 1.5:
            out.append(
                ModelWarning(
                    "FCFF_VS_CASH_FLOW",
                    "warning",
                    f"Year-1 FCFF is {ratio:.1f}x the latest reported operating cash flow less CapEx; "
                    "check that profit is turning into cash.",
                )
            )
    return out


# --------------------------------------------------------------------------- reverse DCF
@dataclass(frozen=True)
class ReverseDcfResult:
    """The constant annual revenue growth (years 1-N) that makes fair value equal the price."""

    status: str  # "solved" or "no_solution_in_bounds"
    implied_growth: float | None
    target_price: float
    fair_value_at_solution: float | None
    iterations: int
    message: str


def reverse_dcf(
    inputs: ValuationInputs,
    target_price: float | None = None,
    low: float | None = None,
    high: float | None = None,
    tolerance: float = 1e-10,
    max_iterations: int = 200,
) -> ReverseDcfResult:
    """Solve for the constant revenue growth that equates fair value with the market price.

    Bisection: fair value rises with growth, so keep the half of [low, high] that brackets
    the target. Everything else (margins, WACC, terminal growth) stays as in ``inputs``.
    """
    price = target_price if target_price is not None else inputs.bridge.price
    if price is None or price <= 0:
        raise InvalidAssumptionError("A positive market price is needed for the reverse DCF.")
    b = config_bounds()["revenue_growth"]
    lo = b[0] if low is None else low
    hi = b[1] if high is None else high
    n = inputs.operating.years

    def fv(growth: float) -> float | None:
        op = replace(inputs.operating, revenue_growth=(growth,) * n)
        try:
            return run_valuation(replace(inputs, operating=op), validate=False).fair_value_per_share
        except InvalidAssumptionError:
            return None  # e.g. year-5 FCFF not positive at very low growth

    f_hi = fv(hi)
    # shrink the lower end until the model can run (very low growth may break the cash flow)
    f_lo = fv(lo)
    steps = 0
    while f_lo is None and steps < 200 and lo < hi:
        lo += (hi - lo) / 200
        f_lo = fv(lo)
        steps += 1
    if f_lo is None or f_hi is None or not f_lo <= price <= f_hi:
        return ReverseDcfResult(
            "no_solution_in_bounds",
            None,
            price,
            None,
            0,
            f"No revenue growth between {lo:.0%} and {hi:.0%} makes the model value equal "
            f"the price of {price:,.2f}.",
        )
    iterations = 0
    mid = (lo + hi) / 2
    f_mid = f_lo
    for step in range(1, max_iterations + 1):
        iterations = step
        mid = (lo + hi) / 2
        f_mid_ = fv(mid)
        if f_mid_ is None:
            lo = mid
            continue
        f_mid = f_mid_
        if abs(f_mid - price) < tolerance * max(1.0, price) or (hi - lo) < tolerance:
            break
        if f_mid < price:
            lo = mid
        else:
            hi = mid
    return ReverseDcfResult(
        "solved",
        mid,
        price,
        f_mid,
        iterations,
        f"The price of {price:,.2f} implies revenue growth of {mid:.2%} a year for "
        f"{n} years with the other assumptions unchanged.",
    )


def result_to_dict(r: ValuationResult | Any) -> dict[str, Any]:
    """Plain-JSON form of any result dataclass (used by the API and the exporter)."""
    from dataclasses import asdict

    return asdict(r)
