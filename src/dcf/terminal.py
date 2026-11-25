"""Terminal value (F5) and the value-creation check (F20).

Spec section 7, step 8:

    TV = FCFF_N x (1 + g) / (WACC - g)         perpetuity growth (default)
    TV = EBITDA_N x exit multiple               cross-check

The model refuses to run when g >= WACC: the formula would give a negative or
infinite value.
"""

from __future__ import annotations

from dataclasses import dataclass

from dcf.exceptions import InvalidAssumptionError


def gordon_terminal_value(fcff_n: float, wacc: float, growth: float) -> float:
    """TV = FCFF_N x (1 + g) / (WACC - g). Raises InvalidAssumptionError if g >= WACC."""
    if growth >= wacc:
        raise InvalidAssumptionError(
            f"Terminal growth ({growth:.2%}) must be lower than WACC ({wacc:.2%})."
        )
    return fcff_n * (1.0 + growth) / (wacc - growth)


def exit_multiple_terminal_value(ebitda_n: float, multiple: float) -> float:
    """TV = EBITDA_N x EV/EBITDA exit multiple."""
    if multiple <= 0:
        raise InvalidAssumptionError("Exit multiple must be positive.")
    return ebitda_n * multiple


def implied_exit_multiple(terminal_value: float, ebitda_n: float) -> float | None:
    """EV/EBITDA multiple that a perpetuity-growth terminal value implies."""
    return terminal_value / ebitda_n if ebitda_n > 0 else None


def implied_perpetual_growth(terminal_value: float, fcff_n: float, wacc: float) -> float | None:
    """Growth rate g that makes the Gordon formula give ``terminal_value``.

    From TV = FCFF x (1 + g) / (WACC - g):  g = (TV x WACC - FCFF) / (TV + FCFF).
    """
    denom = terminal_value + fcff_n
    return None if denom == 0 else (terminal_value * wacc - fcff_n) / denom


@dataclass(frozen=True)
class RoicCheck:
    """Does the terminal growth come with enough reinvestment? (F20)

    Growing forever costs money: reinvestment rate = g / ROIC. If the model reinvests
    less than that, growth is effectively free and the terminal value is too high.
    """

    terminal_growth: float
    model_reinvestment_rate: float  # 1 - FCFF_N / NOPAT_N
    historical_roic: float | None
    required_reinvestment_rate: float | None  # g / historical ROIC
    implied_return_on_new_capital: float | None  # g / model reinvestment rate
    value_driver_terminal_value: float | None  # TV with reinvestment = g / ROIC
    plausible: bool
    message: str


def value_driver_terminal_value(nopat_n: float, wacc: float, growth: float, roic: float) -> float:
    """TV = NOPAT_N x (1 + g) x (1 - g / ROIC) / (WACC - g).  Growth must be paid for."""
    if growth >= wacc:
        raise InvalidAssumptionError(
            f"Terminal growth ({growth:.2%}) must be lower than WACC ({wacc:.2%})."
        )
    return nopat_n * (1.0 + growth) * (1.0 - growth / roic) / (wacc - growth)


def roic_check(
    nopat_n: float, fcff_n: float, wacc: float, growth: float, historical_roic: float | None
) -> RoicCheck:
    """Compare the model's terminal reinvestment with what growth g needs at the historical ROIC."""
    reinvest = 1.0 - fcff_n / nopat_n if nopat_n > 0 else float("nan")
    if historical_roic is None or historical_roic <= 0 or nopat_n <= 0:
        return RoicCheck(growth, reinvest, historical_roic, None, None, None, True,
                         "ROIC check unavailable: invested capital is not in the data.")  # fmt: skip
    required = growth / historical_roic
    implied = growth / reinvest if reinvest > 0 else None
    vd = value_driver_terminal_value(nopat_n, wacc, growth, historical_roic)
    plausible = reinvest >= required * 0.999999
    if plausible:
        msg = (
            f"Terminal reinvestment ({reinvest:.1%} of NOPAT) covers the {required:.1%} that "
            f"{growth:.1%} growth needs at the historical ROIC of {historical_roic:.0%}."
        )
    else:
        shown = "no reinvestment" if implied is None else f"a {implied:.0%} return on new capital"
        msg = (
            f"Terminal reinvestment ({reinvest:.1%} of NOPAT) is below the {required:.1%} that "
            f"{growth:.1%} growth needs at the historical ROIC of {historical_roic:.0%}: the model "
            f"assumes {shown}. Growth is partly free; compare with the value-driver terminal value."
        )
    return RoicCheck(growth, reinvest, historical_roic, required, implied, vd, plausible, msg)
