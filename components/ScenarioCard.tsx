"use client";

import { useState } from "react";

import { pct, rupees, signedPct } from "@/lib/format";
import type { Probabilities, ScenarioName, Scenarios } from "@/lib/types";
import { Card, Table } from "./ui";

const NAMES: ScenarioName[] = ["bear", "base", "bull"];

/** F26: editable scenario probabilities and the probability-weighted value. */
export default function ScenarioCard({
  scenarios,
  probabilities,
  onProbabilities,
}: {
  scenarios: Scenarios | null;
  probabilities: Probabilities;
  onProbabilities: (p: Probabilities) => void;
}) {
  const [draft, setDraft] = useState(() => NAMES.map((n) => String(Math.round(probabilities[n] * 1000) / 10)));
  const [seen, setSeen] = useState(probabilities);
  if (seen !== probabilities) {
    setSeen(probabilities); // the parent changed them (for example "Reset to defaults")
    if (NAMES.some((n, i) => Math.abs(Number(draft[i]) - probabilities[n] * 100) > 0.01)) {
      setDraft(NAMES.map((n) => String(Math.round(probabilities[n] * 1000) / 10)));
    }
  }
  const numbers = draft.map(Number);
  const total = numbers.reduce((a, b) => a + b, 0);
  const valid = draft.every((d) => d !== "") && numbers.every((n) => n >= 0) && Math.abs(total - 100) < 0.01;
  const change = (i: number, text: string) => {
    const next = draft.map((d, j) => (j === i ? text : d));
    setDraft(next);
    const values = next.map(Number);
    const ok = next.every((d) => d !== "") && values.every((n) => n >= 0);
    if (ok && Math.abs(values.reduce((a, b) => a + b, 0) - 100) < 0.01) {
      onProbabilities({ bear: values[0] / 100, base: values[1] / 100, bull: values[2] / 100 });
    }
  };
  return (
    <Card title="Scenarios">
      {scenarios ? (
        <Table
          head={["Case", "Per share", "vs price", "Probability (%)"]}
          rows={[
            ...NAMES.map((n, i) => [
              <span key={n} className="capitalize">{n}</span>,
              rupees(scenarios.scenarios[n].fair_value_per_share),
              signedPct(scenarios.scenarios[n].upside),
              <input
                key="p"
                type="number"
                min={0}
                max={100}
                step={5}
                aria-label={`Probability of the ${n} case, percent`}
                className="w-16 rounded border border-(--line) bg-(--surface) p-1 text-right"
                value={draft[i]}
                onChange={(e) => change(i, e.target.value)}
              />,
            ]),
            ["Weighted", rupees(scenarios.expected_fair_value), signedPct(scenarios.expected_upside), pct(1, 0)],
          ]}
        />
      ) : (
        <p className="text-sm text-(--ink-2)">Loading scenarios…</p>
      )}
      {!valid && (
        <p role="alert" className="mt-2 text-xs">
          Probabilities must add to 100% (now {Math.round(total * 10) / 10}%). The weighted value uses the last valid set.
        </p>
      )}
    </Card>
  );
}
