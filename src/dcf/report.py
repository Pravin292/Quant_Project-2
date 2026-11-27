"""Two-page PDF valuation report (F25): summary, assumptions, sensitivity, caveats."""

from __future__ import annotations

from typing import Any

from dcf.pdf import Pdf
from dcf.scenarios import ScenarioSpec, run_scenarios
from dcf.sensitivity import wacc_growth_grid
from dcf.valuation import ValuationInputs, run_valuation

LEFT, RIGHT = 48.0, 547.0
DISCLAIMER = (
    "Educational model. Outputs are estimates based on stated assumptions and public data, "
    "not investment, tax or financial advice."
)
LIMITATIONS = [
    "Forecasts are uncertain and cover only five years; the terminal value is usually most of the result.",
    "Beta and the equity risk premium are estimates that differ between sources.",
    "Currency effects are not modelled separately.",
    "Lease liabilities are treated as debt in the bridge.",
    "Statement data can contain errors; compare with the annual report.",
]


def _money(v: float | None) -> str:
    return "n/a" if v is None else f"{v:,.0f}"


def _pct(v: float | None, digits: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{digits}f}%"


def heatmap(pdf: Pdf, y: float, grid: dict[str, Any], price: float | None) -> float:
    """WACC x terminal growth table; darker grey the further below the price."""
    left, first, cell, height = LEFT, 70.0, 85.0, 18.0
    pdf.text(left, y, "Growth / WACC", 8, bold=True)
    for j, w in enumerate(grid["columns"]):
        pdf.text(left + first + j * cell + cell / 2, y, _pct(w), 8, bold=True, align="center")
    y += 6
    for i, g in enumerate(grid["rows"]):
        pdf.text(left, y + 12, _pct(g), 8, bold=True)
        for j, value in enumerate(grid["values"][i]):
            x = left + first + j * cell
            gap = 0.0 if value is None or not price else min(max(1 - value / price, 0) / 0.5, 1)
            pdf.rect(x + 1, y + 1, cell - 2, height - 2, 0.97 - 0.22 * gap)
            base = [i, j] == list(grid["centre"])
            pdf.text(x + cell / 2, y + 12, _money(value), 8.5, bold=base, align="center")
        y += height
    return y + 8


def header(pdf: Pdf, title: str, subtitle: str) -> float:
    pdf.text(LEFT, 58, title, 17, bold=True)
    pdf.text(LEFT, 74, subtitle, 8.5, grey=0.42)
    pdf.line(LEFT, 84, RIGHT, 84, grey=0.1, width=1)
    pdf.text(LEFT, 812, DISCLAIMER, 7, grey=0.45)
    return 106


