/** Mirrors the JSON of the Python API (api/schemas.py and the engine dataclasses). */

export interface Assumptions {
  operating: {
    base_revenue: number;
    revenue_growth: number[];
    ebit_margin: number[];
    tax_rate: number;
    da_pct: number;
    capex_pct: number;
    nwc_pct: number;
  };
  wacc: {
    risk_free: number;
    beta: number;
    equity_risk_premium: number;
    cost_of_debt: number;
    debt_weight: number;
    tax_rate: number;
    sources?: Record<string, string>;
  };
  terminal: { growth: number; exit_multiple: number | null };
  bridge: {
    debt: number;
    leases: number;
    cash_and_investments: number;
    minority_interest: number;
    diluted_shares: number;
    price: number | null;
  };
  mid_year: boolean;
  wacc_override: number | null;
  context: {
    margin_min: number | null;
    margin_max: number | null;
    roic: number | null;
    fcf_proxy_latest: number | null;
  } | null;
  ticker: string | null;
}

export type ScenarioName = "bear" | "base" | "bull";

export interface Company {
  ticker: string;
  name: string;
  source: string;
  fetched_at: string;
  fiscal_years: string[];
  quality_warnings: string[];
}

export interface Defaults {
  company: Company;
  assumptions: Assumptions;
  sources: Record<string, string>;
  price: { price: number; as_of: string; source: string; fallback: boolean };
  week_52: { week52_low: number | null; week52_high: number | null };
  bounds: Record<string, [number, number]>;
  tickers: string[];
}

export interface Valuation {
  forecast: {
    base_revenue: number;
    revenue: number[];
    ebit: number[];
    nopat: number[];
    da: number[];
    capex: number[];
    delta_nwc: number[];
    fcff: number[];
  };
  wacc: { cost_of_equity: number; after_tax_cost_of_debt: number; wacc: number };
  wacc_used: number;
  discount_factors: number[];
  pv_fcff: number[];
  sum_pv_fcff: number;
  terminal_value: number;
  pv_terminal_value: number;
  enterprise_value: number;
  terminal_value_share: number | null;
  bridge: Record<
    | "enterprise_value"
    | "less_debt"
    | "less_leases"
    | "plus_cash_and_investments"
    | "less_minority_interest"
    | "equity_value",
    number
  >;
  equity_value: number;
  fair_value_per_share: number;
  price: number | null;
  upside: number | null;
  exit_cross_check: Record<string, number | null> | null;
  value_driver_cross_check: { fair_value_per_share: number } | null;
  warnings: { code: string; severity: string; message: string }[];
}

export interface Scenarios {
  scenarios: Record<
    ScenarioName,
    {
      fair_value_per_share: number;
      upside: number | null;
      probability: number;
      assumptions: Assumptions;
    }
  >;
  expected_fair_value: number;
  expected_upside: number | null;
}

export interface Historical {
  company: Company;
  years: ({ fiscal_year: string } & Record<string, number | null | string>)[];
  sources: Record<string, string>;
}

export interface Grid {
  column_label: string;
  columns: number[];
  row_label: string;
  rows: number[];
  values: (number | null)[][];
  centre: [number, number];
  base_fair_value: number;
}

export interface Sensitivity {
  wacc_growth: Grid;
  growth_margin: Grid;
}

export interface Tornado {
  base_fair_value: number;
  delta: number;
  rows: {
    name: string;
    low_input: number;
    high_input: number;
    fair_value_low_input: number | null;
    fair_value_high_input: number | null;
    swing: number;
  }[];
}

export interface ReverseDcf {
  status: string;
  implied_growth: number | null;
  message: string;
}
