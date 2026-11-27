import type { Defaults } from "@/lib/types";
import { Card, Table } from "./ui";

const STEPS: [string, string][] = [
  ["Revenue", "Revenue(t) = Revenue(t−1) × (1 + growth(t))"],
  ["Operating profit", "EBIT(t) = Revenue(t) × EBIT margin(t)"],
  ["After tax", "NOPAT(t) = EBIT(t) × (1 − tax rate)"],
  ["Free cash flow", "FCFF(t) = NOPAT(t) + D&A(t) − CapEx(t) − change in working capital(t)"],
  ["Cost of equity", "risk-free rate + beta × equity risk premium"],
  ["WACC", "equity weight × cost of equity + debt weight × cost of debt × (1 − tax rate)"],
  ["Terminal value", "FCFF(5) × (1 + g) ÷ (WACC − g), refused when g is not below WACC"],
  ["Present value", "cash flow ÷ (1 + WACC)^t; mid-year discounting uses t − 0.5"],
  ["Enterprise value", "sum of the present values + present value of the terminal value"],
  ["Equity value", "enterprise value − debt − lease liabilities + cash and investments − minority interest"],
  ["Fair value per share", "equity value ÷ diluted shares"],
  ["Upside", "fair value ÷ market price − 1"],
];

const CHECKS: [string, string][] = [
  ["Reverse DCF", "Solves by bisection for the constant revenue growth that makes the model value equal the price."],
  ["Beta", "Least-squares slope of 5 years of weekly returns against the Nifty 50, then 2/3 × raw + 1/3."],
  ["Value creation (ROIC)", "Growth needs reinvestment of g ÷ ROIC of after-tax profit. A forecast that reinvests less is flagged."],
  ["Exit multiple", "Terminal value as year-5 EBITDA × the median peer EV/EBITDA, shown beside the headline."],
  ["Scenarios", "Bear and bull move growth and margin by half the historical spread (between 1.5 and 5 points) and terminal growth by 0.5 points."],
  ["Monte Carlo", "10,000 runs with a fixed seed. Growth, margin and terminal growth are triangular around the base; WACC is normal, with spread from beta's standard error."],
  ["Peers", "P/E and EV/EBITDA of Infosys, Wipro, HCLTech and Tech Mahindra, applied to the selected company."],
];

const LIMITS = [
  "A forecast is uncertain; five years is a short horizon and the terminal value is usually most of the result.",
  "Beta and the equity risk premium are estimates that differ between sources.",
  "Currency effects (dollar earnings, rupee reporting) are not modelled separately.",
  "Lease liabilities are treated as debt, so operating profit is before lease interest.",
  "Statements come from Yahoo Finance or an uploaded Screener file and can contain errors.",
  "Not suitable for banks or insurers.",
  "Educational model. Not investment, tax or financial advice.",
];

/** F24: every formula, source and limitation in plain language. */
export default function MethodologyTab({ defaults }: { defaults: Defaults }) {
  return (
    <div className="space-y-4">
      <Card title="How a value per share is built">
        <p className="mb-3 text-sm">
          A company is worth the cash it can pay its lenders and owners in future, counted in today&apos;s money.
          The model forecasts five years of that cash, adds a value for all later years, and subtracts what is owed.
        </p>
        <Table prose head={["Step", "Formula"]} rows={STEPS} />
      </Card>
      <Card title="Checks and extra methods">
        <Table prose head={["Method", "What it does"]} rows={CHECKS} />
      </Card>
      <Card title={`Where each default comes from (${defaults.company.name})`}>
        <Table prose head={["Input", "Source"]} rows={Object.entries(defaults.sources).map(([k, s]) => [k.replace("wacc.", "").replaceAll("_", " "), s])} />
      </Card>
      <Card title="Limitations">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {LIMITS.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
