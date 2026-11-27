"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLOURS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
const axis = { stroke: "var(--line)", tick: { fill: "var(--ink-2)", fontSize: 11 } };
const tooltip = {
  contentStyle: { background: "var(--surface)", border: "1px solid var(--line)", fontSize: 12 },
  itemStyle: { color: "var(--ink)" },
  labelStyle: { color: "var(--ink)" },
  cursor: { fill: "var(--line)", opacity: 0.3 },
};
const legend = {
  formatter: (value: string) => <span style={{ color: "var(--ink)", fontSize: 12 }}>{value}</span>,
};

export interface SeriesDef {
  key: string;
  label: string;
}

type Row = Record<string, string | number | null>;

export function SeriesChart({
  kind,
  data,
  x,
  series,
  format,
}: {
  kind: "bar" | "line";
  data: Row[];
  x: string;
  series: SeriesDef[];
  format: (v: number) => string;
}) {
  const common = (
    <>
      <CartesianGrid stroke="var(--line)" vertical={false} />
      <XAxis dataKey={x} {...axis} />
      <YAxis {...axis} width={72} tickFormatter={format} />
      <Tooltip {...tooltip} formatter={(v) => format(Number(v))} />
      {series.length > 1 && <Legend {...legend} />}
    </>
  );
  return (
    <ResponsiveContainer width="100%" height={240}>
      {kind === "bar" ? (
        <BarChart data={data} barGap={2}>
          {common}
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={COLOURS[i]} radius={[4, 4, 0, 0]} maxBarSize={32} />
          ))}
        </BarChart>
      ) : (
        <LineChart data={data}>
          {common}
          {series.map((s, i) => (
            <Line key={s.key} dataKey={s.key} name={s.label} stroke={COLOURS[i]} strokeWidth={2} dot={{ r: 4 }} />
          ))}
        </LineChart>
      )}
    </ResponsiveContainer>
  );
}

export interface Step {
  label: string;
  delta: number;
  total?: boolean;
}

export function Waterfall({ steps, format }: { steps: Step[]; format: (v: number) => string }) {
  const data = steps.map((s, i) => {
    let start = 0;
    for (const prior of steps.slice(0, i)) start = prior.total ? prior.delta : start + prior.delta;
    const range: [number, number] = s.total ? [0, s.delta] : [start, start + s.delta];
    return { label: s.label, range, delta: s.delta, total: !!s.total };
  });
  return (
    <ResponsiveContainer width="100%" height={340}>
      <BarChart data={data} layout="vertical" margin={{ right: 16 }}>
        <CartesianGrid stroke="var(--line)" horizontal={false} />
        <XAxis type="number" {...axis} tickFormatter={format} />
        <YAxis type="category" dataKey="label" width={110} {...axis} />
        <Tooltip {...tooltip} formatter={(_v, _n, item) => [format(item.payload.delta), "Amount"]} />
        <Bar dataKey="range" radius={4} maxBarSize={24} isAnimationActive={false}>
          {data.map((d) => (
            <Cell
              key={d.label}
              fill={d.total ? "var(--neutral)" : d.delta >= 0 ? "var(--series-1)" : "var(--series-2)"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TornadoChart({
  data,
  format,
}: {
  data: { name: string; lower: number; higher: number }[];
  format: (v: number) => string;
}) {
  return (
    <ResponsiveContainer width="100%" height={data.length * 44 + 70}>
      <BarChart data={data} layout="vertical" stackOffset="sign" margin={{ right: 16 }}>
        <CartesianGrid stroke="var(--line)" horizontal={false} />
        <XAxis type="number" {...axis} tickFormatter={format} />
        <YAxis type="category" dataKey="name" width={120} {...axis} />
        <Tooltip {...tooltip} formatter={(v) => format(Number(v))} />
        <Legend {...legend} />
        <ReferenceLine x={0} stroke="var(--ink-2)" />
        <Bar dataKey="lower" name="Input 1 point lower" stackId="t" fill="var(--series-2)" maxBarSize={22} />
        <Bar dataKey="higher" name="Input 1 point higher" stackId="t" fill="var(--series-1)" maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}
