"use client";

import { num, pct } from "@/lib/format";
import type { Assumptions, Valuation } from "@/lib/types";
import { SeriesChart } from "./charts";
import { Card, Table } from "./ui";

function Cell({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <input
      type="number"
      step="0.1"
      aria-label={label}
      className="w-20 rounded border border-(--line) bg-(--surface) p-1 text-right"
      value={Math.round(value * 10000) / 100}
      onChange={(e) => {
        const next = e.target.valueAsNumber;
        if (Number.isFinite(next)) onChange(next / 100);
      }}
    />
  );
}

export default function ForecastTab({
  assumptions,
  valuation: v,
  onChange,
}: {
  assumptions: Assumptions; // base case: what the editable cells change
  valuation: Valuation; // active scenario
  onChange: (next: Assumptions) => void;
}) {
  const op = assumptions.operating;
  const f = v.forecast;
  const labels = f.fcff.map((_, i) => `Year ${i + 1}`);
  const setOp = (patch: Partial<Assumptions["operating"]>) =>
    onChange({ ...assumptions, operating: { ...op, ...patch } });
  const perYear = (key: "revenue_growth" | "ebit_margin", name: string) =>
    op[key].map((value, i) => (
      <Cell
        key={i}
        label={`${name}, year ${i + 1}, percent`}
        value={value}
        onChange={(n) => setOp({ [key]: op[key].map((old, j) => (j === i ? n : old)) })}
      />
    ));
  const flat = (key: "tax_rate" | "da_pct" | "capex_pct" | "nwc_pct", label: string) => (
    <label className="text-xs">
      {label} (%)
      <br />
      <Cell label={`${label}, percent`} value={op[key]} onChange={(n) => setOp({ [key]: n })} />
    </label>
  );
  const line = (label: string, values: number[], digits = 0) => [label, ...values.map((x) => num(x, digits))];

  return (
    <div className="space-y-4">
      <Card title="Free cash flow to the firm (₹ crore)">
        <SeriesChart
          kind="bar"
          data={labels.map((label, i) => ({ label, fcff: f.fcff[i], pv: v.pv_fcff[i] }))}
          x="label"
          series={[{ key: "fcff", label: "FCFF" }, { key: "pv", label: "Present value" }]}
          format={(x) => num(x)}
        />
      </Card>
      <Card title="Edit the assumptions (base case)" note="Values the server rejects show a message at the top of the page.">
        <Table
          head={["Per year (%)", ...labels]}
          rows={[
            ["Revenue growth", ...perYear("revenue_growth", "Revenue growth")],
            ["EBIT margin", ...perYear("ebit_margin", "EBIT margin")],
          ]}
        />
        <div className="mt-3 flex flex-wrap gap-4">
          {flat("tax_rate", "Tax rate")}
          {flat("da_pct", "D&A % revenue")}
          {flat("capex_pct", "CapEx % revenue")}
          {flat("nwc_pct", "Working capital % revenue")}
        </div>
      </Card>
      <Card title="Five-year forecast, active scenario (₹ crore)" note={`Year 0 revenue: ₹${num(f.base_revenue)} crore. Discounted at a WACC of ${pct(v.wacc_used, 2)}.`}>
        <Table
          head={["Line", ...labels]}
          rows={[
            line("Revenue", f.revenue),
            line("EBIT", f.ebit),
            line("NOPAT", f.nopat),
            line("+ D&A", f.da),
            line("− CapEx", f.capex),
            line("− Change in working capital", f.delta_nwc),
            line("FCFF", f.fcff),
            line("Discount factor", v.discount_factors, 4),
            line("Present value", v.pv_fcff),
          ]}
        />
      </Card>
    </div>
  );
}
