"""Excel export (F12) and the Python-vs-Excel reconciliation (F8).

The workbook is recalculated with the independent ``formulas`` engine (a spreadsheet
formula interpreter), so a match proves the Excel formulas, not just the Python, are right.
"""

from __future__ import annotations

import io
from dataclasses import replace
from pathlib import Path
from typing import Any

import formulas
import openpyxl
import pytest

from conftest import chai_dict, inputs_from_dict
from dcf import defaults, export, loader, sensitivity, valuation
from dcf.valuation import TerminalInputs, ValuationInputs

ROOT = Path(__file__).resolve().parent.parent
COLS = "BCDEF"


class Calc:
    """Recalculate .xlsx bytes and read cell values."""

    def __init__(self, data: bytes, tmp: Path, name: str) -> None:
        path = tmp / f"{name}.xlsx"
        path.write_bytes(data)
        self.sol = formulas.ExcelModel().loads(str(path)).finish().calculate()

    def get(self, sheet: str, ref: str) -> Any:
        for key, val in self.sol.items():
            if key.upper().endswith(f"{sheet.upper()}'!{ref}"):
                return val.value[0, 0]
        raise KeyError(f"{sheet}!{ref}")


def chai_with_exit() -> ValuationInputs:
    base = inputs_from_dict(chai_dict())
    return replace(base, terminal=TerminalInputs(0.04, exit_multiple=10.0))


@pytest.fixture(scope="module")
def chai_calc(tmp_path_factory: pytest.TempPathFactory) -> tuple[Calc, ValuationInputs]:
    inp = chai_with_exit()
    data = export.export_workbook_bytes(
        inp, valuation.run_valuation(inp), {"name": "Chai", "ticker": "CHAI"}
    )
    return Calc(data, tmp_path_factory.mktemp("xl"), "chai"), inp


def test_workbook_structure_has_live_formulas() -> None:
    inp = chai_with_exit()
    wb = openpyxl.load_workbook(io.BytesIO(export.export_workbook_bytes(inp)))
    assert wb.sheetnames == [
        "Assumptions",
        "Forecast",
        "WACC",
        "Valuation",
        "Sensitivity",
        "Reconciliation",
        "Notes",
    ]
    assert str(wb["Forecast"]["D4"].value).startswith("=")
    assert str(wb["Valuation"]["B15"].value) == "=B12+B14"
    assert str(wb["Sensitivity"]["D7"].value).startswith("=IF(")
    assert wb["Assumptions"]["B6"].font.color.rgb.endswith("0000FF")  # inputs are blue
    # Assumptions hold constants only (no formulas)
    assert all(
        not str(c.value).startswith("=")
        for row in wb["Assumptions"].iter_rows()
        for c in row
        if c.value is not None
    )


def test_excel_matches_python_chai(chai_calc: tuple[Calc, ValuationInputs]) -> None:
    calc, inp = chai_calc
    py = valuation.run_valuation(inp)
    assert calc.get("VALUATION", "B3") == pytest.approx(py.wacc_used)
    for i, col in enumerate(COLS):
        assert calc.get("VALUATION", f"{col}7") == pytest.approx(py.forecast.fcff[i], rel=1e-12)
    for ref, want in (("B12", py.sum_pv_fcff), ("B13", py.terminal_value), ("B14", py.pv_terminal_value),
                      ("B15", py.enterprise_value), ("B22", py.equity_value), ("B23", py.fair_value_per_share),
                      ("B25", py.upside)):  # fmt: skip
        assert calc.get("VALUATION", ref) == pytest.approx(want, rel=1e-12)
    assert round(calc.get("VALUATION", "B23"), 1) == 26.8
    x = py.exit_cross_check
    assert x is not None
    assert calc.get("VALUATION", "B33") == pytest.approx(x["fair_value_per_share"], rel=1e-12)
    assert calc.get("VALUATION", "B34") == pytest.approx(x["implied_exit_multiple"], rel=1e-12)
    assert calc.get("RECONCILIATION", "B18") == "ALL MATCH"


