"use client";

import { useEffect, useState } from "react";

import { useApi, useDebounced } from "@/lib/api";
import { day, rupees } from "@/lib/format";
import { decodeShare, encodeShare, matchesDefaults, type Shared } from "@/lib/share";
import type { Assumptions, Defaults, ScenarioName, Scenarios, Valuation } from "@/lib/types";
import BridgeTab from "./BridgeTab";
import ForecastTab from "./ForecastTab";
import HistoricalTab from "./HistoricalTab";
import InputsPanel from "./InputsPanel";
import SensitivityTab from "./SensitivityTab";
import SummaryTab from "./SummaryTab";
import { Notice, Skeleton } from "./ui";

const TABS = ["Summary", "Historical", "Forecast", "Valuation bridge", "Sensitivity"] as const;
type Tab = (typeof TABS)[number];

const DEFAULT_TICKER = "TCS.NS";
const readHash = () =>
  typeof window === "undefined" ? null : decodeShare(window.location.hash.replace(/^#s=/, ""));

export default function Dashboard() {
  // The link is read after mounting so the server and first client render match.
  const [start, setStart] = useState<{ ticker: string; link: ReturnType<typeof readHash>; broken: boolean } | null>(null);
  useEffect(() => {
    const load = () => {
      const link = readHash();
      setStart({
        ticker: link?.a.ticker ?? DEFAULT_TICKER,
        link,
        broken: window.location.hash.startsWith("#s=") && link === null,
      });
    };
    const timer = setTimeout(load, 0);
    window.addEventListener("hashchange", load); // a pasted link in the same tab
    return () => {
      clearTimeout(timer);
      window.removeEventListener("hashchange", load);
    };
  }, []);

  const defaults = useApi<Defaults>(
    start ? `/api/defaults?ticker=${encodeURIComponent(start.ticker)}` : null,
  );
  const ready = defaults.data && defaults.data.company.ticker === start?.ticker ? defaults.data : null;

  return (
    <div className="mx-auto max-w-[1500px] px-4 pb-16">
      <header className="py-4">
        <h1 className="text-xl font-semibold">{ready?.company.name ?? "TCS"}: DCF valuation</h1>
        <p className="text-sm text-(--ink-2)">
          Five-year discounted cash flow model. Move any assumption and the value updates.
          {ready && ` Statements fetched ${day(ready.company.fetched_at)}.`}
        </p>
      </header>
      {defaults.error ? (
        <Notice kind="error">{defaults.error} Reload the page to try again.</Notice>
      ) : ready && start ? (
        <Model
          key={`${ready.company.ticker} ${start.link ? encodeShare({ assumptions: start.link.a, scenario: start.link.s }) : ""}`}
          defaults={ready}
          link={start.link}
          broken={start.broken}
          onTicker={(ticker) => {
            window.history.replaceState(null, "", window.location.pathname);
            setStart({ ticker, link: null, broken: false });
          }}
        />
      ) : (
        <Skeleton rows={5} />
      )}
      <footer className="fixed inset-x-0 bottom-0 z-20 border-t border-(--line) bg-(--surface) p-2 text-center text-xs">
        Educational model. Not investment advice.
      </footer>
    </div>
  );
}

function Model({
  defaults,
  link,
  broken,
  onTicker,
}: {
  defaults: Defaults;
  link: ReturnType<typeof readHash>;
  broken: boolean;
  onTicker: (ticker: string) => void;
}) {
  const usable = link !== null && matchesDefaults(link.a, defaults.assumptions);
  const initial: Shared = usable
    ? {
        scenario: link.s,
        assumptions: { ...link.a, wacc: { ...link.a.wacc, sources: defaults.assumptions.wacc.sources } },
      }
    : { scenario: "base", assumptions: defaults.assumptions };

  const [assumptions, setAssumptions] = useState<Assumptions>(initial.assumptions);
  const [scenario, setScenario] = useState<ScenarioName>(initial.scenario);
  const [tab, setTab] = useState<Tab>("Summary");
  const [drawer, setDrawer] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const base = useDebounced(assumptions);
  const scenarios = useApi<Scenarios>("/api/scenarios", { assumptions: base });
  const scenarioInputs = scenarios.loading ? null : (scenarios.data?.scenarios[scenario].assumptions ?? null);
  const active = scenario === "base" ? base : scenarioInputs;
  const [lastActive, setLastActive] = useState<Assumptions>(base);
  if (active && active !== lastActive && JSON.stringify(active) !== JSON.stringify(lastActive)) {
    setLastActive(active);
  }
  const valuation = useApi<Valuation>("/api/valuation", lastActive);

  const changed = scenario !== "base" || JSON.stringify(assumptions) !== JSON.stringify(defaults.assumptions);
  const hash = changed ? `#s=${encodeShare({ assumptions: base, scenario })}` : "";
  useEffect(() => {
    window.history.replaceState(null, "", `${window.location.pathname}${hash}`);
  }, [hash]);

  const share = async () => {
    const url = `${window.location.origin}${window.location.pathname}#s=${encodeShare({ assumptions, scenario })}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied("Link copied");
    } catch {
      setCopied("Copy the address bar to share");
    }
    setTimeout(() => setCopied(null), 3000);
  };

  const error = valuation.error ?? scenarios.error;
  const v = valuation.data;
  const busy = valuation.loading || scenarios.loading;

  return (
    <div className="gap-4 lg:grid lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="mb-4 lg:mb-0">
        <button
          type="button"
          className="w-full rounded border border-(--line) bg-(--surface) p-3 text-sm font-semibold lg:hidden"
          aria-expanded={drawer}
          onClick={() => setDrawer((d) => !d)}
        >
          {drawer ? "Hide assumptions" : "Edit assumptions"}
        </button>
        <div className={`${drawer ? "block" : "hidden"} mt-2 rounded-lg border border-(--line) bg-(--surface) p-4 lg:sticky lg:top-2 lg:mt-0 lg:block lg:max-h-[calc(100vh-4rem)] lg:overflow-y-auto`}>
          <InputsPanel
            defaults={defaults}
            assumptions={assumptions}
            scenario={scenario}
            onChange={setAssumptions}
            onScenario={setScenario}
            onTicker={onTicker}
            onReset={() => {
              setAssumptions(defaults.assumptions);
              setScenario("base");
            }}
          />
        </div>
      </aside>

      <main className="min-w-0 space-y-4">
        {(broken || (link !== null && !usable)) && (
          <Notice kind="warn">That shared link could not be read, so the defaults are shown.</Notice>
        )}
        {usable && changed && (
          <p className="text-xs text-(--ink-2)">
            Custom assumptions are in this page&apos;s link, including the share price of {rupees(assumptions.bridge.price)}.
          </p>
        )}
        <div className="sticky top-0 z-10 -mx-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-(--line) bg-(--page) px-4 py-2 lg:mx-0 lg:px-0">
          <div aria-live="polite" className="text-sm">
            Fair value <strong data-testid="fair-value">{rupees(v?.fair_value_per_share)}</strong> vs price{" "}
            {rupees(v?.price)}
            <span className="ml-2 text-(--ink-2)">{busy ? "updating…" : error ? "not updated" : ""}</span>
          </div>
          <button type="button" onClick={share} className="ml-auto rounded border border-(--line) bg-(--surface) px-3 py-1 text-sm">
            {copied ?? "Share link"}
          </button>
        </div>
        {error && <Notice kind="error">{error}</Notice>}
        <div role="tablist" aria-label="Outputs" className="flex gap-1 overflow-x-auto border-b border-(--line)">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`border-b-2 px-3 py-2 text-sm whitespace-nowrap ${tab === t ? "border-(--series-1) font-semibold" : "border-transparent text-(--ink-2)"}`}
            >
              {t}
            </button>
          ))}
        </div>
        <div role="tabpanel" aria-label={tab} className={error ? "opacity-50" : ""}>
          {tab === "Historical" ? (
            <HistoricalTab ticker={defaults.company.ticker} />
          ) : !v ? (
            error ? null : <Skeleton />
          ) : tab === "Summary" ? (
            <SummaryTab defaults={defaults} assumptions={lastActive} valuation={v} scenarios={scenarios.data} scenario={scenario} />
          ) : tab === "Forecast" ? (
            <ForecastTab assumptions={assumptions} valuation={v} onChange={setAssumptions} />
          ) : tab === "Valuation bridge" ? (
            <BridgeTab defaults={defaults} valuation={v} shares={lastActive.bridge.diluted_shares} />
          ) : (
            <SensitivityTab assumptions={lastActive} />
          )}
        </div>
      </main>
    </div>
  );
}
