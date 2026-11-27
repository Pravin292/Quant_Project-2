"use client";

import dynamic from "next/dynamic";

import { useApi } from "@/lib/api";
import { num, pct, rupees } from "@/lib/format";
import type { Assumptions, MonteCarlo } from "@/lib/types";
import { SeriesChart } from "./charts";
import { Card, Notice, Skeleton, Stat, Table } from "./ui";

const Histogram3D = dynamic(() => import("./three/Histogram"), { ssr: false, loading: () => <Skeleton rows={4} /> });

export default function MonteCarloTab({ assumptions }: { assumptions: Assumptions }) {
  const query = useApi<MonteCarlo>("/api/montecarlo", { assumptions });
  if (query.error) return <Notice kind="error">{query.error}</Notice>;
  const m = query.data;
  if (!m) return <Skeleton />;
  const bins = m.histogram.counts.map((count, i) => ({
    from: m.histogram.edges[i],
    to: m.histogram.edges[i + 1],
    count,
  }));
  return (
    <div className={`space-y-4 ${query.loading ? "opacity-60" : ""}`}>
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Median fair value" value={rupees(m.percentiles.p50)} sub={`Base case ${rupees(m.base_fair_value)}`} />
        <Stat label="90% of runs fall between" value={`${rupees(m.percentiles.p5)} to ${rupees(m.percentiles.p95)}`} sub={`Standard deviation ${rupees(m.std)}`} />
        <Stat label="Runs above the market price" value={pct(m.probability_above_price)} sub={`Price ${rupees(m.price)}`} />
      </div>
      <Card title={`Distribution of ${num(m.runs)} simulated values`} note={m.caveat}>
        <Histogram3D bins={bins} price={m.price} median={m.percentiles.p50} />
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Histogram (flat view)">
          <SeriesChart
            kind="bar"
            data={bins.map((b) => ({ value: rupees((b.from + b.to) / 2), count: b.count }))}
            x="value"
            series={[{ key: "count", label: "Runs" }]}
            format={(v) => num(v)}
          />
        </Card>
        <Card title="Percentiles and input ranges" note={`Fixed random seed ${m.seed}; ${num(m.discarded_draws)} surplus or invalid draws discarded.`}>
          <Table
            head={["Percentile", "Per share", "vs price"]}
            rows={(["p5", "p25", "p50", "p75", "p95"] as const).map((p) => [
              `${p.slice(1)}th`,
              rupees(m.percentiles[p]),
              m.price ? pct(m.percentiles[p] / m.price - 1) : "n/a",
            ])}
          />
          <div className="mt-4">
            <Table
              head={["Random input", "Spread around the current case"]}
              rows={[
                ["Revenue growth", `±${pct(m.ranges.growth_swing, 2)}`],
                ["EBIT margin", `±${pct(m.ranges.margin_swing, 2)}`],
                ["WACC (standard deviation)", pct(m.ranges.wacc_sd, 2)],
                ["Terminal growth", `±${pct(m.ranges.terminal_growth_swing, 2)}`],
              ]}
            />
          </div>
        </Card>
      </div>
    </div>
  );
}
