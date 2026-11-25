"""Print the default TCS valuation from the committed snapshot (milestone checks)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dcf import defaults, historical, loader, valuation  # noqa: E402


def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "TCS.NS"
    snap = loader.load_snapshot(ticker, ROOT / "data" / "snapshots")
    bundle = defaults.build_defaults(snap, peers_dir=ROOT / "data" / "snapshots")
    r = valuation.run_valuation(bundle.inputs)
    print(historical.format_history(bundle.historical), "\n")
    op = bundle.inputs.operating
    print("growth", [f"{g:.2%}" for g in op.revenue_growth], "margin", f"{op.ebit_margin[0]:.2%}")
    print("FCFF", [round(x) for x in r.forecast.fcff])
    print(
        f"WACC {r.wacc_used:.2%}  ke {r.wacc.cost_of_equity:.2%}  g {bundle.inputs.terminal.growth:.2%}"
    )
    print(
        f"EV {r.enterprise_value:,.0f}  equity {r.equity_value:,.0f}  TV share {r.terminal_value_share:.0%}"
    )
    print(f"fair value {r.fair_value_per_share:,.0f}  price {r.price}  upside {r.upside:.1%}")
    print("exit cross-check", r.exit_cross_check)
    print("value-driver", r.value_driver_cross_check)
    for w in r.warnings:
        print("WARN", w.code, "-", w.message)
    rev = valuation.reverse_dcf(bundle.inputs)
    print(rev.message)


if __name__ == "__main__":
    main()
