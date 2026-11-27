"""Pydantic request and response models (F9).

These mirror the engine dataclasses field for field, so ``dataclasses.asdict(inputs)``
is a valid ``Assumptions`` payload. Types and sizes are checked here; the financial
bounds live in ``config.yaml`` and are enforced by ``dcf.valuation.validate_inputs``.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from dcf.forecast import OperatingAssumptions
from dcf.valuation import BridgeInputs, TerminalInputs, ValuationContext, ValuationInputs
from dcf.wacc import WaccInputs

Number = Annotated[float, Field(allow_inf_nan=False, ge=-1e12, le=1e12)]
Series = Annotated[list[Number], Field(min_length=1, max_length=10)]
Text = Annotated[str, Field(max_length=300)]
Ticker = Annotated[str, Field(pattern=r"^[A-Za-z0-9._^&-]{1,20}$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Operating(Strict):
    base_revenue: Number
    revenue_growth: Series
    ebit_margin: Series
    tax_rate: Number
    da_pct: Number
    capex_pct: Number
    nwc_pct: Number


class Wacc(Strict):
    risk_free: Number
    beta: Number
    equity_risk_premium: Number
    cost_of_debt: Annotated[float, Field(allow_inf_nan=False, ge=0, le=0.5)]
    debt_weight: Annotated[float, Field(allow_inf_nan=False, ge=0, le=1)]
    tax_rate: Annotated[float, Field(allow_inf_nan=False, ge=0, le=0.5)]
    sources: Annotated[dict[str, Text], Field(max_length=20)] = Field(default_factory=dict)


class Terminal(Strict):
    growth: Number
    exit_multiple: Number | None = None


class Bridge(Strict):
    debt: Number
    leases: Number
    cash_and_investments: Number
    minority_interest: Number
    diluted_shares: Number
    price: Number | None = None


class Context(Strict):
    margin_min: Number | None = None
    margin_max: Number | None = None
    roic: Number | None = None
    fcf_proxy_latest: Number | None = None


class Assumptions(Strict):
    """Everything needed to value one company. Money in INR crore, rates as decimals."""

    operating: Operating
    wacc: Wacc
    terminal: Terminal
    bridge: Bridge
    mid_year: bool = False
    wacc_override: Annotated[float, Field(allow_inf_nan=False, gt=0, le=0.5)] | None = None
    context: Context | None = None
    ticker: Ticker | None = None  # lets scenario and Monte Carlo ranges use this company's history

    def to_inputs(self) -> ValuationInputs:
        o = self.operating
        return ValuationInputs(
            operating=OperatingAssumptions(
                base_revenue=o.base_revenue,
                revenue_growth=tuple(o.revenue_growth),
                ebit_margin=tuple(o.ebit_margin),
                tax_rate=o.tax_rate,
                da_pct=o.da_pct,
                capex_pct=o.capex_pct,
                nwc_pct=o.nwc_pct,
            ),
            wacc=WaccInputs(**self.wacc.model_dump()),
            terminal=TerminalInputs(**self.terminal.model_dump()),
            bridge=BridgeInputs(**self.bridge.model_dump()),
            mid_year=self.mid_year,
            wacc_override=self.wacc_override,
            context=ValuationContext(**self.context.model_dump()) if self.context else None,
        )


class ReverseDcfRequest(Strict):
    assumptions: Assumptions
    target_price: Annotated[float, Field(allow_inf_nan=False, gt=0, le=1e9)] | None = None


class TornadoRequest(Strict):
    assumptions: Assumptions
    delta: Annotated[float, Field(gt=0, le=0.05)] = 0.01


class ScenarioRequest(Strict):
    assumptions: Assumptions
    probabilities: Annotated[dict[str, Number], Field(max_length=3)] | None = None


class MonteCarloRequest(Strict):
    assumptions: Assumptions
    runs: Annotated[int, Field(ge=100, le=20_000)] | None = None
    seed: Annotated[int, Field(ge=0, le=2**31 - 1)] | None = None


class ExportRequest(Strict):
    assumptions: Assumptions


class ReportRequest(Strict):
    assumptions: Assumptions
    probabilities: Annotated[dict[str, Number], Field(max_length=3)] | None = None
