"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { useApi } from "@/lib/api";
import { day, rupees, signedPct } from "@/lib/format";
import type { Assumptions, Defaults, Grid, Valuation } from "@/lib/types";
import { Skeleton, Source } from "./ui";

const Surface = dynamic(() => import("./three/Surface"), { ssr: false, loading: () => <Skeleton rows={4} /> });

/** Counts smoothly to a new value; jumps straight there if the user prefers less motion. */
function useCountTo(target: number): number {
  const [shown, setShown] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    const start = from.current;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const began = performance.now();
    let frame = requestAnimationFrame(function step(now) {
      const t = still ? 1 : Math.min((now - began) / 500, 1);
      const value = start + (target - start) * (1 - (1 - t) ** 3);
      from.current = value;
      setShown(value);
      if (t < 1) frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
  }, [target]);
  return shown;
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
  const fair = useCountTo(v.fair_value_per_share);
  const price = defaults.price;
  const above = v.upside !== null && v.upside >= 0;
  const top = Math.max(v.fair_value_per_share, v.price ?? 0, defaults.week_52.week52_high ?? 0) * 1.08;
  const bar = (label: string, value: number | null, colour: string) =>
    value === null ? null : (
      <div className="grid grid-cols-[5.5rem_1fr_5rem] items-center gap-2 text-xs">
        <span className="text-(--ink-2)">{label}</span>
        <span className="h-3 overflow-hidden rounded-full bg-(--line)">
          <span className="block h-full rounded-full transition-[width] duration-500" style={{ width: `${(value / top) * 100}%`, background: colour }} />
        </span>
        <span className="text-right font-semibold tabular-nums">{rupees(value)}</span>
      </div>
    );
  return (
    <section className="panel rise relative overflow-hidden">
      <div className="pointer-events-none relative z-10 flex flex-col gap-5 p-6 sm:p-8 lg:absolute lg:inset-y-0 lg:left-0 lg:w-[25rem] lg:justify-center [&_button]:pointer-events-auto">
      <div>
        <p className="text-xs tracking-widest text-(--ink-2) uppercase">
          Model fair value per share, {scenario} case
          <Source text={`Computed from the assumptions shown. ${defaults.sources.bridge}`} />
        </p>
        <p className="display brand-text text-6xl font-bold sm:text-8xl lg:text-7xl xl:text-8xl">{rupees(fair)}</p>
        <p className="mt-2 inline-flex items-center gap-2 rounded-full border border-(--line) px-3 py-1 text-sm">
          <span aria-hidden="true" style={{ color: above ? "var(--series-1)" : "var(--series-2)" }}>
            {above ? "▲" : "▼"}
          </span>
          <strong>{signedPct(v.upside)}</strong>
          <span className="text-(--ink-2)">model value {above ? "above" : "below"} market price</span>
        </p>
      </div>
      <div className="space-y-3">
        {bar("Model value", v.fair_value_per_share, above ? "var(--series-1)" : "var(--series-2)")}
        {bar("Market price", v.price, "var(--neutral)")}
        <p className="text-xs text-(--ink-2)">
          {price.fallback ? "Saved" : "Live"} quote, {day(price.as_of)}
          <Source text={`${price.source}; ${price.as_of}`} />
          {defaults.week_52.week52_low !== null &&
            ` · 52-week range ${rupees(defaults.week_52.week52_low)} to ${rupees(defaults.week_52.week52_high)}`}
        </p>
      </div>
      </div>
      <div className="px-3 pb-3 lg:ml-[25rem] lg:pt-3">
        {surface.data ? (
          <div className={surface.loading ? "opacity-60" : ""}>
            <Surface grid={surface.data} price={assumptions.bridge.price} height={460} compact />
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
