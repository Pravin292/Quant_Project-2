"use client";

import dynamic from "next/dynamic";

import { useApi } from "@/lib/api";
import { day, rupees, signedPct } from "@/lib/format";
import type { Assumptions, Defaults, Grid, Valuation } from "@/lib/types";
import BlurText from "./reactbits/BlurText";
import CountUp from "./reactbits/CountUp";
import SpotlightCard from "./reactbits/SpotlightCard";
import { Skeleton, Source } from "./ui";

const Surface = dynamic(() => import("./three/Surface"), { ssr: false, loading: () => <Skeleton rows={4} /> });

function Metric({ label, source, children, note }: { label: string; source?: string; children: React.ReactNode; note: string }) {
  return (
    <SpotlightCard theme="light" className="!rounded-xl !p-4 !shadow-none" spotlightSize={180} intensity={0.12}>
      <p className="text-xs text-(--ink-2)">
        {label}
        <Source text={source} />
      </p>
      <p className="mt-1 text-xl font-semibold tracking-tight tabular-nums">{children}</p>
      <p className="mt-0.5 text-xs text-(--ink-2)">{note}</p>
    </SpotlightCard>
  );
}

export default function Hero({
  defaults,
  assumptions,
  valuation: v,
  scenario,
}: {
  defaults: Defaults;
  assumptions: Assumptions;
  valuation: Valuation;
  scenario: string;
}) {
  const surface = useApi<Grid>("/api/surface", assumptions);
  const price = defaults.price;
  const above = v.upside !== null && v.upside >= 0;
  const { week52_low: low, week52_high: high } = defaults.week_52;
  return (
    <section className="space-y-5">
      <div className="pt-6 text-center">
        <BlurText
          key={defaults.company.ticker}
          text={`What is one ${defaults.company.ticker.replace(".NS", "")} share worth?`}
          animateBy="words"
          trigger="load"
          delay={60}
          className="justify-center text-3xl font-semibold tracking-tight sm:text-5xl"
        />
        <p className="mx-auto mt-3 max-w-xl text-sm text-(--ink-2)">
          A five-year discounted cash flow model of {defaults.company.name}. Every assumption is yours to change.
          Statements fetched {day(defaults.company.fetched_at)}.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Model fair value" source={`Computed from the assumptions shown. ${defaults.sources.bridge}`} note={`per share, ${scenario} case`}>
          {/* starts at the true value, so a wrong number is never shown; later changes count across */}
          <CountUp to={Math.round(v.fair_value_per_share)} from={Math.round(v.fair_value_per_share)} prefix="₹" separator="," duration={0.6} trigger="load" />
        </Metric>
        <Metric label="Market price" source={`${price.source}; ${price.as_of}`} note={`${price.fallback ? "saved" : "live"} quote, ${day(price.as_of)}`}>
          {rupees(v.price)}
        </Metric>
        <Metric label={above ? "Upside" : "Downside"} note={`model value ${above ? "above" : "below"} price`}>
          {signedPct(v.upside)}
        </Metric>
        <Metric label="52-week range" source={`${defaults.company.source}, fetched ${day(defaults.company.fetched_at)}`} note="market price, past year">
          {low === null ? "n/a" : `${rupees(low)} – ${rupees(high)}`}
        </Metric>
      </div>
      <div className="panel p-3">
        {surface.data ? (
          <div className={surface.loading ? "opacity-60" : ""}>
            <Surface grid={surface.data} price={assumptions.bridge.price} height={440} compact />
          </div>
        ) : surface.error ? (
          <p className="p-6 text-sm text-(--ink-2)">{surface.error}</p>
        ) : (
          <Skeleton rows={6} />
        )}
      </div>
    </section>
  );
}
