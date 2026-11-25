"""Bear / base / bull scenarios (F10) and probability weighting (F26).

Scenario swings are tied to the company's own history: half of the historical spread of
revenue growth and EBIT margin (with a floor), applied to every forecast year. Terminal
growth moves by half a point. WACC is held constant: scenarios describe the business, not
the cost of capital.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from dcf.exceptions import InvalidAssumptionError
from dcf.historical import Historical
from dcf.valuation import TerminalInputs, ValuationInputs, run_valuation

NAMES = ("bear", "base", "bull")
DEFAULT_PROBABILITIES = {"bear": 0.25, "base": 0.50, "bull": 0.25}
GROWTH_FLOOR, GROWTH_CAP = 0.015, 0.05
MARGIN_FLOOR, MARGIN_CAP = 0.015, 0.05
TERMINAL_GROWTH_SWING = 0.005


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    growth_shift: float
    margin_shift: float
    terminal_growth_shift: float


def build_specs(hist: Historical) -> dict[str, ScenarioSpec]:
    """Bear/base/bull shifts from the historical spread (floored and capped)."""
    g, m = hist.summary["revenue_growth"], hist.summary["ebit_margin"]

    def swing(s: dict[str, float | None], floor: float, cap: float) -> float:
        if s["min"] is None or s["max"] is None:
            return floor
        return min(max((s["max"] - s["min"]) / 2.0, floor), cap)

    dg, dm = swing(g, GROWTH_FLOOR, GROWTH_CAP), swing(m, MARGIN_FLOOR, MARGIN_CAP)
    return {
        "bear": ScenarioSpec("bear", -dg, -dm, -TERMINAL_GROWTH_SWING),
        "base": ScenarioSpec("base", 0.0, 0.0, 0.0),
        "bull": ScenarioSpec("bull", dg, dm, TERMINAL_GROWTH_SWING),
    }


def apply_scenario(inputs: ValuationInputs, spec: ScenarioSpec) -> ValuationInputs:
    """Inputs with the scenario's shifts applied (margins and growth floored at their bounds)."""
    op = inputs.operating.shifted(growth=spec.growth_shift, margin=spec.margin_shift)
    op = replace(op, ebit_margin=tuple(max(0.0, m) for m in op.ebit_margin))
    term = TerminalInputs(
        max(0.0, inputs.terminal.growth + spec.terminal_growth_shift), inputs.terminal.exit_multiple
    )
    return replace(inputs, operating=op, terminal=term)


def check_probabilities(p: dict[str, float]) -> None:
    if set(p) != set(NAMES):
        raise InvalidAssumptionError("Provide a probability for each of bear, base and bull.")
    if any(v < 0 for v in p.values()):
        raise InvalidAssumptionError("Scenario probabilities cannot be negative.")
    if abs(sum(p.values()) - 1.0) > 1e-6:
        raise InvalidAssumptionError("Scenario probabilities must add up to 100%.")


def run_scenarios(
    inputs: ValuationInputs,
    specs: dict[str, ScenarioSpec],
    probabilities: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Fair value in each scenario and the probability-weighted expected value."""
    probs = probabilities or DEFAULT_PROBABILITIES
    check_probabilities(probs)
    results: dict[str, Any] = {}
    for name in NAMES:
        r = run_valuation(apply_scenario(inputs, specs[name]))
        results[name] = {
            "spec": specs[name],
            "fair_value_per_share": r.fair_value_per_share,
            "enterprise_value": r.enterprise_value,
            "upside": r.upside,
            "probability": probs[name],
            "warnings": [w.code for w in r.warnings],
        }
    expected = sum(results[n]["fair_value_per_share"] * probs[n] for n in NAMES)
    price = inputs.bridge.price
    return {
        "scenarios": results,
        "expected_fair_value": expected,
        "expected_upside": expected / price - 1.0 if price else None,
    }
