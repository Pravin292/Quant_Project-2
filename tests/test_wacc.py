"""WACC, CAPM and beta regression tests (F4, F19)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from dcf import loader, wacc
from dcf.exceptions import DataUnavailableError, InvalidAssumptionError
from helpers import fake_raw

ROOT = Path(__file__).resolve().parent.parent


def inputs(**kw: float) -> wacc.WaccInputs:
    base = dict(
        risk_free=0.07,
        beta=0.8,
        equity_risk_premium=0.07,
        cost_of_debt=0.09,
        debt_weight=0.0,
        tax_rate=0.25,
    )
    base.update(kw)
    return wacc.WaccInputs(**base)


def test_cost_of_equity_by_hand() -> None:
    assert wacc.cost_of_equity(0.07, 0.8, 0.07) == pytest.approx(0.07 + 0.8 * 0.07)


def test_zero_debt_wacc_equals_cost_of_equity() -> None:
    r = wacc.compute_wacc(inputs(debt_weight=0.0))
    assert r.wacc == pytest.approx(r.cost_of_equity)
    assert r.equity_weight == 1.0


def test_wacc_blend_by_hand() -> None:
    r = wacc.compute_wacc(inputs(debt_weight=0.2))
    ke = 0.07 + 0.8 * 0.07
    assert r.wacc == pytest.approx(0.8 * ke + 0.2 * 0.09 * 0.75)
    assert [row["name"] for row in r.inputs_log][:3] == ["risk_free", "beta", "equity_risk_premium"]


def test_invalid_wacc_inputs() -> None:
    with pytest.raises(InvalidAssumptionError):
        wacc.compute_wacc(inputs(debt_weight=1.5))
    with pytest.raises(InvalidAssumptionError):
        wacc.compute_wacc(inputs(risk_free=0.0, beta=0.0, equity_risk_premium=0.0))


def test_regression_recovers_known_beta() -> None:
    rng = np.random.default_rng(7)
    mkt_ret = rng.normal(0.002, 0.02, 260)
    stk_ret = 0.001 + 0.85 * mkt_ret + rng.normal(0, 0.005, 260)
    mkt = 100 * np.cumprod(1 + np.r_[0, mkt_ret])
    stk = 100 * np.cumprod(1 + np.r_[0, stk_ret])
    b = wacc.regression_beta(list(stk), list(mkt))
    assert b.raw == pytest.approx(0.85, abs=0.05)
    assert b.ci95_low < 0.85 < b.ci95_high
    assert b.adjusted == pytest.approx(2 / 3 * b.raw + 1 / 3)
    assert b.observations == 260 and 0.5 < b.r_squared <= 1.0


def test_regression_exact_hand_case() -> None:
    # stock returns are exactly 2x market returns -> beta 2, zero residual
    mkt_ret = np.array([0.01, -0.02, 0.03, 0.005, -0.01] * 8)
    mkt = 100 * np.cumprod(1 + np.r_[0, mkt_ret])
    stk = 100 * np.cumprod(1 + np.r_[0, 2 * mkt_ret])
    b = wacc.regression_beta(list(stk), list(mkt))
    assert b.raw == pytest.approx(2.0)
    assert b.std_error == pytest.approx(0.0, abs=1e-9)


def test_regression_rejects_bad_series() -> None:
    with pytest.raises(DataUnavailableError):
        wacc.regression_beta([1.0] * 10, [1.0] * 10)
    with pytest.raises(DataUnavailableError):
        wacc.regression_beta([1.0] * 40, [1.0] * 41)
    with pytest.raises(DataUnavailableError, match="did not move"):
        wacc.regression_beta(list(range(1, 41)), [5.0] * 40)


def test_default_inputs_need_macro() -> None:
    snap = loader.build_snapshot("T.NS", fake_raw(), now=datetime(2026, 11, 26, tzinfo=UTC))
    with pytest.raises(DataUnavailableError, match="Risk-free"):
        wacc.default_wacc_inputs(snap)


def test_default_inputs_from_committed_tcs_snapshot() -> None:
    snap = loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots")
    inp, beta = wacc.default_wacc_inputs(snap)
    assert inp.risk_free == snap["macro"]["risk_free"]["value"]
    assert inp.beta == pytest.approx(beta.adjusted)
    assert 0 <= inp.debt_weight < 0.1  # TCS carries almost no borrowings
    assert "FRED" in inp.sources["risk_free"]
    r = wacc.compute_wacc(inp)
    assert inp.risk_free < r.wacc < 0.25
