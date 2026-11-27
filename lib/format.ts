const number = (digits: number) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export const num = (v: unknown, digits = 0) => (finite(v) ? number(digits).format(v + 0 === 0 ? 0 : v) : "n/a");
export const rupees = (v: unknown, digits = 0) => (finite(v) ? `₹${num(v, digits)}` : "n/a");
export const crore = (v: unknown) => (finite(v) ? `₹${num(v)} cr` : "n/a");
export const pct = (v: unknown, digits = 1) => (finite(v) ? `${(v * 100).toFixed(digits)}%` : "n/a");
export const signedPct = (v: unknown, digits = 1) =>
  finite(v) ? `${v > 0 ? "+" : ""}${pct(v, digits)}` : "n/a";
export const day = (iso: string | null | undefined) => (iso ? iso.slice(0, 10) : "n/a");
