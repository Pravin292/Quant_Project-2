"use client";

import { useEffect, useState } from "react";

import { download, useApi, useDebounced } from "@/lib/api";
import { rupees } from "@/lib/format";
import { decodeShare, encodeShare, matchesDefaults, type Shared } from "@/lib/share";
import type { Assumptions, Defaults, ScenarioName, Scenarios, Valuation } from "@/lib/types";
import BridgeTab from "./BridgeTab";
import ForecastTab from "./ForecastTab";
import Hero from "./Hero";
import HistoricalTab from "./HistoricalTab";
import InputsPanel from "./InputsPanel";
import MonteCarloTab from "./MonteCarloTab";
import PeersTab from "./PeersTab";
import SensitivityTab from "./SensitivityTab";
import SummaryTab from "./SummaryTab";
import { Notice, Skeleton } from "./ui";

const TABS = ["Summary", "Historical", "Forecast", "Valuation bridge", "Sensitivity", "Monte Carlo", "Peers"] as const;
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
    <div className="mx-auto max-w-[1180px] px-4 pb-20 sm:px-6">
      <header className="flex items-center justify-between border-b border-(--line) py-4">
        <h1 className="text-sm font-semibold">
          <span aria-hidden="true" className="mr-2 inline-block h-2.5 w-2.5 rounded-[3px] bg-(--ink)" />
          {ready?.company.name ?? "TCS"}: DCF valuation
        </h1>
        <a
          className="text-xs text-(--ink-2) hover:text-(--ink)"
          href="https://github.com/Pravin292/Quant_Project-2"
          target="_blank"
          rel="noreferrer"
        >
          Source code ↗
        </a>
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
  const [drawer, setDrawer] = useState(false); // phones
  const [panel, setPanel] = useState(true); // wide screens
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

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const excel = async () => {
    setExporting(true);
    setExportError(null);
    try {
      await download("/api/export", { assumptions: lastActive }, "dcf_model.xlsx");
    } catch (e) {
      setExportError((e as Error).message);
    }
    setExporting(false);
  };

  const error = valuation.error ?? scenarios.error;
  const v = valuation.data;
  const busy = valuation.loading || scenarios.loading;

  return (
    <div className="space-y-6">
        <div className="sticky top-0 z-10 -mx-4 z-20 flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-(--line) bg-(--page)/90 px-4 py-2.5 backdrop-blur sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0">
          <div aria-live="polite" className="text-sm">
            Fair value <strong data-testid="fair-value">{rupees(v?.fair_value_per_share)}</strong> vs price{" "}
            {rupees(v?.price)}
            <span className="ml-2 text-(--ink-2)">{busy ? "updating…" : error ? "not updated" : ""}</span>
          </div>
          <span className="ml-auto flex flex-wrap gap-2">
            <button
              type="button"
              className="chip hidden lg:block"
              aria-expanded={panel}
              onClick={() => setPanel((p) => !p)}
            >
              {panel ? "Hide assumptions" : "Show assumptions"}
            </button>
            <button type="button" className="chip lg:hidden" aria-expanded={drawer} onClick={() => setDrawer((d) => !d)}>
              {drawer ? "Hide assumptions" : "Edit assumptions"}
            </button>
            <button type="button" onClick={excel} disabled={exporting || busy || !!error} className="chip disabled:opacity-50">
              {exporting ? "Preparing…" : "Download Excel"}
            </button>
            <button type="button" onClick={share} className="chip chip-solid">
              {copied ?? "Share link"}
            </button>
          </span>
        </div>
        {(broken || (link !== null && !usable)) && (
          <Notice kind="warn">That shared link could not be read, so the defaults are shown.</Notice>
        )}
        {usable && changed && (
          <p className="text-xs text-(--ink-2)">
            Custom assumptions are in this page&apos;s link, including the share price of {rupees(assumptions.bridge.price)}.
          </p>
        )}
        {error && <Notice kind="error">{error}</Notice>}
        {exportError && <Notice kind="error">{exportError}</Notice>}
        {v && <Hero defaults={defaults} assumptions={lastActive} valuation={v} scenario={scenario} />}
        <div className={`gap-6 lg:grid ${panel ? "lg:grid-cols-[272px_minmax(0,1fr)]" : ""}`}>
      <aside className={panel ? "" : "lg:hidden"}>
        <div className={`${drawer ? "block" : "hidden"} panel max-lg:fixed max-lg:inset-x-2 max-lg:bottom-10 max-lg:z-30 max-lg:max-h-[55vh] max-lg:overflow-y-auto max-lg:bg-(--surface-solid)! p-5 lg:sticky lg:top-20 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto ${panel ? "lg:block" : "lg:hidden"}`}>
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
      <main className="min-w-0 space-y-6">
        <div role="tablist" aria-label="Outputs" className="flex gap-1 overflow-x-auto border-b border-(--line)">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`-mb-px border-b-2 px-3 py-2 text-[13px] whitespace-nowrap ${tab === t ? "border-(--ink) font-semibold" : "border-transparent text-(--ink-2) hover:text-(--ink)"}`}
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
            <SummaryTab assumptions={lastActive} valuation={v} scenarios={scenarios.data} />
          ) : tab === "Forecast" ? (
            <ForecastTab assumptions={assumptions} valuation={v} onChange={setAssumptions} />
          ) : tab === "Valuation bridge" ? (
            <BridgeTab defaults={defaults} valuation={v} shares={lastActive.bridge.diluted_shares} />
          ) : tab === "Monte Carlo" ? (
            <MonteCarloTab assumptions={lastActive} />
          ) : tab === "Peers" ? (
            <PeersTab ticker={defaults.company.ticker} fairValue={v.fair_value_per_share} price={v.price} />
          ) : (
            <SensitivityTab assumptions={lastActive} />
          )}
        </div>
      </main>
        </div>
    </div>
  );
}
