"""Sensitivity grids, tornado (F7, F22), scenarios (F10, F26)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from dcf import defaults, loader, scenarios, sensitivity, valuation
from dcf.exceptions import InvalidAssumptionError
from dcf.valuation import ValuationInputs

ROOT = Path(__file__).resolve().parent.parent


def test_wacc_growth_grid_centre_equals_base(chai: ValuationInputs) -> None:
    grid = sensitivity.wacc_growth_grid(chai)
    r, c = grid["centre"]
    base = valuation.run_valuation(chai).fair_value_per_share
    assert grid["values"][r][c] == pytest.approx(base)
    assert grid["base_fair_value"] == pytest.approx(base)
    assert round(grid["values"][r][c], 1) == 26.8


def test_wacc_growth_grid_monotonic_and_matches_direct_run(chai: ValuationInputs) -> None:
    grid = sensitivity.wacc_growth_grid(chai)
    vals = grid["values"]
    for row in vals:  # higher WACC (to the right) lowers value
        assert all(a > b for a, b in zip(row[:-1], row[1:], strict=True))
    for col in range(5):  # higher terminal growth (down the rows) raises value
        column = [vals[i][col] for i in range(5)]
        assert all(a < b for a, b in zip(column[:-1], column[1:], strict=True))
    # one off-centre cell recomputed independently: WACC 13%, terminal growth 4.5%
    direct = valuation.run_valuation(
        replace(chai, wacc_override=0.13, terminal=replace(chai.terminal, growth=0.045))
    ).fair_value_per_share
    assert vals[3][3] == pytest.approx(direct)


def test_grid_blanks_cells_where_growth_reaches_wacc(chai: ValuationInputs) -> None:
    tight = replace(chai, wacc_override=0.05, terminal=replace(chai.terminal, growth=0.04))
    grid = sensitivity.wacc_growth_grid(tight)
    assert any(v is None for row in grid["values"] for v in row)
    r, c = grid["centre"]
    assert grid["values"][r][c] is not None


def test_growth_margin_grid_centre_and_direction(chai: ValuationInputs) -> None:
    grid = sensitivity.growth_margin_grid(chai)
    r, c = grid["centre"]
    assert grid["values"][r][c] == pytest.approx(valuation.run_valuation(chai).fair_value_per_share)
    assert grid["values"][r][4] > grid["values"][r][0]  # more growth -> more value
    assert grid["values"][4][c] > grid["values"][0][c]  # higher margin -> more value
    assert grid["columns"][c] == pytest.approx(0.10) and grid["rows"][r] == pytest.approx(0.20)


def test_tornado_ranks_by_swing(chai: ValuationInputs) -> None:
    t = sensitivity.tornado(chai)
    swings = [row["swing"] for row in t["rows"]]
    assert swings == sorted(swings, reverse=True)
    assert {row["name"] for row in t["rows"]} >= {
        "WACC",
        "Terminal growth",
        "EBIT margin (all years)",
    }
    wacc = next(row for row in t["rows"] if row["name"] == "WACC")
    # one point lower WACC -> higher value
    assert wacc["fair_value_low_input"] > t["base_fair_value"] > wacc["fair_value_high_input"]


def test_scenarios_differ_and_order(chai: ValuationInputs) -> None:
    from dcf.historical import compute_historical

    s = loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots")
    specs = scenarios.build_specs(compute_historical(s))
    out = scenarios.run_scenarios(chai, specs)
    fv = {n: out["scenarios"][n]["fair_value_per_share"] for n in scenarios.NAMES}
    assert fv["bear"] < fv["base"] < fv["bull"]
    assert fv["base"] == pytest.approx(valuation.run_valuation(chai).fair_value_per_share)
    exp = 0.25 * fv["bear"] + 0.5 * fv["base"] + 0.25 * fv["bull"]
    assert out["expected_fair_value"] == pytest.approx(exp)


def test_scenario_specs_tied_to_history_with_floor_and_cap() -> None:
    from dcf.historical import compute_historical

    s = loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots")
    specs = scenarios.build_specs(compute_historical(s))
    assert specs["bull"].growth_shift >= scenarios.GROWTH_FLOOR
    assert specs["bear"].growth_shift == -specs["bull"].growth_shift
    assert specs["base"].margin_shift == 0.0


def test_probability_validation(chai: ValuationInputs) -> None:
    specs = {n: scenarios.ScenarioSpec(n, 0.0, 0.0, 0.0) for n in scenarios.NAMES}
    for bad in (
        {"bear": 0.5, "base": 0.5, "bull": 0.5},
        {"bear": -0.1, "base": 0.6, "bull": 0.5},
        {"bear": 0.5, "base": 0.5},
    ):
        with pytest.raises(InvalidAssumptionError):
            scenarios.run_scenarios(chai, specs, bad)
    ok = scenarios.run_scenarios(chai, specs, {"bear": 0.2, "base": 0.6, "bull": 0.2})
    assert ok["expected_fair_value"] == pytest.approx(
        valuation.run_valuation(chai).fair_value_per_share
    )


def test_tcs_scenarios_give_sensible_spread() -> None:
    s = loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots")
    bundle = defaults.build_defaults(s, peers_dir=ROOT / "data" / "snapshots")
    out = scenarios.run_scenarios(bundle.inputs, scenarios.build_specs(bundle.historical))
    fv = [out["scenarios"][n]["fair_value_per_share"] for n in scenarios.NAMES]
    assert fv[0] < fv[1] < fv[2]
    assert 0.5 < fv[0] / fv[2] < 0.95  # different but not absurd
