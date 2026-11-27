"use client";

import { useApi } from "@/lib/api";
import { pct, rupees } from "@/lib/format";
import type { Assumptions, Grid, Sensitivity, Tornado } from "@/lib/types";
import { TornadoChart } from "./charts";
import { Card, Notice, Skeleton, Table } from "./ui";

/** Blue above the market price, orange below, stronger the further away (full at 50%). */
function shade(value: number | null, price: number | null): string | undefined {
  if (value === null || !price) return undefined;
  const gap = value / price - 1;
  const strength = Math.round(Math.min(Math.abs(gap) / 0.5, 1) * 55);
  return `color-mix(in srgb, var(${gap >= 0 ? "--series-1" : "--series-2"}) ${strength}%, var(--surface))`;
}

function Heatmap({ grid, price }: { grid: Grid; price: number | null }) {
  const [centreRow, centreCol] = grid.centre;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-0.5 text-sm">
        <caption className="pb-2 text-left text-xs text-(--ink-2)">
          Columns: {grid.column_label}. Rows: {grid.row_label}.
        </caption>
        <thead>
          <tr>
            <td />
            {grid.columns.map((c) => (
              <th key={c} scope="col" className="p-1 font-medium">{pct(c)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {grid.rows.map((r, i) => (
            <tr key={r}>
              <th scope="row" className="p-1 text-right font-medium">{pct(r)}</th>
              {grid.values[i].map((value, j) => {
                const base = i === centreRow && j === centreCol;
                return (
                  <td
                    key={j}
                    className={`rounded p-2 text-center ${base ? "font-bold outline-2 -outline-offset-2 outline-(--ink)" : ""}`}
                    style={{ background: shade(value, price) }}
                    title={`${grid.column_label} ${pct(grid.columns[j])}, ${grid.row_label} ${pct(r)}: ${rupees(value)}${value !== null && price ? ` (${pct(value / price - 1)} vs price)` : ""}`}
                  >
                    {value === null ? "—" : rupees(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SensitivityTab({ assumptions }: { assumptions: Assumptions }) {
  const grids = useApi<Sensitivity>("/api/sensitivity", assumptions);
  const tornado = useApi<Tornado>("/api/tornado", { assumptions });
  const price = assumptions.bridge.price;
  const error = grids.error ?? tornado.error;
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!grids.data || !tornado.data) return <Skeleton />;
  const base = tornado.data.base_fair_value;
  const note = `Fair value per share. Blue is above the market price of ${rupees(price)}, orange below. The outlined cell is the current case; a dash means growth is not below WACC.`;
  return (
    <div className={`space-y-4 ${grids.loading || tornado.loading ? "opacity-60" : ""}`}>
      <div className="grid gap-4 2xl:grid-cols-2">
        <Card title="WACC × terminal growth" note={note}>
          <Heatmap grid={grids.data.wacc_growth} price={price} />
        </Card>
        <Card title="Revenue growth × EBIT margin" note={note}>
          <Heatmap grid={grids.data.growth_margin} price={price} />
        </Card>
      </div>
      <Card
        title="Tornado: what moves the value most"
        note={`Change in fair value per share from ${rupees(base)} when one assumption moves by one percentage point.`}
      >
        <TornadoChart
          data={tornado.data.rows.map((r) => ({
            name: r.name.replace(" (all years)", "").replace(" % of revenue", " %"),
            lower: (r.fair_value_low_input ?? base) - base,
            higher: (r.fair_value_high_input ?? base) - base,
          }))}
          format={(x) => rupees(x)}
        />
        <Table
          head={["Assumption", "1 point lower", "1 point higher", "Range"]}
          rows={tornado.data.rows.map((r) => [
            r.name,
            rupees(r.fair_value_low_input),
            rupees(r.fair_value_high_input),
            rupees(r.swing),
          ])}
        />
      </Card>
    </div>
  );
}
