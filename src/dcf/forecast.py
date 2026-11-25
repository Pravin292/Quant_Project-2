"""Forecast engine (F3): five-year revenue, EBIT, NOPAT, reinvestment and FCFF.

Spec section 7, steps 1-4. All money is in one consistent unit (INR crore for real
companies); rates are decimals (0.10 = 10%).

    Revenue_t = Revenue_(t-1) x (1 + g_t)
    EBIT_t    = Revenue_t x EBIT margin_t
    NOPAT_t   = EBIT_t x (1 - tax rate)
    dNWC_t    = NWC% x (Revenue_t - Revenue_(t-1))
    FCFF_t    = NOPAT_t + D&A_t - CapEx_t - dNWC_t
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from dcf.exceptions import InvalidAssumptionError


@dataclass(frozen=True)
class OperatingAssumptions:
    """Editable forecast assumptions. ``revenue_growth`` and ``ebit_margin`` are per year."""

    base_revenue: float  # last actual revenue (year 0)
    revenue_growth: tuple[float, ...]
    ebit_margin: tuple[float, ...]
    tax_rate: float
    da_pct: float  # depreciation & amortisation as % of revenue
    capex_pct: float  # capital expenditure as % of revenue
    nwc_pct: float  # net working capital as % of revenue (moves with revenue change)

    def __post_init__(self) -> None:
        if self.base_revenue <= 0:
            raise InvalidAssumptionError("Base revenue must be positive.")
        if len(self.revenue_growth) == 0:
            raise InvalidAssumptionError("At least one forecast year is required.")
        if len(self.revenue_growth) != len(self.ebit_margin):
            raise InvalidAssumptionError(
                "Revenue growth and EBIT margin must have the same number of years."
            )

    @property
    def years(self) -> int:
        return len(self.revenue_growth)

    def shifted(self, growth: float = 0.0, margin: float = 0.0) -> OperatingAssumptions:
        """Copy with every year's growth and margin moved by an absolute amount (decimals)."""
        return replace(
            self,
            revenue_growth=tuple(g + growth for g in self.revenue_growth),
            ebit_margin=tuple(m + margin for m in self.ebit_margin),
        )


@dataclass(frozen=True)
class ForecastResult:
    """Year 1..N arrays. ``revenue[0]`` is year 1 (year 0 is ``base_revenue``)."""

    base_revenue: float
    revenue: tuple[float, ...]
    ebit: tuple[float, ...]
    nopat: tuple[float, ...]
    da: tuple[float, ...]
    capex: tuple[float, ...]
    delta_nwc: tuple[float, ...]
    fcff: tuple[float, ...]

    @property
    def years(self) -> int:
        return len(self.fcff)


def forecast_revenue(base_revenue: float, growth: tuple[float, ...]) -> tuple[float, ...]:
    """Step 1: Revenue_t = Revenue_(t-1) x (1 + g_t)."""
    out: list[float] = []
    prev = base_revenue
    for g in growth:
        prev = prev * (1.0 + g)
        out.append(prev)
    return tuple(out)


def forecast_ebit(revenue: tuple[float, ...], margin: tuple[float, ...]) -> tuple[float, ...]:
    """Step 2: EBIT_t = Revenue_t x EBIT margin_t."""
    return tuple(r * m for r, m in zip(revenue, margin, strict=True))


def nopat(ebit: tuple[float, ...], tax_rate: float) -> tuple[float, ...]:
    """Step 2: NOPAT_t = EBIT_t x (1 - tax rate)."""
    return tuple(e * (1.0 - tax_rate) for e in ebit)


def change_in_nwc(
    base_revenue: float, revenue: tuple[float, ...], nwc_pct: float
) -> tuple[float, ...]:
    """Step 3: dNWC_t = NWC% x (Revenue_t - Revenue_(t-1))."""
    prior = (base_revenue, *revenue[:-1])
    return tuple(nwc_pct * (cur - prev) for cur, prev in zip(revenue, prior, strict=True))


def fcff(
    nopat_: tuple[float, ...],
    da: tuple[float, ...],
    capex: tuple[float, ...],
    d_nwc: tuple[float, ...],
) -> tuple[float, ...]:
    """Step 4: FCFF_t = NOPAT_t + D&A_t - CapEx_t - dNWC_t."""
    return tuple(n + d - c - w for n, d, c, w in zip(nopat_, da, capex, d_nwc, strict=True))


def run_forecast(a: OperatingAssumptions) -> ForecastResult:
    """Steps 1-4 for every forecast year."""
    revenue = forecast_revenue(a.base_revenue, a.revenue_growth)
    ebit = forecast_ebit(revenue, a.ebit_margin)
    nop = nopat(ebit, a.tax_rate)
    da = tuple(r * a.da_pct for r in revenue)
    capex = tuple(r * a.capex_pct for r in revenue)
    dnwc = change_in_nwc(a.base_revenue, revenue, a.nwc_pct)
    return ForecastResult(
        base_revenue=a.base_revenue,
        revenue=revenue,
        ebit=ebit,
        nopat=nop,
        da=da,
        capex=capex,
        delta_nwc=dnwc,
        fcff=fcff(nop, da, capex, dnwc),
    )