def build_report(
    inputs: ValuationInputs,
    specs: dict[str, ScenarioSpec],
    meta: dict[str, Any],
    probabilities: dict[str, float] | None = None,
) -> bytes:
    """The report as PDF bytes. ``meta`` carries name, ticker, source, fetched_at and sources."""
    r = run_valuation(inputs)
    sc = run_scenarios(inputs, specs, probabilities)
    op = inputs.operating
    name = str(meta.get("name") or "Custom model")
    subtitle = (
        f"{meta.get('ticker') or 'uploaded data'} | statements: {meta.get('source', 'n/a')}, "
        f"fetched {str(meta.get('fetched_at', 'n/a'))[:10]} | money in INR crore unless stated"
    )
    pdf = Pdf()
    y = header(pdf, f"{name}: DCF valuation report", subtitle)

    pdf.text(LEFT, y, "Model fair value per share", 8.5, grey=0.42)
    pdf.text(LEFT + 190, y, "Market price", 8.5, grey=0.42)
    pdf.text(LEFT + 330, y, "Model value vs price", 8.5, grey=0.42)
    y += 22
    pdf.text(LEFT, y, f"INR {_money(r.fair_value_per_share)}", 20, bold=True)
    pdf.text(LEFT + 190, y, f"INR {_money(r.price)}" if r.price else "n/a", 20, bold=True)
    pdf.text(LEFT + 330, y, _pct(r.upside), 20, bold=True)
    y += 30

    pdf.text(LEFT, y, "Forecast", 11, bold=True)
    y += 16
    years = [f"Year {i + 1}" for i in range(op.years)]
    f = r.forecast
    width = (RIGHT - LEFT - 130) / op.years
    y = pdf.table(
        LEFT,
        y,
        [130.0] + [width] * op.years,
        [
            ["", *years],
            ["Revenue growth", *[_pct(v) for v in op.revenue_growth]],
            ["EBIT margin", *[_pct(v) for v in op.ebit_margin]],
            ["Revenue", *map(_money, f.revenue)],
            ["EBIT", *map(_money, f.ebit)],
            ["NOPAT", *map(_money, f.nopat)],
            ["Free cash flow", *map(_money, f.fcff)],
            ["Present value", *map(_money, r.pv_fcff)],
        ],
    )
    y += 12

    top = y
    pdf.text(LEFT, y, "Assumptions", 11, bold=True)
    pdf.text(LEFT + 260, y, "Value bridge", 11, bold=True)
    y = pdf.table(
        LEFT,
        top + 16,
        [150.0, 75.0],
        [
            ["Input", "Value"],
            ["Tax rate", _pct(op.tax_rate)],
            ["CapEx % of revenue", _pct(op.capex_pct, 2)],
            ["D&A % of revenue", _pct(op.da_pct, 2)],
            ["Working capital % of revenue", _pct(op.nwc_pct)],
            ["Risk-free rate", _pct(inputs.wacc.risk_free, 2)],
            ["Beta", f"{inputs.wacc.beta:.2f}"],
            ["Equity risk premium", _pct(inputs.wacc.equity_risk_premium, 2)],
            ["WACC", _pct(r.wacc_used, 2)],
            ["Terminal growth", _pct(inputs.terminal.growth, 2)],
            ["Discounting", "mid-year" if inputs.mid_year else "end of year"],
        ],
    )
    b = r.bridge
    bottom = pdf.table(
        LEFT + 260,
        top + 16,
        [150.0, 89.0],
        [
            ["Step", "INR crore"],
            ["PV of forecast cash flows", _money(r.sum_pv_fcff)],
            ["PV of terminal value", _money(r.pv_terminal_value)],
            ["Enterprise value", _money(r.enterprise_value)],
            ["Less debt", _money(-b["less_debt"])],
            ["Less leases", _money(-b["less_leases"])],
            ["Plus cash and investments", _money(b["plus_cash_and_investments"])],
            ["Less minority interest", _money(-b["less_minority_interest"])],
            ["Equity value", _money(r.equity_value)],
            ["Diluted shares (crore)", f"{inputs.bridge.diluted_shares:,.2f}"],
            ["Terminal share of EV", _pct(r.terminal_value_share, 0)],
        ],
    )
    y = max(y, bottom) + 12

    pdf.text(LEFT, y, "Scenarios", 11, bold=True)
    rows = [["Case", "Per share (INR)", "vs price", "Probability"]]
    for key in ("bear", "base", "bull"):
        s = sc["scenarios"][key]
        rows.append(
            [
                key.title(),
                _money(s["fair_value_per_share"]),
                _pct(s["upside"]),
                _pct(s["probability"], 0),
            ]
        )
    rows.append(
        ["Weighted", _money(sc["expected_fair_value"]), _pct(sc["expected_upside"]), "100%"]
    )
    pdf.table(LEFT, y + 16, [150.0, 110.0, 110.0, 110.0], rows)

    pdf.add_page()
    y = header(pdf, "Sensitivity, checks and caveats", subtitle)
    pdf.text(LEFT, y, "Fair value per share (INR): WACC x terminal growth", 11, bold=True)
    y = heatmap(pdf, y + 20, wacc_growth_grid(inputs), r.price)
    pdf.text(LEFT, y, "Bold is the current case; darker cells are further below the price.", 7.5)
    y += 24
    pdf.text(LEFT, y, "Warnings raised by the model", 11, bold=True)
    y += 16
    for warning in [w.message for w in r.warnings] or ["None."]:
        y = pdf.paragraph(LEFT, y, f"- {warning}", RIGHT - LEFT) + 2
    y += 12
    pdf.text(LEFT, y, "Limitations", 11, bold=True)
    y += 16
    for item in LIMITATIONS:
        y = pdf.paragraph(LEFT, y, f"- {item}", RIGHT - LEFT) + 2
    y += 12
    pdf.text(LEFT, y, "Sources", 11, bold=True)
    y += 15
    for key, source in dict(meta.get("sources") or {}).items():
        if y > 780:
            break
        y = pdf.paragraph(LEFT, y, f"{key}: {source}", RIGHT - LEFT, size=7.5)
    return pdf.to_bytes()
