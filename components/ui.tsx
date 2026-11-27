"use client";

import { useId, useState, type ReactNode } from "react";

export function Card({ title, children, note }: { title?: string; children: ReactNode; note?: ReactNode }) {
  return (
    <section className="panel min-w-0 p-5">
      {title && <h2 className="mb-3 text-[13px] font-semibold">{title}</h2>}
      {children}
      {note && <p className="mt-3 text-xs text-(--ink-2)">{note}</p>}
    </section>
  );
}

/** Source and date of a number: shown on hover, keyboard focus or tap. */
export function Source({ text }: { text: string | undefined }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  if (!text) return null;
  return (
    <span
      className="relative inline-block align-middle"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        aria-label="Show source"
        aria-describedby={open ? id : undefined}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-(--line) text-[10px] text-(--ink-2)"
        onClick={() => setOpen((o) => !o)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        i
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="fixed inset-x-4 bottom-12 z-30 rounded border border-(--line) bg-(--surface) p-2 text-left text-xs font-normal text-(--ink) shadow-lg sm:absolute sm:inset-x-auto sm:bottom-6 sm:left-0 sm:w-64"
        >
          {text}
        </span>
      )}
    </span>
  );
}

export function Stat({ label, value, sub, source }: { label: string; value: string; sub?: string; source?: string }) {
  return (
    <div className="panel min-w-0 p-5">
      <div className="text-xs text-(--ink-2)">
        {label}
        <Source text={source} />
      </div>
      <div className="mt-1 text-lg font-semibold tracking-tight tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs text-(--ink-2)">{sub}</div>}
    </div>
  );
}

export function Notice({ kind, children }: { kind: "warn" | "error"; children: ReactNode }) {
  const colours =
    kind === "warn" ? "border-(--warn-line) bg-(--warn-bg)" : "border-(--error-line) bg-(--error-bg)";
  return (
    <div role={kind === "error" ? "alert" : undefined} className={`rounded border-l-4 p-3 text-sm ${colours}`}>
      <span aria-hidden="true">{kind === "warn" ? "⚠ " : "✕ "}</span>
      {children}
    </div>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-label="Loading" aria-busy="true" className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-lg bg-(--line)" />
      ))}
    </div>
  );
}

export function Table({ head, rows }: { head: ReactNode[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-(--line) text-(--ink-2)">
            {head.map((h, i) => (
              <th key={i} scope="col" className={`py-1 pr-3 font-medium ${i ? "text-right" : "text-left"}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r} className="border-b border-(--line) last:border-0">
              {row.map((cell, i) =>
                i === 0 ? (
                  <th key={i} scope="row" className="py-1 pr-3 text-left font-normal">
                    {cell}
                  </th>
                ) : (
                  <td key={i} className="py-1 pr-3 text-right whitespace-nowrap">
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
