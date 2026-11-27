/** F23: the whole valuation lives in the URL fragment, which never reaches the server. */
import type { Assumptions, ScenarioName } from "./types";

export interface Shared {
  assumptions: Assumptions;
  scenario: ScenarioName;
}

export function encodeShare({ assumptions, scenario }: Shared): string {
  const wacc = { ...assumptions.wacc };
  delete wacc.sources; // long text; restored from the defaults on load
  const json = JSON.stringify({ v: 1, s: scenario, a: { ...assumptions, wacc } });
  const bytes = new TextEncoder().encode(json);
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

const isNumber = (v: unknown) => typeof v === "number" && Number.isFinite(v);

/** True when ``value`` has the same shape as ``template`` (nulls may be numbers or null). */
function sameShape(value: unknown, template: unknown): boolean {
  if (template === null) return value === null || typeof value === "object" || isNumber(value);
  if (Array.isArray(template)) {
    return Array.isArray(value) && value.length === template.length && value.every(isNumber);
  }
  if (typeof template === "object") {
    if (typeof value !== "object" || value === null) return false;
    const record = value as Record<string, unknown>;
    return Object.entries(template as Record<string, unknown>).every(
      ([k, t]) => k === "sources" || sameShape(record[k], t),
    );
  }
  if (typeof template === "number") return value === null || isNumber(value);
  return typeof value === typeof template;
}

export function decodeShare(text: string): { s: ScenarioName; a: Assumptions } | null {
  try {
    const binary = atob(text.replaceAll("-", "+").replaceAll("_", "/"));
    const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
    const data = JSON.parse(new TextDecoder().decode(bytes));
    if (data?.v !== 1 || !["bear", "base", "bull"].includes(data.s)) return null;
    if (typeof data.a?.ticker !== "string" || !data.a.operating) return null;
    return { s: data.s, a: data.a as Assumptions };
  } catch {
    return null;
  }
}

export function matchesDefaults(shared: Assumptions, defaults: Assumptions): boolean {
  return sameShape(shared, defaults);
}
