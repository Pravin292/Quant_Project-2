"""Excel export (F12): the full model as a workbook with live formulas.

Sheets: Assumptions (blue input cells), Forecast, WACC, Valuation, Sensitivity,
Reconciliation (Python result next to the Excel formula result) and Notes.
Change any blue cell and every sheet recalculates. The sensitivity grids are formulas too.
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from dcf.sensitivity import GROWTH_STEPS, OPERATING_STEPS, WACC_STEPS
from dcf.valuation import ValuationInputs, ValuationResult, run_valuation

INPUT = Font(color="0000FF")
BOLD = Font(bold=True)
HEAD = PatternFill("solid", fgColor="DDE6F2")
COLS = ["B", "C", "D", "E", "F"]  # Assumptions per-year columns (years 1-5)
FCOLS = ["C", "D", "E", "F", "G"]  # Forecast columns (year 0 is column B)
DISCLAIMER = "Educational model. Not investment advice. Estimates based on stated assumptions."


def _title(ws: Worksheet, text: str) -> None:
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=14)
    ws.column_dimensions["A"].width = 34


def _header(ws: Worksheet, row: int, text: str, width: int = 7) -> None:
    ws.cell(row=row, column=1, value=text).font = BOLD
    for c in range(1, width + 1):
        ws.cell(row=row, column=c).fill = HEAD


def _put(ws: Worksheet, ref: str, value: Any, fmt: str | None = None, inp: bool = False) -> None:
    ws[ref] = value
    if fmt:
        ws[ref].number_format = fmt
    if inp:
        ws[ref].font = INPUT


def build_workbook(
    inputs: ValuationInputs,
    result: ValuationResult | None = None,
    meta: dict[str, Any] | None = None,
) -> Workbook:
    """Build the workbook. ``result`` (Python) is used only for the Reconciliation sheet."""
    meta = meta or {}
    res = result or run_valuation(inputs)
    op, w, t, br = inputs.operating, inputs.wacc, inputs.terminal, inputs.bridge
    n = op.years
    if n != 5:
        raise ValueError("The Excel export is laid out for a five-year forecast.")

    wb = Workbook()
    wb.calculation.fullCalcOnLoad = True
    a = wb.active
    a.title = "Assumptions"
    _title(
        a,
        f"Assumptions: {meta.get('name', 'Company')} ({meta.get('ticker', '')})   [blue = editable input]",
    )
    pct, num = "0.00%", "#,##0.00"

    _header(a, 3, "Operating assumptions")
    _put(a, "A4", "Base revenue (year 0), INR crore")
    _put(a, "B4", op.base_revenue, num, True)
    a["A5"] = "Forecast year"
    for i, c in enumerate(COLS):
        a[f"{c}5"] = i + 1
        a[f"{c}6"] = op.revenue_growth[i]
        a[f"{c}6"].number_format = pct
        a[f"{c}6"].font = INPUT
        a[f"{c}7"] = op.ebit_margin[i]
        a[f"{c}7"].number_format = pct
        a[f"{c}7"].font = INPUT
    a["A6"], a["A7"] = "Revenue growth", "EBIT margin"
    for r, label, val in ((8, "Tax rate", op.tax_rate), (9, "D&A % of revenue", op.da_pct),
                          (10, "CapEx % of revenue", op.capex_pct), (11, "Net working capital % of revenue", op.nwc_pct)):  # fmt: skip
        a[f"A{r}"] = label
        _put(a, f"B{r}", val, pct, True)

    _header(a, 13, "Discount rate (WACC) inputs")
    for r, label, val, fmt in (
        (14, "Risk-free rate", w.risk_free, pct), (15, "Beta", w.beta, "0.000"),
        (16, "Equity risk premium", w.equity_risk_premium, pct), (17, "Cost of debt (pre-tax)", w.cost_of_debt, pct),
        (18, "Debt weight D/(D+E)", w.debt_weight, pct), (19, "Tax rate for debt shield", w.tax_rate, pct),
    ):  # fmt: skip
        a[f"A{r}"] = label
        _put(a, f"B{r}", val, fmt, True)
    a["A20"] = "WACC override (optional, replaces computed WACC)"
    if inputs.wacc_override is not None:
        _put(a, "B20", inputs.wacc_override, pct, True)
    a["A21"] = "Mid-year discounting (1 = on, 0 = end of year)"
    _put(a, "B21", 1 if inputs.mid_year else 0, "0", True)

    _header(a, 23, "Terminal value")
    a["A24"] = "Terminal growth"
    _put(a, "B24", t.growth, pct, True)
    a["A25"] = "Exit EV/EBITDA multiple (cross-check)"
    if t.exit_multiple is not None:
        _put(a, "B25", t.exit_multiple, "0.00", True)

    _header(a, 27, "Equity bridge and market data")
    bridge_rows: tuple[tuple[int, str, float | None], ...] = (
        (28, "Debt (borrowings)", br.debt), (29, "Lease liabilities (treated as debt)", br.leases),
        (30, "Cash and liquid investments", br.cash_and_investments), (31, "Minority interest", br.minority_interest),
        (32, "Diluted shares (same unit as money, crore)", br.diluted_shares), (33, "Market price per share (INR)", br.price),
    )  # fmt: skip
    for r, label, bval in bridge_rows:
        a[f"A{r}"] = label
        if bval is not None:
            _put(a, f"B{r}", bval, num, True)

    # ---------------------------------------------------------------- Forecast
    f = wb.create_sheet("Forecast")
    _title(f, "Forecast (steps 1-4): INR crore")
    _header(f, 3, "Year", 7)
    f["B3"] = 0
    for i, c in enumerate(FCOLS):
        f[f"{c}3"] = i + 1
    labels = {
        4: "Revenue",
        5: "EBIT",
        6: "NOPAT",
        7: "D&A",
        8: "CapEx",
        9: "Change in NWC",
        10: "FCFF",
    }
    for r, label in labels.items():
        f[f"A{r}"] = label
    f["B4"] = "=Assumptions!B4"
    prev = "B"
    for i, c in enumerate(FCOLS):
        ac = COLS[i]
        f[f"{c}4"] = f"={prev}4*(1+Assumptions!{ac}6)"
        f[f"{c}5"] = f"={c}4*Assumptions!{ac}7"
        f[f"{c}6"] = f"={c}5*(1-Assumptions!$B$8)"
        f[f"{c}7"] = f"={c}4*Assumptions!$B$9"
        f[f"{c}8"] = f"={c}4*Assumptions!$B$10"
        f[f"{c}9"] = f"=Assumptions!$B$11*({c}4-{prev}4)"
        f[f"{c}10"] = f"={c}6+{c}7-{c}8-{c}9"
        prev = c
    for r in range(4, 11):
        for c in ["B", *FCOLS]:
            f[f"{c}{r}"].number_format = "#,##0.0"
    f["A10"].font = BOLD

    # -------------------------------------------------------------------- WACC
    wsh = wb.create_sheet("WACC")
    _title(wsh, "Discount rate (steps 5-6)")
    rows = (
        (3, "Cost of equity = Rf + beta x ERP", "=Assumptions!B14+Assumptions!B15*Assumptions!B16"),
        (4, "After-tax cost of debt", "=Assumptions!B17*(1-Assumptions!B19)"),
        (5, "Equity weight", "=1-Assumptions!B18"),
        (6, "WACC", "=B5*B3+Assumptions!B18*B4"),
    )
    for r, label, formula in rows:
        wsh[f"A{r}"] = label
        _put(wsh, f"B{r}", formula, pct)
    wsh["A6"].font = BOLD
    for i, line in enumerate(res.wacc.inputs_log):
        wsh[f"A{9 + i}"] = f"Input: {line['name']}"
        wsh[f"B{9 + i}"] = line["value"]
        wsh[f"C{9 + i}"] = str(line["source"])
    wsh.column_dimensions["C"].width = 90

    # --------------------------------------------------------------- Valuation
    v = wb.create_sheet("Valuation")
    _title(v, "Valuation (steps 7-11): INR crore")
    v["A3"], v["A4"] = "WACC used", "Terminal growth"
    _put(v, "B3", "=IF(ISNUMBER(Assumptions!B20),Assumptions!B20,WACC!B6)", pct)
    _put(v, "B4", "=Assumptions!B24", pct)
    _header(v, 6, "Year", 6)
    for i, c in enumerate(COLS):
        v[f"{c}6"] = i + 1
        v[f"{c}7"] = f"=Forecast!{FCOLS[i]}10"
        v[f"{c}8"] = f"={c}6-0.5*Assumptions!$B$21"
        v[f"{c}9"] = f"=1/(1+$B$3)^{c}8"
        v[f"{c}10"] = f"={c}7*{c}9"
        v[f"{c}7"].number_format = v[f"{c}10"].number_format = "#,##0.0"
        v[f"{c}9"].number_format = "0.0000"
    for r, label in (
        (7, "FCFF"),
        (8, "Discount exponent"),
        (9, "Discount factor"),
        (10, "Present value of FCFF"),
    ):
        v[f"A{r}"] = label
    lines = (
        (12, "Sum of PV of FCFF", "=SUM(B10:F10)"),
        (13, "Terminal value (perpetuity growth)", "=IF(B3>B4,F7*(1+B4)/(B3-B4),NA())"),
        (14, "PV of terminal value", "=B13*F9"),
        (15, "Enterprise value", "=B12+B14"),
        (16, "Terminal value share of EV", "=B14/B15"),
        (18, "Less: debt", "=-Assumptions!B28"),
        (19, "Less: lease liabilities", "=-Assumptions!B29"),
        (20, "Plus: cash and investments", "=Assumptions!B30"),
        (21, "Less: minority interest", "=-Assumptions!B31"),
        (22, "Equity value", "=B15+B18+B19+B20+B21"),
        (23, "Fair value per share (INR)", "=B22/Assumptions!B32"),
    )
    for r, label, formula in lines:
        v[f"A{r}"] = label
        _put(v, f"B{r}", formula, "#,##0.00")
    v["B16"].number_format = pct
    if br.price:
        v["A24"], v["A25"] = "Market price (INR)", "Upside (+) / downside (-) vs price"
        _put(v, "B24", "=Assumptions!B33", "#,##0.00")
        _put(v, "B25", "=B23/B24-1", pct)
    for r in (15, 22, 23):
        v[f"A{r}"].font = BOLD
    if t.exit_multiple is not None:
        _header(v, 27, "Exit-multiple cross-check", 2)
        for r, label, formula in (
            (28, "EBITDA in year 5", "=Forecast!G5+Forecast!G7"),
            (29, "Terminal value at exit multiple", "=B28*Assumptions!B25"),
            (30, "PV of exit terminal value (year-end)", "=B29/(1+B3)^5"),
            (31, "Enterprise value (exit multiple)", "=B12+B30"),
            (32, "Equity value (exit multiple)", "=B31+B18+B19+B20+B21"),
            (33, "Fair value per share (exit multiple)", "=B32/Assumptions!B32"),
            (34, "Exit multiple implied by perpetuity growth", "=B13/B28"),
        ):
            v[f"A{r}"] = label
            _put(v, f"B{r}", formula, "#,##0.00")
    for c in "BCDEF":
        v.column_dimensions[c].width = 14

    _sensitivity_sheet(wb, inputs)
    _reconciliation_sheet(wb, inputs, res)
    _notes_sheet(wb, inputs, meta)
    return wb


def _sensitivity_sheet(wb: Workbook, inputs: ValuationInputs) -> None:
    s = wb.create_sheet("Sensitivity")
    _title(s, "Sensitivity: fair value per share (INR), live formulas")
    bridge_net = "(Valuation!$B$18+Valuation!$B$19+Valuation!$B$20+Valuation!$B$21)"
    shares = "Assumptions!$B$32"
    adj = "0.5*Assumptions!$B$21"

    # Grid 1: WACC (columns) x terminal growth (rows)
    _header(s, 3, "Grid 1: WACC (across) x terminal growth (down)", 6)
    for j, d in enumerate(WACC_STEPS):
        c = COLS[j]
        _put(s, f"{c}4", f"=Valuation!$B$3+({d})", "0.00%")
    for i, d in enumerate(GROWTH_STEPS):
        r = 5 + i
        _put(s, f"A{r}", f"=Valuation!$B$4+({d})", "0.00%")
        for c in COLS:
            wref, gref = f"{c}$4", f"$A{r}"
            pv = "+".join(f"Valuation!${k}$7/(1+{wref})^(Valuation!${k}$6-{adj})" for k in COLS)
            tv = f"Valuation!$F$7*(1+{gref})/({wref}-{gref})/(1+{wref})^(Valuation!$F$6-{adj})"
            _put(
                s,
                f"{c}{r}",
                f"=IF({gref}<{wref},({pv}+{tv}+{bridge_net})/{shares},NA())",
                "#,##0.00",
            )

    # Helper block: revenue path for each growth shift
    _header(s, 24, "Helper: revenue path for each revenue-growth shift (feeds Grid 2)", 6)
    s["A25"] = "Revenue-growth shift"
    for j, d in enumerate(OPERATING_STEPS):
        c = COLS[j]
        _put(s, f"{c}25", d, "0.0%", True)
        s[f"{c}26"] = "=Assumptions!$B$4"
        for k in range(5):
            r = 27 + k
            s[f"{c}{r}"] = f"={c}{r - 1}*(1+Assumptions!{COLS[k]}$6+{c}$25)"
    for k in range(6):
        s[f"A{26 + k}"] = f"Revenue year {k}"
    for r in range(26, 32):
        for c in COLS:
            s[f"{c}{r}"].number_format = "#,##0.0"

    # Grid 2: revenue-growth shift (columns) x EBIT-margin shift (rows)
    _header(
        s,
        13,
        "Grid 2: revenue-growth shift (across) x EBIT-margin shift (down); WACC and terminal growth as in Valuation",
        6,
    )
    for j in range(len(OPERATING_STEPS)):
        _put(s, f"{COLS[j]}14", f"={COLS[j]}25", "0.0%")
    for i, d in enumerate(OPERATING_STEPS):
        r = 15 + i
        _put(s, f"A{r}", d, "0.0%", True)
        for c in COLS:
            fc = []
            for k in range(1, 6):
                rev, prev = f"{c}${26 + k}", f"{c}${25 + k}"
                fc.append(
                    f"({rev}*((Assumptions!{COLS[k - 1]}$7+$A{r})*(1-Assumptions!$B$8)"
                    f"+Assumptions!$B$9-Assumptions!$B$10)-Assumptions!$B$11*({rev}-{prev}))"
                )
            w, g = "Valuation!$B$3", "Valuation!$B$4"
            pv = "+".join(f"{x}/(1+{w})^({k}-{adj})" for k, x in enumerate(fc, start=1))
            tv = f"{fc[-1]}*(1+{g})/({w}-{g})/(1+{w})^(5-{adj})"
            _put(s, f"{c}{r}", f"=IF({g}<{w},({pv}+{tv}+{bridge_net})/{shares},NA())", "#,##0.00")


def _reconciliation_sheet(wb: Workbook, inputs: ValuationInputs, r: ValuationResult) -> None:
    rec = wb.create_sheet("Reconciliation")
    _title(rec, "Reconciliation: Python engine vs this workbook's formulas")
    for c, h in zip(
        "ABCDE", ("Item", "Python", "Excel formula", "Difference", "Check"), strict=True
    ):
        rec[f"{c}3"] = h
        rec[f"{c}3"].font = BOLD
    items: list[tuple[str, float, str]] = [("WACC used", r.wacc_used, "=Valuation!B3")]
    for i in range(5):
        items.append((f"FCFF year {i + 1}", r.forecast.fcff[i], f"=Valuation!{COLS[i]}7"))
    items += [
        ("Sum of PV of FCFF", r.sum_pv_fcff, "=Valuation!B12"),
        ("Terminal value", r.terminal_value, "=Valuation!B13"),
        ("PV of terminal value", r.pv_terminal_value, "=Valuation!B14"),
        ("Enterprise value", r.enterprise_value, "=Valuation!B15"),
        ("Equity value", r.equity_value, "=Valuation!B22"),
        ("Fair value per share", r.fair_value_per_share, "=Valuation!B23"),
    ]
    if r.exit_cross_check and r.exit_cross_check.get("fair_value_per_share") is not None:
        items.append(
            (
                "Fair value per share (exit multiple)",
                float(r.exit_cross_check["fair_value_per_share"] or 0.0),
                "=Valuation!B33",
            )
        )
    for idx, (label, py, formula) in enumerate(items):
        row = 4 + idx
        rec[f"A{row}"] = label
        rec[f"B{row}"] = py
        rec[f"C{row}"] = formula
        rec[f"D{row}"] = f"=C{row}-B{row}"
        rec[f"E{row}"] = f'=IF(ABS(D{row})<=0.000001*MAX(1,ABS(B{row})),"OK","CHECK")'
        for c in "BCD":
            rec[f"{c}{row}"].number_format = "#,##0.0000"
    last = 3 + len(items)
    rec[f"A{last + 2}"] = "Overall"
    rec[f"A{last + 2}"].font = BOLD
    rec[f"B{last + 2}"] = f'=IF(COUNTIF(E4:E{last},"CHECK")=0,"ALL MATCH","MISMATCH")'
    rec.column_dimensions["B"].width = rec.column_dimensions["C"].width = 20
    rec["A2"] = "Python values are static numbers from the engine run that produced this file."
    rec["A2"].alignment = Alignment(wrap_text=False)


def _notes_sheet(wb: Workbook, inputs: ValuationInputs, meta: dict[str, Any]) -> None:
    n = wb.create_sheet("Notes")
    _title(n, "Notes and sources")
    lines = [
        DISCLAIMER,
        f"Data source: {meta.get('source', 'n/a')}; fetched {meta.get('fetched_at', 'n/a')}.",
        "Units: INR crore unless stated; rates are decimals; shares in crore.",
        "Method: FCFF DCF, perpetuity-growth terminal value, exit-multiple cross-check.",
        "Lease liabilities are treated as debt in the bridge (EBIT is before lease interest).",
        "Discounting: end-of-year by default; set Assumptions!B21 = 1 for mid-year.",
        "Terminal growth must stay below WACC; the formulas return #N/A otherwise.",
        "Blue cells are inputs; everything else is a formula.",
        "",
        "Sources of inputs:",
    ]
    for k, src in (meta.get("sources") or {}).items():
        lines.append(f"  {k}: {src}")
    for i, text in enumerate(lines, start=3):
        n[f"A{i}"] = text
    n.column_dimensions["A"].width = 120


def export_workbook_bytes(
    inputs: ValuationInputs,
    result: ValuationResult | None = None,
    meta: dict[str, Any] | None = None,
) -> bytes:
    """The workbook as .xlsx bytes (what the API returns)."""
    buf = io.BytesIO()
    build_workbook(inputs, result, meta).save(buf)
    return buf.getvalue()
