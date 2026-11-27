"use client";

import { useApi } from "@/lib/api";
import { crore, pct, rupees, signedPct } from "@/lib/format";
import type { Assumptions, ReverseDcf, Scenarios, Valuation } from "@/lib/types";
import { Card, Notice, Table } from "./ui";

export default function SummaryTab({
  assumptions,
  valuation: v,
  scenarios,
}: {
  assumptions: Assumptions;
  valuation: Valuation;
  scenarios: Scenarios | null;
}) {
  const reverse = useApi<ReverseDcf>("/api/reverse-dcf", { assumptions });
  const op = assumptions.operating;
  return (
    <div className="space-y-4">
      {v.warnings.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold">Check before trusting this result</h2>
          {v.warnings.map((w) => (
            <Notice key={w.code} kind="warn">
              {w.message}
            </Notice>
          ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Headline assumptions">
          <Table
            head={["Assumption", "Value"]}
            rows={[
              ["Revenue growth, year 1 to 5", `${pct(op.revenue_growth[0])} to ${pct(op.revenue_growth.at(-1))}`],
              ["EBIT margin, year 1", pct(op.ebit_margin[0])],
              ["Tax rate", pct(op.tax_rate)],
              ["WACC", pct(v.wacc_used, 2)],
              ["Cost of equity", pct(v.wacc.cost_of_equity, 2)],
              ["Terminal growth", pct(assumptions.terminal.growth, 2)],
              ["Enterprise value", crore(v.enterprise_value)],
              ["Terminal value share of EV", pct(v.terminal_value_share, 0)],
            ]}
          />
        </Card>
        <div className="space-y-4">
          <Card title="Scenarios">
            {scenarios ? (
              <Table
                head={["Case", "Per share", "vs price", "Weight"]}
                rows={[
                  ...(["bear", "base", "bull"] as const).map((n) => [
                    <span key={n} className="capitalize">{n}</span>,
                    rupees(scenarios.scenarios[n].fair_value_per_share),
                    signedPct(scenarios.scenarios[n].upside),
                    pct(scenarios.scenarios[n].probability, 0),
                  ]),
                  ["Weighted", rupees(scenarios.expected_fair_value), signedPct(scenarios.expected_upside), ""],
                ]}
              />
            ) : (
              <p className="text-sm text-(--ink-2)">Loading scenarios…</p>
            )}
          </Card>
          <Card title="What is the price assuming? (reverse DCF)">
            <p className="text-sm">{reverse.error ?? (reverse.loading ? "Solving…" : reverse.data?.message)}</p>
          </Card>
          <Card title="Cross-checks, per share">
            <Table
              head={["Method", "Value"]}
              rows={[
                ["Perpetuity growth (headline)", rupees(v.fair_value_per_share)],
                ["Exit multiple", rupees(v.exit_cross_check?.fair_value_per_share)],
                ["Value driver (growth paid for at ROIC)", rupees(v.value_driver_cross_check?.fair_value_per_share)],
              ]}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}
