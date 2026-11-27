"""Build docs/case_study.pdf (2 pages, M16) from the latest committed snapshot.

Every number is computed by the engine when the script runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dcf import defaults, loader, montecarlo, peers, scenarios, sensitivity, valuation  # noqa: E402
from dcf.config import load_config  # noqa: E402
from dcf.pdf import Pdf  # noqa: E402
from dcf.report import LEFT, RIGHT, header, heatmap  # noqa: E402

WIDTH = RIGHT - LEFT


def pct(v: float, digits: int = 1) -> str:
    return f"{v * 100:.{digits}f}%"


def section(pdf: Pdf, y: float, title: str, body: str) -> float:
    pdf.text(LEFT, y, title, 11, bold=True)
    return pdf.paragraph(LEFT, y + 15, body, WIDTH) + 9


def main() -> None:
    cfg = load_config()
    folder = ROOT / cfg["paths"]["snapshots_dir"]
    snap = loader.load_snapshot(cfg["company"]["ticker"], folder)
    others = peers.load_peer_snapshots(folder, cfg["peers"])
    bundle = defaults.build_defaults(snap, others)
    i, h = bundle.inputs, bundle.historical
    r = valuation.run_valuation(i)
    specs = scenarios.build_specs(h)
    sc = scenarios.run_scenarios(i, specs)
    mc = montecarlo.run_monte_carlo(
        i,
        montecarlo.settings_from_context(
            specs["bull"].growth_shift,
            specs["bull"].margin_shift,
            bundle.beta.std_error,
            i.wacc.equity_risk_premium,
        ),
    )
    pc = peers.peer_cross_check(snap, others, r.fair_value_per_share)
    reverse = valuation.reverse_dcf(i)
    growth = h.summary["revenue_growth"]
    margin = h.summary["ebit_margin"]
    assert r.price and r.upside is not None
    subtitle = (
        f"Case study | statements fetched {snap['fetched_at'][:10]}, price of "
        f"{snap['market']['price_date']} | money in INR"
    )

    pdf = Pdf()
    y = header(pdf, "Valuing TCS with a discounted cash flow model", subtitle)
    y = section(
        pdf,
        y,
        "What a DCF does",
        "A company is worth the cash it can pay its lenders and owners in future, counted in today's "
        "money. I forecast five years of free cash flow, add a value for all later years, discount "
        "both at the weighted cost of capital, then subtract what is owed and divide by the shares.",
    )
    pdf.text(LEFT, y, "Assumptions and why", 11, bold=True)
    rows = [
        ["Assumption", "Value", "Basis"],
        [
            "Revenue growth",
            f"{pct(i.operating.revenue_growth[0])} to {pct(i.operating.revenue_growth[-1])}",
            f"mean {pct(growth['mean'] or 0)} fading to terminal",
        ],
        [
            "EBIT margin",
            pct(i.operating.ebit_margin[0]),
            f"history {pct(margin['min'] or 0)} to {pct(margin['max'] or 0)}",
        ],
        ["Tax rate", pct(i.operating.tax_rate), "latest effective rate"],
        [
            "Beta",
            f"{i.wacc.beta:.2f}",
            f"regression, 95% range {bundle.beta.ci95_low:.2f}-{bundle.beta.ci95_high:.2f}",
        ],
        [
            "Cost of equity",
            pct(r.wacc.cost_of_equity, 2),
            f"{pct(i.wacc.risk_free, 2)} + beta x {pct(i.wacc.equity_risk_premium, 2)}",
        ],
        ["WACC", pct(r.wacc_used, 2), "debt is only lease liabilities"],
        ["Terminal growth", pct(i.terminal.growth, 2), "capped at the risk-free rate"],
    ]
    y = pdf.table(LEFT, y + 16, [120.0, 110.0, WIDTH - 230.0], rows) + 6
    y = section(
        pdf,
        y,
        "Result",
        f"Model value INR {r.fair_value_per_share:,.0f} per share against a price of INR "
        f"{r.price:,.0f} ({pct(r.upside)}). Bear / base / bull: "
        + " / ".join(
            f"{sc['scenarios'][n]['fair_value_per_share']:,.0f}" for n in ("bear", "base", "bull")
        )
        + f". The terminal value is {pct(r.terminal_value_share, 0)} of enterprise value. "
        + reverse.message.replace("The price of", "The price of INR"),
    )
    pdf.text(LEFT, y, "Value per share (INR): WACC x terminal growth", 11, bold=True)
    heatmap(pdf, y + 20, sensitivity.wacc_growth_grid(i), r.price)

    pdf.add_page()
    y = header(pdf, "Range, cross-check and limits", subtitle)
    p = mc["percentiles"]
    y = section(
        pdf,
        y,
        f"Monte Carlo ({mc['runs']:,} runs, fixed seed)",
        f"5th to 95th percentile INR {p['p5']:,.0f} to {p['p95']:,.0f}, median {p['p50']:,.0f}. "
        f"Share of runs above the price: {pct(mc['probability_above_price'] or 0, 2)}. The range "
        "reflects only the input ranges chosen, not real-world odds.",
    )
    counts, edges = mc["histogram"]["counts"], mc["histogram"]["edges"]
    chart_h, bar_w = 120.0, WIDTH / len(counts)
    for k, count in enumerate(counts):
        height = chart_h * count / max(counts)
        pdf.rect(LEFT + k * bar_w, y + chart_h - height, bar_w - 1.5, height, 0.35)
    pdf.line(LEFT, y + chart_h, RIGHT, y + chart_h, grey=0.1)
    pdf.text(LEFT, y + chart_h + 12, f"INR {edges[0]:,.0f}", 8)
    pdf.text(RIGHT, y + chart_h + 12, f"INR {edges[-1]:,.0f}", 8, align="right")
    y += chart_h + 34

    pdf.text(LEFT, y, "Peer cross-check", 11, bold=True)
    table = [["Company", "P/E", "EV/EBITDA", "Price date"]]
    for m in [pc["subject"], *pc["peers"]]:
        table.append([m["name"], f"{m['pe']:.1f}x", f"{m['ev_ebitda']:.1f}x", str(m["price_date"])])
    y = pdf.table(LEFT, y + 16, [220.0, 80.0, 90.0, WIDTH - 390.0], table) + 4
    y = section(
        pdf,
        y,
        "",
        f"At the peer median P/E of {pc['median_pe']:.1f}x a share would be INR "
        f"{pc['value_per_share_at_median_pe']:,.0f}; at the median EV/EBITDA of "
        f"{pc['median_ev_ebitda']:.1f}x, INR {pc['value_per_share_at_median_ev_ebitda']:,.0f}. Both "
        "are above the DCF value, so the market prices this group on more optimistic assumptions "
        "(or a lower discount rate) than the model uses.",
    )
    y = section(
        pdf,
        y,
        "Validation",
        "A hand-checkable example reproduces to INR 26.8 per share; an exported Excel model with live "
        "formulas matches Python when recalculated by an independent formula engine; property-based "
        "tests check that a higher discount rate never raises value.",
    )
    y = section(
        pdf,
        y,
        "Limitations",
        "Five-year forecast; most value sits in the terminal value; beta and the equity risk premium "
        "are estimates; currency effects are not modelled; leases are treated as debt, which leaves "
        "lease additions outside CapEx and triggers the reinvestment warning; statements come from "
        "Yahoo Finance and some lines are not yet ticked against the annual report.",
    )
    section(
        pdf,
        y,
        "What I would improve next",
        "Add lease additions to reinvestment, use a longer history, model currency exposure, and read "
        "assumptions from the annual report with page citations.",
    )
    out = ROOT / "docs" / "case_study.pdf"
    out.write_bytes(pdf.to_bytes())
    print(f"wrote {out.relative_to(ROOT)} ({len(pdf.pages)} pages)")


if __name__ == "__main__":
    main()
