"""Property-based tests (F27): rules that must hold for every valid input."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from dcf import montecarlo, valuation
from dcf.exceptions import InvalidAssumptionError
from dcf.forecast import OperatingAssumptions
from dcf.valuation import BridgeInputs, TerminalInputs, ValuationInputs
from dcf.wacc import WaccInputs

SETTINGS = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def pct(lo: float, hi: float) -> st.SearchStrategy[float]:
    return st.floats(min_value=lo, max_value=hi, allow_nan=False, allow_infinity=False)


@st.composite
def valid_inputs(draw: st.DrawFn) -> ValuationInputs:
    """Inputs inside the config bounds with positive unit economics (k > NWC %)."""
    years = 5
    margin = draw(pct(0.05, 0.40))
    tax = draw(pct(0.10, 0.35))
    da = draw(pct(0.0, 0.08))
    capex = draw(pct(0.0, 0.08))
    nwc = draw(pct(0.0, 0.25))
    k = margin * (1 - tax) + da - capex
    assume(k > nwc + 0.01)  # each extra rupee of revenue adds value
    op = OperatingAssumptions(
        base_revenue=draw(pct(100.0, 500_000.0)),
        revenue_growth=tuple(draw(pct(-0.05, 0.25)) for _ in range(years)),
        ebit_margin=(margin,) * years,
        tax_rate=tax,
        da_pct=da,
        capex_pct=capex,
        nwc_pct=nwc,
    )
    rf = draw(pct(0.03, 0.10))
    erp = draw(pct(0.03, 0.09))
    beta = draw(pct(0.5, 1.6))
    wacc_in = WaccInputs(rf, beta, erp, draw(pct(0.04, 0.14)), draw(pct(0.0, 0.5)), tax)
    g = draw(pct(0.0, 0.06))
    bridge = BridgeInputs(
        debt=draw(pct(0.0, 5000.0)),
        leases=draw(pct(0.0, 5000.0)),
        cash_and_investments=draw(pct(0.0, 50_000.0)),
        minority_interest=draw(pct(0.0, 2000.0)),
        diluted_shares=draw(pct(1.0, 1000.0)),
        price=draw(pct(1.0, 10_000.0)),
    )
    return ValuationInputs(op, wacc_in, TerminalInputs(g), bridge, mid_year=draw(st.booleans()))


def run(inp: ValuationInputs) -> valuation.ValuationResult | None:
    try:
        return valuation.run_valuation(inp)
    except InvalidAssumptionError:
        return None  # a clear, controlled refusal is allowed; a crash is not


@SETTINGS
@given(valid_inputs())
def test_random_valid_inputs_never_crash_and_are_finite(inp: ValuationInputs) -> None:
    r = run(inp)
    if r is not None:
        for x in (r.enterprise_value, r.equity_value, r.fair_value_per_share, r.terminal_value):
            assert math.isfinite(x)
        assert all(math.isfinite(f) for f in r.forecast.fcff)


@SETTINGS
@given(valid_inputs(), pct(0.001, 0.05))
def test_higher_wacc_never_raises_value(inp: ValuationInputs, bump: float) -> None:
    base = run(replace(inp, wacc_override=0.12))
    higher = run(replace(inp, wacc_override=0.12 + bump))
    assume(base is not None and higher is not None)
    assert base is not None and higher is not None
    assert higher.enterprise_value <= base.enterprise_value + 1e-9


@SETTINGS
@given(valid_inputs(), pct(0.001, 0.02))
def test_higher_terminal_growth_never_lowers_value(inp: ValuationInputs, bump: float) -> None:
    lo = run(replace(inp, wacc_override=0.14, terminal=TerminalInputs(0.03)))
    hi = run(replace(inp, wacc_override=0.14, terminal=TerminalInputs(0.03 + bump)))
    assume(lo is not None and hi is not None)
    assert lo is not None and hi is not None
    assert hi.enterprise_value >= lo.enterprise_value - 1e-9


@SETTINGS
@given(valid_inputs(), pct(0.001, 0.03))
def test_higher_revenue_growth_and_margin_never_lower_value(
    inp: ValuationInputs, bump: float
) -> None:
    base = run(replace(inp, wacc_override=0.14, terminal=TerminalInputs(0.03)))
    more_growth = run(
        replace(
            inp,
            wacc_override=0.14,
            terminal=TerminalInputs(0.03),
            operating=inp.operating.shifted(growth=bump),
        )
    )
    more_margin = run(
        replace(
            inp,
            wacc_override=0.14,
            terminal=TerminalInputs(0.03),
            operating=inp.operating.shifted(margin=bump),
        )
    )
    assume(base is not None and more_growth is not None and more_margin is not None)
    assert base is not None and more_growth is not None and more_margin is not None
    assert more_growth.enterprise_value >= base.enterprise_value - 1e-9
    assert more_margin.enterprise_value >= base.enterprise_value - 1e-9


@SETTINGS
@given(valid_inputs())
def test_bridge_always_adds_up(inp: ValuationInputs) -> None:
    r = run(inp)
    assume(r is not None)
    assert r is not None
    b = inp.bridge
    assert math.isclose(r.enterprise_value, r.sum_pv_fcff + r.pv_terminal_value, rel_tol=1e-12)
    assert math.isclose(
        r.equity_value,
        r.enterprise_value - b.debt - b.leases + b.cash_and_investments - b.minority_interest,
        rel_tol=1e-9,
        abs_tol=1e-6,
    )
    assert math.isclose(
        r.fair_value_per_share * b.diluted_shares, r.equity_value, rel_tol=1e-9, abs_tol=1e-6
    )
    assert math.isclose(
        sum(r.bridge.values()) - r.bridge["equity_value"],
        r.equity_value,
        rel_tol=1e-9,
        abs_tol=1e-6,
    )


@SETTINGS
@given(valid_inputs())
def test_mid_year_never_below_end_of_year(inp: ValuationInputs) -> None:
    end = run(replace(inp, mid_year=False))
    mid = run(replace(inp, mid_year=True))
    assume(end is not None and mid is not None)
    assert end is not None and mid is not None
    if end.enterprise_value > 0:
        assert mid.enterprise_value >= end.enterprise_value


@SETTINGS
@given(valid_inputs(), st.integers(0, 2**31))
def test_vector_engine_agrees_with_scalar_engine(inp: ValuationInputs, seed: int) -> None:
    rng = np.random.default_rng(seed)
    dg, dm = rng.uniform(-0.01, 0.01, 3), rng.uniform(-0.01, 0.01, 3)
    w, g = rng.uniform(0.09, 0.2, 3), rng.uniform(0.0, 0.06, 3)
    fv, valid = montecarlo.vector_fair_values(inp, dg, dm, w, g)
    for i in range(3):
        if not valid[i]:
            continue
        scalar = run(
            replace(
                inp,
                operating=inp.operating.shifted(growth=float(dg[i]), margin=float(dm[i])),
                wacc_override=float(w[i]),
                terminal=TerminalInputs(float(g[i])),
            )
        )
        if scalar is not None:
            assert math.isclose(fv[i], scalar.fair_value_per_share, rel_tol=1e-9)


@SETTINGS
@given(valid_inputs())
def test_reverse_dcf_fair_value_equals_price_when_solved(inp: ValuationInputs) -> None:
    base = run(replace(inp, wacc_override=0.14, terminal=TerminalInputs(0.03)))
    assume(base is not None and base.fair_value_per_share > 0)
    assert base is not None
    target = base.fair_value_per_share
    res = valuation.reverse_dcf(
        replace(inp, wacc_override=0.14, terminal=TerminalInputs(0.03)), target_price=target
    )
    if res.status == "solved":
        assert res.fair_value_at_solution is not None
        assert math.isclose(res.fair_value_at_solution, target, rel_tol=1e-6)
