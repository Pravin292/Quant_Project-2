"use client";

import dynamic from "next/dynamic";

import { useApi } from "@/lib/api";
import { crore, day, num, pct, rupees } from "@/lib/format";
import type { Peers } from "@/lib/types";
import { Card, Notice, Skeleton, Stat, Table } from "./ui";

const PeerSpace = dynamic(() => import("./three/PeerSpace"), { ssr: false, loading: () => <Skeleton rows={4} /> });

const times = (v: number | null) => (v === null ? "n/a" : `${num(v, 1)}x`);

export default function PeersTab({ ticker, fairValue, price }: { ticker: string; fairValue: number; price: number | null }) {
  const query = useApi<Peers>(`/api/peers?ticker=${encodeURIComponent(ticker)}`);
  if (query.error) return <Notice kind="error">{query.error}</Notice>;
  if (!query.data || query.loading) return <Skeleton />;
  const p = query.data;
  const all = [p.subject, ...p.peers];
  const versus = (v: number | null) => (v !== null && price ? `${pct(v / price - 1)} vs price` : undefined);
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="DCF value per share" value={rupees(fairValue)} sub={versus(fairValue)} />
        <Stat label="At the peer median P/E" value={rupees(p.value_per_share_at_median_pe)} sub={versus(p.value_per_share_at_median_pe)} />
        <Stat label="At the peer median EV/EBITDA" value={rupees(p.value_per_share_at_median_ev_ebitda)} sub={versus(p.value_per_share_at_median_ev_ebitda)} />
      </div>
      <Card title="Peer cross-check" note={p.note}>
        <Table
          head={["Company", "P/E", "EV/EBITDA", "Market value", "Fiscal year", "Price date", "Fetched"]}
          rows={[
            ...all.map((m) => [
              m.ticker === ticker ? <strong key="t">{m.name} (selected)</strong> : m.name,
              times(m.pe),
              times(m.ev_ebitda),
              crore(m.market_cap),
              m.fiscal_year,
              day(m.price_date),
              day(m.fetched_at),
            ]),
            ["Peer median (excludes selected)", times(p.median_pe), times(p.median_ev_ebitda), "", "", "", ""],
          ]}
        />
      </Card>
      <Card title="Companies in valuation space" note="Further right means a higher P/E, higher up a higher EV/EBITDA; the axes span the data rather than starting at zero. Sphere size follows market value.">
        <PeerSpace companies={all} selected={ticker} />
      </Card>
    </div>
  );
}
