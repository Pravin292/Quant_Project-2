"""Shared fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dcf.forecast import OperatingAssumptions
from dcf.valuation import BridgeInputs, TerminalInputs, ValuationInputs
from dcf.wacc import WaccInputs

ROOT = Path(__file__).resolve().parent.parent


def chai_dict() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / "data/samples/chai_corner.json").read_text())
    return data


def inputs_from_dict(d: dict[str, Any]) -> ValuationInputs:
    o = d["operating"]
    return ValuationInputs(
        operating=OperatingAssumptions(
            base_revenue=o["base_revenue"],
            revenue_growth=tuple(o["revenue_growth"]),
            ebit_margin=tuple(o["ebit_margin"]),
            tax_rate=o["tax_rate"],
            da_pct=o["da_pct"],
            capex_pct=o["capex_pct"],
            nwc_pct=o["nwc_pct"],
        ),
        wacc=WaccInputs(
            risk_free=d["wacc"]["risk_free"],
            beta=d["wacc"]["beta"],
            equity_risk_premium=d["wacc"]["equity_risk_premium"],
            cost_of_debt=d["wacc"]["cost_of_debt"],
            debt_weight=d["wacc"]["debt_weight"],
            tax_rate=d["wacc"]["tax_rate"],
        ),
        terminal=TerminalInputs(**d["terminal"]),
        bridge=BridgeInputs(**d["bridge"]),
        mid_year=d.get("mid_year", False),
    )


@pytest.fixture
def chai() -> ValuationInputs:
    return inputs_from_dict(chai_dict())
