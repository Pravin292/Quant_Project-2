"use client";

import { useApi } from "@/lib/api";
import { day, num, pct } from "@/lib/format";
import type { Historical } from "@/lib/types";
import { SeriesChart } from "./charts";
import { Card, Notice, Skeleton, Table } from "./ui";

export default function HistoricalTab({ ticker }: { ticker: string }) {
  const query = useApi<Historical>(`/api/historical?ticker=${encodeURIComponent(ticker)}`);
  if (query.error) return <Notice kind="error">{query.error}</Notice>;
  if (!query.data || query.loading) return <Skeleton />;
  const { years, company } = query.data;
  const data = years as Record<string, string | number | null>[];
  const source = `${company.source}, fetched ${day(company.fetched_at)}`;
  const row = (label: string, key: string, format: (v: unknown) => string) => [
    label,
    ...years.map((y) => format(y[key])),
  ];
  const percent = (v: number) => pct(v);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Revenue (₹ crore)">
          <SeriesChart kind="bar" data={data} x="fiscal_year" series={[{ key: "revenue", label: "Revenue" }]} format={(v) => num(v)} />
        </Card>
        <Card title="Margins (% of revenue)">
          <SeriesChart
            kind="line"
            data={data}
            x="fiscal_year"
            series={[{ key: "ebit_margin", label: "EBIT" }, { key: "ebitda_margin", label: "EBITDA" }]}
            format={percent}
          />
        </Card>
        <Card title="Reinvestment (% of revenue)">
          <SeriesChart
            kind="line"
            data={data}
            x="fiscal_year"
            series={[
              { key: "capex_pct", label: "CapEx" },
              { key: "da_pct", label: "D&A" },
              { key: "nwc_pct", label: "Working capital" },
            ]}
            format={percent}
          />
        </Card>
        <Card title="Tax rate">
          <SeriesChart kind="line" data={data} x="fiscal_year" series={[{ key: "tax_rate", label: "Effective tax rate" }]} format={percent} />
        </Card>
      </div>
      <Card title="Historical figures" note={`Source: ${source}. Money in ₹ crore.`}>
        <Table
          head={["Measure", ...years.map((y) => y.fiscal_year)]}
          rows={[
            row("Revenue (₹ cr)", "revenue", num),
            row("Revenue growth", "revenue_growth", pct),
            row("EBIT (₹ cr)", "ebit", num),
            row("EBIT margin", "ebit_margin", pct),
            row("EBITDA margin", "ebitda_margin", pct),
            row("Tax rate", "tax_rate", pct),
            row("D&A % revenue", "da_pct", pct),
            row("CapEx % revenue", "capex_pct", pct),
            row("Working capital % revenue", "nwc_pct", pct),
            row("Operating cash flow ÷ net income (x)", "cash_conversion", (v) => num(v, 2)),
            row("Operating cash flow − CapEx (₹ cr)", "fcf_proxy", num),
            row("Return on invested capital", "roic", pct),
          ]}
        />
      </Card>
    </div>
  );
}
