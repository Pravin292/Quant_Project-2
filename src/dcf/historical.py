"""Historical analysis (F2): growth, margins, tax rate, CapEx %, working-capital %.

All ratios are computed per fiscal year from a loader snapshot (INR crore).
Each ratio is a small pure function with its formula in the docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dcf.loader import Snapshot

Series = list[float | None]


def _div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def revenue_growth(revenue: Series) -> Series:
    """growth_t = Revenue_t / Revenue_(t-1) - 1   (first year has no prior year -> None)."""
    out: Series = [None]
    for prev, cur in zip(revenue[:-1], revenue[1:], strict=True):
        ratio = _div(cur, prev)
        out.append(None if ratio is None else ratio - 1.0)
    return out


def margin(numerator: Series, revenue: Series) -> Series:
    """margin_t = numerator_t / Revenue_t   (EBIT margin, EBITDA margin, D&A %, CapEx %)."""
    return [_div(n, r) for n, r in zip(numerator, revenue, strict=True)]


def effective_tax_rate(tax: Series, pretax: Series) -> Series:
    """tax rate_t = Tax expense_t / Pre-tax profit_t   (None when pre-tax profit <= 0)."""
    return [
        _div(t, p) if p is not None and p > 0 else None for t, p in zip(tax, pretax, strict=True)
    ]


def net_working_capital(receivables: Series, inventory: Series, payables: Series) -> Series:
    """NWC_t = Receivables_t + Inventory_t - Payables_t   (operating items only, no cash).

    Inventory missing is treated as 0 (services companies often report none); receivables
    and payables must be present, otherwise the year is None.
    """
    out: Series = []
    for r, i, p in zip(receivables, inventory, payables, strict=True):
        out.append(None if r is None or p is None else r + (i or 0.0) - p)
    return out


def summarize(values: Series) -> dict[str, float | None]:
    """mean / min / max / latest over the non-null values."""
    vals = [v for v in values if v is not None]
    if not vals:
        return {"mean": None, "min": None, "max": None, "latest": None, "n": 0}
    return {
        "mean": sum(vals) / len(vals),
        "min": min(vals),
        "max": max(vals),
        "latest": vals[-1],
        "n": float(len(vals)),
    }


@dataclass(frozen=True)
class Historical:
    """Per-year ratios aligned with ``fiscal_years`` plus a summary of each ratio."""

    fiscal_years: list[str]
    revenue: Series
    revenue_growth: Series
    ebit: Series
    ebit_margin: Series
    ebitda_margin: Series
    tax_rate: Series
    da_pct: Series
    capex_pct: Series
    nwc: Series
    nwc_pct: Series
    cash_conversion: Series  # operating cash flow / net income: is profit real cash?
    fcf_proxy: Series  # operating cash flow - capex (a rough cross-check on FCFF)
    summary: dict[str, dict[str, float | None]] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)

    def table(self) -> list[dict[str, Any]]:
        """One row per fiscal year, for display and the API."""
        keys = [
            "revenue", "revenue_growth", "ebit", "ebit_margin", "ebitda_margin", "tax_rate",
            "da_pct", "capex_pct", "nwc", "nwc_pct", "cash_conversion", "fcf_proxy",
        ]  # fmt: skip
        return [
            {"fiscal_year": fy, **{k: getattr(self, k)[i] for k in keys}}
            for i, fy in enumerate(self.fiscal_years)
        ]


def compute_historical(snap: Snapshot) -> Historical:
    """Compute every historical ratio from a snapshot."""
    years: list[str] = snap["fiscal_years"]

    def s(section: str, item: str) -> Series:
        return [snap[section][item].get(fy) for fy in years]

    revenue = s("income", "revenue")
    ebit = s("income", "operating_income")
    ebitda = s("income", "ebitda")
    nwc = net_working_capital(
        s("balance", "receivables"), s("balance", "inventory"), s("balance", "payables")
    )
    capex = s("cashflow", "capex")
    h = Historical(
        fiscal_years=years,
        revenue=revenue,
        revenue_growth=revenue_growth(revenue),
        ebit=ebit,
        ebit_margin=margin(ebit, revenue),
        ebitda_margin=margin(ebitda, revenue),
        tax_rate=effective_tax_rate(s("income", "tax_provision"), s("income", "pretax_income")),
        da_pct=margin(s("income", "depreciation"), revenue),
        capex_pct=margin(capex, revenue),
        nwc=nwc,
        nwc_pct=margin(nwc, revenue),
        cash_conversion=[
            _div(c, n)
            for c, n in zip(
                s("cashflow", "operating_cash_flow"), s("income", "net_income"), strict=True
            )
        ],
        fcf_proxy=[
            None if c is None or x is None else c - x
            for c, x in zip(s("cashflow", "operating_cash_flow"), capex, strict=True)
        ],
        sources={
            k: v
            for k, v in snap.get("provenance", {}).items()
            if k.startswith(("income", "balance", "cashflow"))
        },
    )
    summary = {
        name: summarize(getattr(h, name))
        for name in (
            "revenue_growth", "ebit_margin", "ebitda_margin", "tax_rate", "da_pct",
            "capex_pct", "nwc_pct", "cash_conversion",
        )
    }  # fmt: skip
    object.__setattr__(h, "summary", summary)
    return h


def format_history(h: Historical) -> str:
    """Plain-text table of the ratios (milestone M3 check: recompute two by hand)."""
    rows = [
        ("Revenue (INR cr)", h.revenue, "{:,.0f}"),
        ("Revenue growth", h.revenue_growth, "{:.2%}"),
        ("EBIT (INR cr)", h.ebit, "{:,.0f}"),
        ("EBIT margin", h.ebit_margin, "{:.2%}"),
        ("EBITDA margin", h.ebitda_margin, "{:.2%}"),
        ("Effective tax rate", h.tax_rate, "{:.2%}"),
        ("D&A % revenue", h.da_pct, "{:.2%}"),
        ("CapEx % revenue", h.capex_pct, "{:.2%}"),
        ("NWC (INR cr)", h.nwc, "{:,.0f}"),
        ("NWC % revenue", h.nwc_pct, "{:.2%}"),
        ("Op. cash flow / net income", h.cash_conversion, "{:.2f}x"),
        ("Op. cash flow - CapEx (INR cr)", h.fcf_proxy, "{:,.0f}"),
    ]
    lines = [f"{'':32}" + "".join(f"{fy:>12}" for fy in h.fiscal_years)]
    for label, vals, fmt in rows:
        cells = "".join(f"{'n/a':>12}" if v is None else f"{fmt.format(v):>12}" for v in vals)
        lines.append(f"{label:32}{cells}")
    return "\n".join(lines)
