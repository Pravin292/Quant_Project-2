"use client";

import { crore, num, rupees } from "@/lib/format";
import type { Defaults, Valuation } from "@/lib/types";
import { Waterfall } from "./charts";
import Bars3D from "./Bars3DLazy";
import { Card, Source, Table } from "./ui";

export default function BridgeTab({ defaults, valuation: v, shares }: { defaults: Defaults; valuation: Valuation; shares: number }) {
  const b = v.bridge;
  const steps = [
    { label: "PV of cash flows", delta: v.sum_pv_fcff },
    { label: "PV of terminal", delta: v.pv_terminal_value },
    { label: "Enterprise value", delta: b.enterprise_value, total: true },
    { label: "Less debt", delta: b.less_debt },
    { label: "Less leases", delta: b.less_leases },
    { label: "Plus cash", delta: b.plus_cash_and_investments },
    { label: "Less minority", delta: b.less_minority_interest },
    { label: "Equity value", delta: b.equity_value, total: true },
  ];
  return (
    <div className="space-y-4">
      <Card title="The bridge in 3D (₹ crore)" note="Black adds value, light grey subtracts, mid grey is a total. Very small steps are drawn as thin slabs.">
        <Bars3D
          label="3D waterfall from present values to equity value"
          columns={["Flows", "Terminal", "EV", "Debt", "Leases", "Cash", "Minority", "Equity"]}
          rows={[""]}
          cells={steps.map((s, col) => {
            let start = 0;
            for (const prior of steps.slice(0, col)) start = prior.total ? prior.delta : start + prior.delta;
            return {
              col,
              row: 0,
              from: s.total ? 0 : start,
              to: s.total ? s.delta : start + s.delta,
              tone: s.total ? ("neutral" as const) : s.delta >= 0 ? ("above" as const) : ("below" as const),
              tip: `${s.label}: ${crore(s.delta)}`,
            };
          })}
        />
      </Card>
      <Card title="From cash flows to equity value (₹ crore)" note="Black adds value, grey subtracts, dark grey is a total.">
        <Waterfall steps={steps} format={(x) => num(x)} />
      </Card>
      <Card title="Bridge table">
        <Table
          head={["Step", "Amount"]}
          rows={[
            ...steps.map((s) => [s.label, crore(s.delta)]),
            [
              <span key="s">
                Diluted shares (crore)
                <Source text={defaults.sources.diluted_shares} />
              </span>,
              num(shares, 2),
            ],
            ["Fair value per share", rupees(v.fair_value_per_share, 2)],
          ]}
        />
        <p className="mt-3 text-xs text-(--ink-2)">Balance sheet source: {defaults.sources.bridge}</p>
      </Card>
    </div>
  );
}
