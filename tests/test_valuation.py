"""Discounting, terminal value, bridge, warnings and reverse DCF (F5, F6, F18, F20)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from conftest import chai_dict
from dcf import terminal, valuation
from dcf.exceptions import InvalidAssumptionError
from dcf.forecast import OperatingAssumptions
from dcf.valuation import BridgeInputs, TerminalInputs, ValuationContext, ValuationInputs


def test_discounting_100_at_12_percent() -> None:
    got = [100 * valuation.discount_factor(0.12, t) for t in (1, 2, 3)]
    assert got == pytest.approx([89.29, 79.72, 71.18], abs=0.005)


def test_chai_corner_full_valuation_matches_spec(chai: ValuationInputs) -> None:
    r = valuation.run_valuation(chai)
    want = chai_dict()["expected"]
    assert r.wacc_used == pytest.approx(0.12)
    assert r.sum_pv_fcff == pytest.approx(want["sum_pv_fcff"], abs=0.1)
    assert r.terminal_value == pytest.approx(want["terminal_value"], abs=0.2)
    assert r.pv_terminal_value == pytest.approx(want["pv_terminal_value"], abs=0.2)
    assert r.enterprise_value == pytest.approx(want["enterprise_value"], abs=0.2)
    assert r.equity_value == pytest.approx(want["equity_value"], abs=0.2)
    assert round(r.fair_value_per_share, 1) == 26.8
    assert r.terminal_value_share == pytest.approx(0.71, abs=0.01)  # "about 71%"
    assert r.upside == pytest.approx(r.fair_value_per_share / 20.0 - 1)


def test_terminal_growth_at_or_above_wacc_is_refused(chai: ValuationInputs) -> None:
    for g in (0.12, 0.13):
        with pytest.raises(InvalidAssumptionError, match="lower than WACC"):
            terminal.gordon_terminal_value(100.0, 0.12, g)
    bad = replace(chai, terminal=TerminalInputs(growth=0.08), wacc_override=0.08)
    with pytest.raises(InvalidAssumptionError, match="Terminal growth"):
        valuation.run_valuation(bad)


def test_bridge_adds_and_subtracts_exact_amounts(chai: ValuationInputs) -> None:
    base = valuation.run_valuation(chai)
    br = chai.bridge

    def equity(**kw: float) -> float:
        return valuation.run_valuation(replace(chai, bridge=replace(br, **kw))).equity_value

    assert equity(debt=50.0) == pytest.approx(base.equity_value - 50.0)
    assert equity(leases=30.0) == pytest.approx(base.equity_value - 30.0)
    assert equity(minority_interest=20.0) == pytest.approx(base.equity_value - 20.0)
    assert equity(cash_and_investments=br.cash_and_investments + 40.0) == pytest.approx(
        base.equity_value + 40.0
    )
    assert base.bridge["equity_value"] == pytest.approx(
        base.enterprise_value
        + sum(v for k, v in base.bridge.items() if k.startswith(("less", "plus")))
    )


def test_mid_year_raises_value_by_half_year_of_discounting(chai: ValuationInputs) -> None:
    end = valuation.run_valuation(chai)
    mid = valuation.run_valuation(replace(chai, mid_year=True))
    assert mid.enterprise_value == pytest.approx(end.enterprise_value * 1.12**0.5)


def test_exit_multiple_cross_check(chai: ValuationInputs) -> None:
    r = valuation.run_valuation(replace(chai, terminal=TerminalInputs(0.04, exit_multiple=10.0)))
    x = r.exit_cross_check
    assert x is not None
    ebitda5 = r.forecast.ebit[-1] + r.forecast.da[-1]
    assert x["terminal_value"] == pytest.approx(ebitda5 * 10.0)
    assert x["pv_terminal_value"] == pytest.approx(ebitda5 * 10.0 / 1.12**5)
    assert x["implied_exit_multiple"] == pytest.approx(r.terminal_value / ebitda5)
    # the implied growth of the exit TV round-trips through the Gordon formula
    g = x["implied_perpetual_growth"]
    assert g is not None
    assert terminal.gordon_terminal_value(r.forecast.fcff[-1], 0.12, g) == pytest.approx(
        x["terminal_value"]
    )


def test_input_bounds_give_plain_sentences(chai: ValuationInputs) -> None:
    op = chai.operating
    cases = [
        (
            replace(chai, operating=replace(op, revenue_growth=(0.5,) * 5)),
            "Revenue growth must be between",
        ),
        (replace(chai, operating=replace(op, ebit_margin=(0.9,) * 5)), "EBIT margin"),
        (replace(chai, operating=replace(op, tax_rate=0.9)), "Tax rate"),
        (replace(chai, bridge=replace(chai.bridge, diluted_shares=-1.0)), "Diluted shares"),
        (replace(chai, bridge=replace(chai.bridge, debt=-5.0)), "Debt cannot be negative"),
        (replace(chai, bridge=replace(chai.bridge, price=0.0)), "price must be positive"),
        (replace(chai, terminal=TerminalInputs(growth=0.2)), "Terminal growth must be between"),
    ]
    for bad, msg in cases:
        with pytest.raises(InvalidAssumptionError, match=msg):
            valuation.run_valuation(bad)


def test_nonpositive_terminal_cash_flow_refused(chai: ValuationInputs) -> None:
    op = chai.operating
    broke = replace(chai, operating=replace(op, ebit_margin=(0.01,) * 5, capex_pct=0.2))
    with pytest.raises(InvalidAssumptionError, match="not positive"):
        valuation.run_valuation(broke)


def test_warnings_fire(chai: ValuationInputs) -> None:
    quiet = valuation.run_valuation(chai)
    assert [w.code for w in quiet.warnings] == []
    ctx = ValuationContext(margin_min=0.05, margin_max=0.08, roic=0.5, fcf_proxy_latest=10.0)
    loud_in = replace(
        chai,
        terminal=TerminalInputs(0.075),
        wacc=replace(chai.wacc, risk_free=0.05),
        wacc_override=0.12,
        bridge=replace(chai.bridge, price=1.0),
        context=ctx,
    )
    codes = {w.code for w in valuation.run_valuation(loud_in).warnings}
    assert {"TV_SHARE_HIGH", "TERMINAL_GROWTH_HIGH", "MARGIN_OUTSIDE_HISTORY"} <= codes
    assert {"FAIR_VALUE_FAR_FROM_PRICE", "FCFF_VS_CASH_FLOW"} <= codes
    low_wacc = valuation.run_valuation(
        replace(chai, wacc_override=0.05, terminal=TerminalInputs(0.03))
    )
    assert "WACC_OUTSIDE_BAND" in {w.code for w in low_wacc.warnings}


def test_roic_check_flags_free_growth() -> None:
    # NOPAT 100, FCFF 99 -> reinvests 1%; 5% growth at 25% ROIC needs 20%
    bad = terminal.roic_check(100.0, 99.0, 0.12, 0.05, 0.25)
    assert not bad.plausible and bad.required_reinvestment_rate == pytest.approx(0.20)
    assert bad.implied_return_on_new_capital == pytest.approx(5.0)
    ok = terminal.roic_check(100.0, 75.0, 0.12, 0.05, 0.25)
    assert ok.plausible
    # value-driver TV by hand: 100 x 1.05 x (1 - 0.2) / 0.07
    assert ok.value_driver_terminal_value == pytest.approx(100 * 1.05 * 0.8 / 0.07)
    assert terminal.roic_check(100.0, 75.0, 0.12, 0.05, None).message.startswith(
        "ROIC check unavailable"
    )


def test_reverse_dcf_recovers_known_growth(chai: ValuationInputs) -> None:
    n = chai.operating.years
    for known in (0.03, 0.10, 0.18):
        op = replace(chai.operating, revenue_growth=(known,) * n)
        base = replace(chai, operating=op)
        price = valuation.run_valuation(base).fair_value_per_share
        # start the solver from a different growth path: only the price carries the answer
        res = valuation.reverse_dcf(replace(chai, bridge=replace(chai.bridge, price=price)))
        assert res.status == "solved"
        assert res.implied_growth == pytest.approx(known, abs=1e-6)
        assert res.fair_value_at_solution == pytest.approx(price, rel=1e-6)


def test_reverse_dcf_reports_no_solution(chai: ValuationInputs) -> None:
    res = valuation.reverse_dcf(chai, target_price=1e9)
    assert res.status == "no_solution_in_bounds" and res.implied_growth is None
    with pytest.raises(InvalidAssumptionError):
        valuation.reverse_dcf(replace(chai, bridge=replace(chai.bridge, price=None)))


def test_operating_assumption_type_is_frozen(chai: ValuationInputs) -> None:
    assert isinstance(chai.operating, OperatingAssumptions)
    assert isinstance(chai.bridge, BridgeInputs)
    with pytest.raises(AttributeError):
        chai.operating.tax_rate = 0.3  # type: ignore[misc]
