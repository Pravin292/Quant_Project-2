"use client";

import { useEffect, useRef, useState } from "react";

import { day, rupees, signedPct } from "@/lib/format";
import type { Defaults, Valuation } from "@/lib/types";
import { Source } from "./ui";

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

export default function Hero({ defaults, valuation: v, scenario }: { defaults: Defaults; valuation: Valuation; scenario: string }) {
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
    <section className="panel rise grid gap-6 p-6 md:grid-cols-[auto_1fr] md:items-center">
      <div>
        <p className="text-xs tracking-widest text-(--ink-2) uppercase">
          Model fair value per share, {scenario} case
          <Source text={`Computed from the assumptions shown. ${defaults.sources.bridge}`} />
        </p>
        <p className="display text-6xl font-bold sm:text-7xl">{rupees(fair)}</p>
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
    </section>
  );
}
