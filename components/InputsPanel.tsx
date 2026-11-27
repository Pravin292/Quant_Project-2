"use client";

import { useState } from "react";

import type { Assumptions, Defaults, ScenarioName } from "@/lib/types";
import { pct } from "@/lib/format";
import { Source } from "./ui";

const round = (v: number) => Math.round(v * 1e6) / 1e6;
const mean = (values: number[]) => values.reduce((a, b) => a + b, 0) / values.length;

function Slider({
  label,
  value,
  range,
  step,
  onChange,
  percent = true,
  source,
}: {
  label: string;
  value: number;
  range: [number, number];
  step: number;
  onChange: (v: number) => void;
  percent?: boolean;
  source?: string;
}) {
  const shown = percent ? pct(value, 2) : value.toFixed(2);
  return (
    <div className="py-1">
      <div className="flex justify-between text-xs">
        <span>
          {label}
          <Source text={source} />
        </span>
        <output className="font-semibold tabular-nums">{shown}</output>
      </div>
      <input
        type="range"
        aria-label={label}
        aria-valuetext={shown}
        className="w-full"
        min={range[0]}
        max={range[1]}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function TickerField({ current, tickers, onTicker }: { current: string; tickers: string[]; onTicker: (t: string) => void }) {
  const [text, setText] = useState(current);
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const typed = text.trim().toUpperCase();
        const match = tickers.find((t) => t === typed || t === `${typed}.NS`);
        if (!match) return setError(`No data for ${typed || "that ticker"}. Try ${tickers.join(", ")}.`);
        setError(null);
        if (match !== current) onTicker(match);
        else setText(match);
      }}
    >
      <label className="block text-xs">
        Company ticker
        <span className="mt-1 flex gap-2">
          <input
            list="tickers"
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full min-w-0 rounded-lg border border-(--line) bg-(--surface) p-2 text-sm uppercase"
          />
          <button type="submit" className="chip">
            Load
          </button>
        </span>
      </label>
      <datalist id="tickers">
        {tickers.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
      {error && (
        <p role="alert" className="mt-1 text-xs">
          {error}
        </p>
      )}
    </form>
  );
}

export default function InputsPanel({
  defaults,
  assumptions,
  scenario,
  onChange,
  onScenario,
  onTicker,
  onReset,
}: {
  defaults: Defaults;
  assumptions: Assumptions;
  scenario: ScenarioName;
  onChange: (next: Assumptions) => void;
  onScenario: (s: ScenarioName) => void;
  onTicker: (t: string) => void;
  onReset: () => void;
}) {
  const { operating: op, wacc, terminal } = assumptions;
  const b = defaults.bounds;
  const src = defaults.sources;
  const setOp = (patch: Partial<Assumptions["operating"]>) =>
    onChange({ ...assumptions, operating: { ...op, ...patch } });
  const setWacc = (patch: Partial<Assumptions["wacc"]>) =>
    onChange({ ...assumptions, wacc: { ...wacc, ...patch } });
  const clamp = (v: number, [lo, hi]: [number, number]) => Math.min(hi, Math.max(lo, v));
  const margin = round(mean(op.ebit_margin));

  return (
    <div className="space-y-4">
      <TickerField key={defaults.company.ticker} current={defaults.company.ticker} tickers={defaults.tickers} onTicker={onTicker} />

      <fieldset>
        <legend className="text-xs">Scenario</legend>
        <div className="mt-1 grid grid-cols-3 overflow-hidden rounded border border-(--line)">
          {(["bear", "base", "bull"] as const).map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={scenario === s}
              onClick={() => onScenario(s)}
              className={`p-2 text-sm capitalize ${scenario === s ? "bg-(--ink) font-semibold text-white" : ""}`}
            >
              {s}
            </button>
          ))}
        </div>
        {scenario !== "base" && (
          <p className="mt-1 text-xs text-(--ink-2)">
            The sliders show the base case. The {scenario} case shifts growth, margin and terminal
            growth from it.
          </p>
        )}
      </fieldset>

      <details className="border-t border-(--line) pt-3" open>
        <summary className="mb-2 text-sm font-semibold">Revenue growth</summary>
        {op.revenue_growth.map((g, i) => (
          <Slider
            key={i}
            label={`Year ${i + 1}`}
            value={g}
            range={b.revenue_growth}
            step={0.001}
            source={i === 0 ? src.revenue_growth : undefined}
            onChange={(v) =>
              setOp({ revenue_growth: op.revenue_growth.map((old, j) => (j === i ? v : old)) })
            }
          />
        ))}
      </details>

      <details className="border-t border-(--line) pt-3">
        <summary className="mb-2 text-sm font-semibold">Operations</summary>
        <Slider
          label="EBIT margin (average of years)"
          value={margin}
          range={b.ebit_margin}
          step={0.001}
          source={src.ebit_margin}
          onChange={(v) =>
            setOp({ ebit_margin: op.ebit_margin.map((m) => round(clamp(m + v - margin, b.ebit_margin))) })
          }
        />
        <Slider label="Tax rate" value={op.tax_rate} range={b.tax_rate} step={0.001} source={src.tax_rate} onChange={(v) => setOp({ tax_rate: v })} />
        <Slider label="CapEx % of revenue" value={op.capex_pct} range={b.capex_pct} step={0.001} source={src.capex_pct} onChange={(v) => setOp({ capex_pct: v })} />
        <Slider label="Working capital % of revenue" value={op.nwc_pct} range={b.nwc_pct} step={0.001} source={src.nwc_pct} onChange={(v) => setOp({ nwc_pct: v })} />
      </details>

      <details className="border-t border-(--line) pt-3">
        <summary className="mb-2 text-sm font-semibold">Discount rate and terminal value</summary>
        <Slider label="Risk-free rate" value={wacc.risk_free} range={b.risk_free} step={0.0005} source={src["wacc.risk_free"]} onChange={(v) => setWacc({ risk_free: v })} />
        <Slider label="Equity risk premium" value={wacc.equity_risk_premium} range={b.equity_risk_premium} step={0.0005} source={src["wacc.equity_risk_premium"]} onChange={(v) => setWacc({ equity_risk_premium: v })} />
        <Slider label="Beta" value={wacc.beta} range={b.beta} step={0.01} percent={false} source={src["wacc.beta"]} onChange={(v) => setWacc({ beta: v })} />
        <Slider
          label="Terminal growth"
          value={terminal.growth}
          range={b.terminal_growth}
          step={0.0025}
          source={src.terminal_growth}
          onChange={(v) => onChange({ ...assumptions, terminal: { ...terminal, growth: v } })}
        />
        <label className="mt-2 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={assumptions.mid_year}
            onChange={(e) => onChange({ ...assumptions, mid_year: e.target.checked })}
          />
          Mid-year discounting (off = end of year)
        </label>
      </details>

      <button type="button" onClick={onReset} className="chip w-full">
        Reset to defaults
      </button>
    </div>
  );
}