def test_excel_sensitivity_grids_match_python(chai_calc: tuple[Calc, ValuationInputs]) -> None:
    calc, inp = chai_calc
    g1 = sensitivity.wacc_growth_grid(inp)
    g2 = sensitivity.growth_margin_grid(inp)
    for i in range(5):
        for j in range(5):
            assert calc.get("SENSITIVITY", f"{COLS[j]}{5 + i}") == pytest.approx(
                g1["values"][i][j], rel=1e-12
            )
            assert calc.get("SENSITIVITY", f"{COLS[j]}{15 + i}") == pytest.approx(
                g2["values"][i][j], rel=1e-12
            )
    assert calc.get("SENSITIVITY", "D7") == pytest.approx(
        g1["base_fair_value"]
    )  # centre = base case


def test_workbook_is_live_edit_inputs_and_it_recalculates(tmp_path: Path) -> None:
    """Change blue cells in the workbook; the formulas must give what the engine gives."""
    inp = chai_with_exit()
    wb = openpyxl.load_workbook(io.BytesIO(export.export_workbook_bytes(inp)))
    a = wb["Assumptions"]
    for col in COLS:
        a[f"{col}6"] = 0.08  # revenue growth
        a[f"{col}7"] = 0.22  # EBIT margin
    a["B8"] = 0.27  # tax
    a["B21"] = 1  # mid-year on
    a["B24"] = 0.05  # terminal growth
    a["B30"] = 450.0  # cash
    a["B29"] = 40.0  # leases
    a["B20"] = 0.115  # WACC override
    buf = io.BytesIO()
    wb.save(buf)
    calc = Calc(buf.getvalue(), tmp_path, "edited")

    edited = replace(
        inp,
        operating=replace(
            inp.operating, revenue_growth=(0.08,) * 5, ebit_margin=(0.22,) * 5, tax_rate=0.27
        ),
        terminal=TerminalInputs(0.05, exit_multiple=10.0),
        bridge=replace(inp.bridge, cash_and_investments=450.0, leases=40.0),
        mid_year=True,
        wacc_override=0.115,
    )
    py = valuation.run_valuation(edited)
    assert calc.get("VALUATION", "B3") == pytest.approx(0.115)
    assert calc.get("VALUATION", "B15") == pytest.approx(py.enterprise_value, rel=1e-12)
    assert calc.get("VALUATION", "B23") == pytest.approx(py.fair_value_per_share, rel=1e-12)
    grid = sensitivity.wacc_growth_grid(edited)
    assert calc.get("SENSITIVITY", "D7") == pytest.approx(grid["values"][2][2], rel=1e-12)
    assert calc.get("SENSITIVITY", "B5") == pytest.approx(grid["values"][0][0], rel=1e-12)


def test_excel_matches_python_on_tcs_to_the_rupee(tmp_path: Path) -> None:
    snap = loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots")
    bundle = defaults.build_defaults(snap, peers_dir=ROOT / "data" / "snapshots")
    py = valuation.run_valuation(bundle.inputs)
    data = export.export_workbook_bytes(
        bundle.inputs, py,
        {"name": snap["name"], "ticker": snap["ticker"], "source": snap["source"],
         "fetched_at": snap["fetched_at"], "sources": bundle.sources},
    )  # fmt: skip
    calc = Calc(data, tmp_path, "tcs")
    # INR crore, so a difference below 0.5 would already be under one rupee-crore; we do much better
    assert calc.get("VALUATION", "B15") == pytest.approx(py.enterprise_value, abs=1e-6)
    assert calc.get("VALUATION", "B22") == pytest.approx(py.equity_value, abs=1e-6)
    assert calc.get("VALUATION", "B23") == pytest.approx(py.fair_value_per_share, abs=1e-9)
    recon = openpyxl.load_workbook(io.BytesIO(data))["Reconciliation"]
    overall_row = next(r for r in range(1, 40) if recon[f"A{r}"].value == "Overall")
    assert calc.get("RECONCILIATION", f"B{overall_row}") == "ALL MATCH"
