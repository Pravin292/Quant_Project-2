"""Monte Carlo tests (F14): reproducible, consistent with the scalar engine, respects constraints."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from dcf import defaults, loader, montecarlo, valuation
from dcf.exceptions import InvalidAssumptionError
from dcf.valuation import TerminalInputs, ValuationInputs

ROOT = Path(__file__).resolve().parent.parent


def test_vector_engine_matches_scalar_engine(chai: ValuationInputs) -> None:
    rng = np.random.default_rng(3)
    k = 25
    dg = rng.uniform(-0.03, 0.03, k)
    dm = rng.uniform(-0.03, 0.03, k)
    w = rng.uniform(0.09, 0.16, k)
    tg = rng.uniform(0.02, 0.06, k)
    fv, valid = montecarlo.vector_fair_values(chai, dg, dm, w, tg)
    assert valid.all()
    for i in range(k):
        scalar = valuation.run_valuation(
            replace(
                chai,
                operating=chai.operating.shifted(growth=dg[i], margin=dm[i]),
                wacc_override=float(w[i]),
                terminal=TerminalInputs(float(tg[i])),
            ),
            validate=False,
        ).fair_value_per_share
        assert fv[i] == pytest.approx(scalar, rel=1e-12)


def test_vector_engine_matches_scalar_midyear(chai: ValuationInputs) -> None:
    mid = replace(chai, mid_year=True)
    fv, _ = montecarlo.vector_fair_values(
        mid, np.zeros(1), np.zeros(1), np.array([0.12]), np.array([0.04])
    )
    assert fv[0] == pytest.approx(valuation.run_valuation(mid).fair_value_per_share)


def test_zero_ranges_collapse_to_base_case(chai: ValuationInputs) -> None:
    s = montecarlo.McSettings(
        runs=200, growth_swing=0.0, margin_swing=0.0, wacc_sd=0.0, terminal_growth_swing=0.0
    )
    out = montecarlo.run_monte_carlo(chai, s)
    base = valuation.run_valuation(chai).fair_value_per_share
    assert out["percentiles"]["p5"] == pytest.approx(base) and out["percentiles"][
        "p95"
    ] == pytest.approx(base)


def test_fixed_seed_is_reproducible_and_seed_matters(chai: ValuationInputs) -> None:
    a = montecarlo.run_monte_carlo(chai, montecarlo.McSettings(runs=1000, seed=7))
    b = montecarlo.run_monte_carlo(chai, montecarlo.McSettings(runs=1000, seed=7))
    c = montecarlo.run_monte_carlo(chai, montecarlo.McSettings(runs=1000, seed=8))
    assert a["percentiles"] == b["percentiles"]
    assert a["percentiles"] != c["percentiles"]


def test_distribution_properties(chai: ValuationInputs) -> None:
    out = montecarlo.run_monte_carlo(chai)
    p = out["percentiles"]
    assert out["runs"] == 10_000
    assert p["p5"] < p["p25"] < p["p50"] < p["p75"] < p["p95"]
    assert p["p50"] == pytest.approx(out["base_fair_value"], rel=0.08)  # median close to base
    assert 0.0 <= out["probability_above_price"] <= 1.0
    assert sum(out["histogram"]["counts"]) == 10_000
    assert len(out["histogram"]["edges"]) == len(out["histogram"]["counts"]) + 1
    assert "only as good" in out["caveat"]


def test_probability_above_price_matches_price(chai: ValuationInputs) -> None:
    cheap = replace(chai, bridge=replace(chai.bridge, price=1.0))
    rich = replace(chai, bridge=replace(chai.bridge, price=1000.0))
    assert (
        montecarlo.run_monte_carlo(cheap, montecarlo.McSettings(runs=500))[
            "probability_above_price"
        ]
        == 1.0
    )
    assert (
        montecarlo.run_monte_carlo(rich, montecarlo.McSettings(runs=500))["probability_above_price"]
        == 0.0
    )


def test_invalid_draws_are_discarded_not_returned() -> None:
    from conftest import chai_dict, inputs_from_dict

    tight = replace(
        inputs_from_dict(chai_dict()), wacc_override=0.05, terminal=TerminalInputs(0.045)
    )
    out = montecarlo.run_monte_carlo(tight, montecarlo.McSettings(runs=500, wacc_sd=0.005))
    assert out["discarded_draws"] > 0  # many draws had terminal growth >= WACC
    assert np.isfinite(out["percentiles"]["p50"])


def test_run_count_bounds_and_speed(chai: ValuationInputs) -> None:
    with pytest.raises(InvalidAssumptionError):
        montecarlo.run_monte_carlo(chai, montecarlo.McSettings(runs=10))
    t = time.perf_counter()
    montecarlo.run_monte_carlo(chai)
    assert time.perf_counter() - t < 2.0  # 10,000 runs finish in about a second


def test_tcs_monte_carlo_end_to_end() -> None:
    s = loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots")
    b = defaults.build_defaults(s, peers_dir=ROOT / "data" / "snapshots")
    st = montecarlo.settings_from_context(
        0.015, 0.015, b.beta.std_error, b.inputs.wacc.equity_risk_premium
    )
    out = montecarlo.run_monte_carlo(b.inputs, st)
    assert out["percentiles"]["p5"] < out["base_fair_value"] < out["percentiles"]["p95"]
    assert out["ranges"]["wacc_sd"] == pytest.approx(
        max(0.0025, b.beta.std_error * b.inputs.wacc.equity_risk_premium)
    )
