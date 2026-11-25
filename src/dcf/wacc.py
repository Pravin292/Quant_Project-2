"""Discount rate (F4, F19): CAPM cost of equity, WACC, and beta by regression.

Spec section 7, steps 5-6:

    k_e  = r_f + beta x ERP
    WACC = E/(D+E) x k_e + D/(D+E) x k_d x (1 - tax rate)

Every input records its source in ``sources`` so the app can show it on hover.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from dcf.exceptions import DataUnavailableError, InvalidAssumptionError
from dcf.loader import Snapshot, latest_value

Z_95 = 1.96  # normal approximation of the 95% t-value (about 260 weekly observations)
BLUME_WEIGHT = 2.0 / 3.0  # adjusted beta = 2/3 x raw + 1/3 x 1


@dataclass(frozen=True)
class WaccInputs:
    risk_free: float
    beta: float
    equity_risk_premium: float
    cost_of_debt: float  # pre-tax
    debt_weight: float  # D / (D + E), between 0 and 1
    tax_rate: float
    sources: dict[str, str] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class WaccResult:
    cost_of_equity: float
    after_tax_cost_of_debt: float
    equity_weight: float
    debt_weight: float
    wacc: float
    inputs_log: list[dict[str, Any]]


@dataclass(frozen=True)
class BetaResult:
    raw: float
    adjusted: float
    std_error: float
    ci95_low: float
    ci95_high: float
    r_squared: float
    observations: int
    start_date: str | None
    end_date: str | None
    frequency: str = "weekly"


def cost_of_equity(risk_free: float, beta: float, equity_risk_premium: float) -> float:
    """Step 5 (CAPM): k_e = r_f + beta x ERP."""
    return risk_free + beta * equity_risk_premium


def compute_wacc(i: WaccInputs) -> WaccResult:
    """Step 6: blended cost of capital. With zero debt, WACC equals the cost of equity."""
    if not 0.0 <= i.debt_weight <= 1.0:
        raise InvalidAssumptionError("Debt weight must be between 0 and 1.")
    ke = cost_of_equity(i.risk_free, i.beta, i.equity_risk_premium)
    kd_after = i.cost_of_debt * (1.0 - i.tax_rate)
    w_e = 1.0 - i.debt_weight
    wacc = w_e * ke + i.debt_weight * kd_after
    if wacc <= 0:
        raise InvalidAssumptionError(
            "WACC must be positive; check the risk-free rate, beta and ERP."
        )
    log = [
        {"name": n, "value": v, "source": i.sources.get(n, "user input")}
        for n, v in (
            ("risk_free", i.risk_free),
            ("beta", i.beta),
            ("equity_risk_premium", i.equity_risk_premium),
            ("cost_of_debt", i.cost_of_debt),
            ("debt_weight", i.debt_weight),
            ("tax_rate", i.tax_rate),
        )
    ]
    return WaccResult(ke, kd_after, w_e, i.debt_weight, wacc, log)


def weekly_returns(prices: list[float] | np.ndarray) -> np.ndarray:
    """Simple returns r_t = P_t / P_(t-1) - 1."""
    p = np.asarray(prices, dtype=float)
    out: np.ndarray = p[1:] / p[:-1] - 1.0
    return out


def blume_adjust(raw_beta: float) -> float:
    """Standard adjustment toward 1: adjusted = 2/3 x raw + 1/3."""
    return BLUME_WEIGHT * raw_beta + (1.0 - BLUME_WEIGHT)


def regression_beta(
    stock_prices: list[float], index_prices: list[float], dates: list[str] | None = None
) -> BetaResult:
    """Beta by ordinary least squares of stock returns on market returns.

    slope = Cov(r_stock, r_mkt) / Var(r_mkt);  standard error from the residual variance;
    95% range = slope +/- 1.96 x SE.
    """
    if len(stock_prices) != len(index_prices):
        raise DataUnavailableError("Stock and index price series must have equal length.")
    if len(stock_prices) < 30:
        raise DataUnavailableError("At least 30 weekly prices are needed to estimate beta.")
    y = weekly_returns(stock_prices)
    x = weekly_returns(index_prices)
    n = len(x)
    x_mean, y_mean = x.mean(), y.mean()
    sxx = float(((x - x_mean) ** 2).sum())
    if sxx == 0:
        raise DataUnavailableError("The market index did not move; beta is undefined.")
    slope = float(((x - x_mean) * (y - y_mean)).sum() / sxx)
    intercept = float(y_mean - slope * x_mean)
    resid = y - (intercept + slope * x)
    sse = float((resid**2).sum())
    se = math.sqrt(sse / (n - 2) / sxx)
    sst = float(((y - y_mean) ** 2).sum())
    r2 = 1.0 - sse / sst if sst > 0 else 0.0
    return BetaResult(
        raw=slope,
        adjusted=blume_adjust(slope),
        std_error=se,
        ci95_low=slope - Z_95 * se,
        ci95_high=slope + Z_95 * se,
        r_squared=r2,
        observations=n,
        start_date=dates[0] if dates else None,
        end_date=dates[-1] if dates else None,
    )


def beta_from_snapshot(snap: Snapshot) -> BetaResult:
    w = snap["prices_weekly"]
    if not w["dates"]:
        raise DataUnavailableError("No weekly price history in the snapshot; cannot compute beta.")
    return regression_beta(w["stock"], w["index"], w["dates"])


def default_wacc_inputs(snap: Snapshot) -> tuple[WaccInputs, BetaResult]:
    """Build WACC inputs from a snapshot: macro rates, regression beta, derived debt terms."""
    macro = snap.get("macro", {})
    if "risk_free" not in macro or "equity_risk_premium" not in macro:
        raise DataUnavailableError(
            "Risk-free rate or equity risk premium missing from the snapshot; refresh the snapshot."
        )
    rf, erp = macro["risk_free"], macro["equity_risk_premium"]
    beta = beta_from_snapshot(snap)

    debt = latest_value(snap, "balance", "total_debt") or 0.0  # includes leases (see config)
    mcap = snap["market"].get("market_cap_crore")
    if not mcap:
        raise DataUnavailableError("Market capitalisation missing; cannot weight debt and equity.")
    debt_weight = debt / (debt + mcap)

    years = snap["fiscal_years"]
    interest = latest_value(snap, "income", "interest_expense")
    debts = [snap["balance"]["total_debt"].get(fy) for fy in years[-2:]]
    avg_debt = sum(d for d in debts if d is not None) / max(
        1, len([d for d in debts if d is not None])
    )
    if interest and avg_debt > 0:
        kd = min(max(interest / avg_debt, 0.0), 0.20)
        kd_src = "derived: latest interest expense / average total debt (capped at 20%)"
    else:
        kd = rf["value"]
        kd_src = "no debt or interest reported; set to the risk-free rate (weight is ~0)"

    pbt = latest_value(snap, "income", "pretax_income")
    tax = latest_value(snap, "income", "tax_provision")
    tax_rate = tax / pbt if pbt and tax is not None and pbt > 0 else 0.25
    snap_date = snap["fetched_at"][:10]
    sources = {
        "risk_free": f"{rf['source']}; {rf['as_of']}",
        "equity_risk_premium": f"{erp['source']}; {erp['as_of']}",
        "beta": (
            f"regression of {beta.observations} weekly returns vs {snap['prices_weekly']['index_ticker']} "
            f"({beta.start_date} to {beta.end_date}), raw {beta.raw:.3f}, Blume-adjusted; fetched {snap_date}"
        ),
        "cost_of_debt": kd_src,
        "debt_weight": f"total debt (incl. leases) / (debt + market cap); fetched {snap_date}",
        "tax_rate": "latest effective tax rate (tax provision / pre-tax income)",
    }
    inputs = WaccInputs(
        risk_free=rf["value"],
        beta=beta.adjusted,
        equity_risk_premium=erp["value"],
        cost_of_debt=kd,
        debt_weight=debt_weight,
        tax_rate=tax_rate,
        sources=sources,
    )
    return inputs, beta
