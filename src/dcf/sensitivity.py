"""Sensitivity analysis (F7, F22): two-way grids and the tornado ranking.

Step 12 of the spec: recompute steps 7-11 across a grid. Grid axes are absolute values
(WACC, terminal growth) or shifts applied to every forecast year (revenue growth, margin).
Cells where the model cannot run (terminal growth >= WACC) are None.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from dcf.exceptions import InvalidAssumptionError
from dcf.valuation import TerminalInputs, ValuationInputs, run_valuation

WACC_STEPS = (-0.02, -0.01, 0.0, 0.01, 0.02)
GROWTH_STEPS = (-0.01, -0.005, 0.0, 0.005, 0.01)
OPERATING_STEPS = (-0.02, -0.01, 0.0, 0.01, 0.02)


def _fair_value(inputs: ValuationInputs) -> float | None:
    try:
        return run_valuation(inputs, validate=False).fair_value_per_share
    except InvalidAssumptionError:
        return None


def _base_wacc(inputs: ValuationInputs) -> float:
    return run_valuation(inputs, validate=False).wacc_used


def wacc_growth_grid(
    inputs: ValuationInputs,
    wacc_steps: tuple[float, ...] = WACC_STEPS,
    growth_steps: tuple[float, ...] = GROWTH_STEPS,
) -> dict[str, Any]:
    """Fair value per share over WACC (columns) x terminal growth (rows)."""
    base_w = _base_wacc(inputs)
    base_g = inputs.terminal.growth
    waccs = [base_w + d for d in wacc_steps]
    gs = [base_g + d for d in growth_steps]
    values: list[list[float | None]] = []
    for g in gs:
        row: list[float | None] = []
        for w in waccs:
            cell = replace(
                inputs, wacc_override=w, terminal=TerminalInputs(g, inputs.terminal.exit_multiple)
            )
            row.append(_fair_value(cell) if g < w and w > 0 else None)
        values.append(row)
    return _grid(
        "WACC", waccs, "Terminal growth", gs, values, wacc_steps.index(0.0), growth_steps.index(0.0),
        run_valuation(inputs, validate=False).fair_value_per_share,
    )  # fmt: skip


def growth_margin_grid(
    inputs: ValuationInputs,
    growth_steps: tuple[float, ...] = OPERATING_STEPS,
    margin_steps: tuple[float, ...] = OPERATING_STEPS,
) -> dict[str, Any]:
    """Fair value over revenue-growth shift (columns) x EBIT-margin shift (rows).

    Axis values are the resulting average revenue growth and average EBIT margin.
    """
    op = inputs.operating
    avg_g = sum(op.revenue_growth) / op.years
    avg_m = sum(op.ebit_margin) / op.years
    values: list[list[float | None]] = []
    for dm in margin_steps:
        row: list[float | None] = []
        for dg in growth_steps:
            row.append(_fair_value(replace(inputs, operating=op.shifted(growth=dg, margin=dm))))
        values.append(row)
    return _grid(
        "Average revenue growth", [avg_g + d for d in growth_steps],
        "Average EBIT margin", [avg_m + d for d in margin_steps],
        values, growth_steps.index(0.0), margin_steps.index(0.0),
        run_valuation(inputs, validate=False).fair_value_per_share,
    )  # fmt: skip


def _grid(
    col_label: str,
    cols: list[float],
    row_label: str,
    rows: list[float],
    values: list[list[float | None]],
    centre_col: int,
    centre_row: int,
    base: float,
) -> dict[str, Any]:
    return {
        "column_label": col_label,
        "columns": cols,
        "row_label": row_label,
        "rows": rows,
        "values": values,
        "centre": [centre_row, centre_col],
        "base_fair_value": base,
    }


def tornado(inputs: ValuationInputs, delta: float = 0.01) -> dict[str, Any]:
    """Move each assumption by +/- ``delta`` (one point) and rank by effect on fair value."""
    op = inputs.operating
    base_fv = run_valuation(inputs, validate=False).fair_value_per_share
    base_w = _base_wacc(inputs)
    g = inputs.terminal.growth

    def vary(name: str, make: Any, low_label: float, high_label: float) -> dict[str, Any]:
        lo_in, hi_in = make(-delta), make(+delta)
        lo, hi = _fair_value(lo_in), _fair_value(hi_in)
        return {
            "name": name,
            "low_input": low_label,
            "high_input": high_label,
            "fair_value_low_input": lo,
            "fair_value_high_input": hi,
            "swing": abs((hi if hi is not None else base_fv) - (lo if lo is not None else base_fv)),
        }

    avg_g = sum(op.revenue_growth) / op.years
    avg_m = sum(op.ebit_margin) / op.years
    rows = [
        vary("Revenue growth (all years)", lambda d: replace(inputs, operating=op.shifted(growth=d)), avg_g - delta, avg_g + delta),
        vary("EBIT margin (all years)", lambda d: replace(inputs, operating=op.shifted(margin=d)), avg_m - delta, avg_m + delta),
        vary("WACC", lambda d: replace(inputs, wacc_override=base_w + d), base_w - delta, base_w + delta),
        vary("Terminal growth", lambda d: replace(inputs, terminal=TerminalInputs(g + d, inputs.terminal.exit_multiple)), g - delta, g + delta),
        vary("Tax rate", lambda d: replace(inputs, operating=replace(op, tax_rate=op.tax_rate + d)), op.tax_rate - delta, op.tax_rate + delta),
        vary("CapEx % of revenue", lambda d: replace(inputs, operating=replace(op, capex_pct=max(0.0, op.capex_pct + d))), op.capex_pct - delta, op.capex_pct + delta),
        vary("Working capital % of revenue", lambda d: replace(inputs, operating=replace(op, nwc_pct=op.nwc_pct + d)), op.nwc_pct - delta, op.nwc_pct + delta),
    ]  # fmt: skip
    rows.sort(key=lambda r: r["swing"], reverse=True)
    return {"base_fair_value": base_fv, "delta": delta, "rows": rows}
