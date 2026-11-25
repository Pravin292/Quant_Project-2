"""Forecast tests (F3), including the Chai Corner example from SPEC section 7."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dcf import forecast
from dcf.exceptions import InvalidAssumptionError
from dcf.forecast import OperatingAssumptions

ROOT = Path(__file__).resolve().parent.parent


def chai() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((ROOT / "data/samples/chai_corner.json").read_text())
    return data


def chai_operating() -> OperatingAssumptions:
    o = chai()["operating"]
    return OperatingAssumptions(
        base_revenue=o["base_revenue"],
        revenue_growth=tuple(o["revenue_growth"]),
        ebit_margin=tuple(o["ebit_margin"]),
        tax_rate=o["tax_rate"],
        da_pct=o["da_pct"],
        capex_pct=o["capex_pct"],
        nwc_pct=o["nwc_pct"],
    )


def test_chai_corner_fcff_reproduces_spec_values() -> None:
    """Spec shows 157.5, 173.3, 190.6, 209.7, 230.6 (rounded spreadsheet figures)."""
    result = forecast.run_forecast(chai_operating())
    expected = chai()["expected"]["fcff"]
    # Year 1 is exact; later years grow exactly 10% a year and match to the spec's rounding
    assert result.fcff[0] == pytest.approx(157.5, abs=1e-9)
    for got, want in zip(result.fcff, expected, strict=True):
        assert got == pytest.approx(want, abs=0.1)
    for prev, cur in zip(result.fcff[:-1], result.fcff[1:], strict=True):
        assert cur / prev == pytest.approx(1.10)


def test_each_step_by_hand() -> None:
    r = forecast.run_forecast(chai_operating())
    assert r.revenue[0] == pytest.approx(1100.0)
    assert r.ebit[0] == pytest.approx(220.0)
    assert r.nopat[0] == pytest.approx(165.0)
    assert r.da[0] == pytest.approx(55.0)
    assert r.capex[0] == pytest.approx(55.0)
    assert r.delta_nwc[0] == pytest.approx(7.5)  # 0.075 x (1100 - 1000)
    assert r.fcff[0] == pytest.approx(165 + 55 - 55 - 7.5)


def test_forecast_length_follows_inputs() -> None:
    a = OperatingAssumptions(100.0, (0.1, 0.1, 0.1), (0.2, 0.2, 0.2), 0.25, 0.03, 0.04, 0.1)
    assert forecast.run_forecast(a).years == 3


def test_shifted_moves_every_year() -> None:
    a = chai_operating().shifted(growth=0.01, margin=-0.02)
    assert a.revenue_growth == pytest.approx((0.11,) * 5)
    assert a.ebit_margin == pytest.approx((0.18,) * 5)


def test_invalid_assumptions_rejected() -> None:
    with pytest.raises(InvalidAssumptionError):
        OperatingAssumptions(0.0, (0.1,), (0.2,), 0.25, 0.03, 0.04, 0.1)
    with pytest.raises(InvalidAssumptionError):
        OperatingAssumptions(100.0, (0.1, 0.1), (0.2,), 0.25, 0.03, 0.04, 0.1)
    with pytest.raises(InvalidAssumptionError):
        OperatingAssumptions(100.0, (), (), 0.25, 0.03, 0.04, 0.1)
