"use client";

import { useApi } from "@/lib/api";
import { rupees } from "@/lib/format";
import type { Assumptions, Defaults, MonteCarlo, Peers, Scenarios } from "@/lib/types";
import { Card, Skeleton, Table } from "./ui";

interface Bar {
  label: string;
  low: number;
  high: number;
  mid?: number;
  midLabel?: string;
}

/** F21: every valuation method as a horizontal range, with today's price as a line. */
export default function FootballField({
  assumptions,
  scenarios,
  week52,
  ticker,
}: {
  assumptions: Assumptions;
  scenarios: Scenarios | null;
  week52: Defaults["week_52"];
  ticker: string | null; // null for uploaded data: no peer bars
}) {
  const mc = useApi<MonteCarlo>("/api/montecarlo", { assumptions });
  const peers = useApi<Peers>(ticker ? `/api/peers?ticker=${encodeURIComponent(ticker)}` : null);
  const price = assumptions.bridge.price;
  const bars: Bar[] = [];
  if (scenarios) {
    const s = scenarios.scenarios;
    bars.push({
      label: "DCF, bear to bull",
      low: s.bear.fair_value_per_share,
      high: s.bull.fair_value_per_share,
      mid: s.base.fair_value_per_share,
      midLabel: "base",
    });
  }
  if (mc.data) {
    const p = mc.data.percentiles;
    bars.push({ label: "Monte Carlo, 5th to 95th", low: p.p5, high: p.p95, mid: p.p50, midLabel: "median" });
  }
  const p = peers.data;
  if (p?.value_range_pe) {
    bars.push({ label: "Peer P/E, lowest to highest", low: p.value_range_pe[0], high: p.value_range_pe[1], mid: p.value_per_share_at_median_pe ?? undefined, midLabel: "median" });
  }
  if (p?.value_range_ev_ebitda) {
    bars.push({ label: "Peer EV/EBITDA, lowest to highest", low: p.value_range_ev_ebitda[0], high: p.value_range_ev_ebitda[1], mid: p.value_per_share_at_median_ev_ebitda ?? undefined, midLabel: "median" });
  }
  if (week52.week52_low !== null && week52.week52_high !== null) {
    bars.push({ label: "52-week price range", low: week52.week52_low, high: week52.week52_high });
  }
  const loading = !scenarios || mc.loading || peers.loading;
  const values = bars.flatMap((b) => [b.low, b.high]).concat(price ? [price] : []);
  const lo = Math.min(...values) * 0.95;
  const hi = Math.max(...values) * 1.03;
  const at = (v: number) => `${((v - lo) / (hi - lo || 1)) * 100}%`;
  return (
    <Card
      title="Football field: value per share by method"
      note={`Each bar spans the range of one method; the tick marks its central value. The dashed line is the market price of ${rupees(price)}.`}
    >
      {bars.length === 0 ? (
        <Skeleton rows={3} />
      ) : (
        <div className={loading ? "opacity-60" : ""}>
          <div role="img" aria-label="Football field chart; the table below lists the same ranges" className="space-y-2">
            {bars.map((b) => (
              <div key={b.label} className="grid items-center gap-x-3 sm:grid-cols-[13rem_1fr]">
                <span className="text-xs">{b.label}</span>
                <div className="relative h-6" title={`${b.label}: ${rupees(b.low)} to ${rupees(b.high)}`}>
                  <span className="absolute inset-y-1 rounded bg-(--series-1)" style={{ left: at(b.low), width: `calc(${at(b.high)} - ${at(b.low)})` }} />
                  {b.mid !== undefined && <span className="absolute inset-y-0 w-0.5 bg-(--ink)" style={{ left: at(b.mid) }} />}
                  {price !== null && <span className="absolute -inset-y-1 border-l-2 border-dashed border-(--series-2)" style={{ left: at(price) }} />}
                </div>
              </div>
            ))}
            <div className="grid sm:grid-cols-[13rem_1fr] sm:gap-x-3">
              <span />
              <div className="flex justify-between text-[11px] text-(--ink-2)">
                <span>{rupees(lo)}</span>
                <span>{rupees(hi)}</span>
              </div>
            </div>
          </div>
          <div className="mt-3">
            <Table
              head={["Method", "Low", "Central", "High"]}
              rows={bars.map((b) => [b.label, rupees(b.low), b.mid === undefined ? "" : `${rupees(b.mid)} (${b.midLabel})`, rupees(b.high)])}
            />
          </div>
        </div>
      )}
    </Card>
  );
}
