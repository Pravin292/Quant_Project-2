"""Data loader (F1): yfinance fetch, Screener.in upload parser, dated JSON snapshots.

Every stored number carries its source and fetch date (``provenance`` and
``fetched_at``). All money values are stored in INR crore (1 crore = 1e7 INR);
share counts are plain counts. No company numbers are hard-coded here: every
figure comes from the data source.

Snapshot layout (schema_version 1)::

    {
      "schema_version": 1, "ticker": "TCS.NS", "name": "...", "unit": "INR crore",
      "source": "yfinance", "fetched_at": "2026-11-26T10:00:00+00:00",
      "fiscal_years": ["FY2023", ...],              # ascending
      "period_ends": {"FY2023": "2023-03-31", ...},
      "income":   {item: {fy: value_or_null}},
      "balance":  {item: {fy: value_or_null}},
      "cashflow": {item: {fy: value_or_null}},
      "shares":   {"diluted_average": {fy: count}},
      "provenance": {"income.revenue": "yfinance: Total Revenue", ...},
      "market": {"price", "price_date", "week52_high", "week52_low", ...},
      "prices_weekly": {"dates": [...], "stock": [...], "index": [...], "index_ticker": "^NSEI"},
      "quality_warnings": [...]
    }
"""

from __future__ import annotations

import io
import json
import math
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dcf.exceptions import DataUnavailableError

SCHEMA_VERSION = 1
CRORE = 1e7
if TYPE_CHECKING:  # pandas is only needed to build snapshots, not to serve the API
    import pandas as pd

Snapshot = dict[str, Any]

# Canonical item -> candidate yfinance row labels (first match wins).
YF_INCOME: dict[str, list[str]] = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    # Operating income excludes treasury "other income" (cash is added in the bridge)
    "operating_income": ["Operating Income"],
    "depreciation": [
        "Reconciled Depreciation",
        "Depreciation And Amortization In Income Statement",
    ],
    "interest_expense": ["Interest Expense"],
    "pretax_income": ["Pretax Income"],
    "tax_provision": ["Tax Provision"],
    "net_income": ["Net Income Common Stockholders", "Net Income"],
}
YF_BALANCE: dict[str, list[str]] = {
    "receivables": ["Accounts Receivable", "Receivables"],
    "inventory": ["Inventory"],
    "payables": ["Accounts Payable"],
    "total_debt": ["Total Debt"],
    "lease_liabilities": ["Capital Lease Obligations"],
    "cash_and_equivalents": ["Cash And Cash Equivalents"],
    "short_term_investments": ["Other Short Term Investments"],
    "cash_and_investments_total": ["Cash Cash Equivalents And Short Term Investments"],
    "minority_interest": ["Minority Interest"],
    "total_assets": ["Total Assets"],
    "equity": ["Stockholders Equity", "Common Stock Equity"],
}
YF_CASHFLOW: dict[str, list[str]] = {
    "operating_cash_flow": ["Operating Cash Flow"],
    "capex": ["Capital Expenditure"],  # reported negative; stored positive
    "depreciation_cf": ["Depreciation And Amortization"],
}
YF_SHARES: list[str] = ["Diluted Average Shares", "Basic Average Shares"]

REQUIRED_INCOME = ["revenue", "operating_income", "depreciation", "pretax_income", "tax_provision"]
MIN_YEARS = 3


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _clean(x: Any) -> float | None:
    """Return a finite float or None (NaN, inf, non-numeric)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def fy_label(period_end: date, fy_end_month: int = 3) -> str:
    """Fiscal year label named by the calendar year in which it ends: 2026-03-31 -> FY2026."""
    return (
        f"FY{period_end.year}" if period_end.month <= fy_end_month else f"FY{period_end.year + 1}"
    )


def _pick(df: pd.DataFrame | None, aliases: list[str], col: Any) -> tuple[float | None, str | None]:
    """First available value among row-label aliases for one column. Returns (value, label)."""
    if df is None or df.empty or col not in df.columns:
        return None, None
    for label in aliases:
        if label in df.index:
            v = _clean(df.at[label, col])
            if v is not None:
                return v, label
    return None, None


def _find_column(df: pd.DataFrame | None, period_end: Any) -> Any:
    import pandas as pd

    if df is None or df.empty:
        return None
    for c in df.columns:
        if pd.Timestamp(c) == pd.Timestamp(period_end):
            return c
    return None


# ---------------------------------------------------------------------------
# Fetching (network). Isolated so tests can inject fakes.
# ---------------------------------------------------------------------------
def fetch_yfinance(ticker: str, index_ticker: str = "^NSEI") -> dict[str, Any]:
    """Fetch raw statements, price history and market data for one ticker from yfinance."""
    import yfinance as yf  # local import: keeps module import light for the API

    t = yf.Ticker(ticker)
    try:
        raw: dict[str, Any] = {
            "income": t.income_stmt,
            "balance": t.balance_sheet,
            "cashflow": t.cashflow,
            "daily_1y": t.history(period="1y", interval="1d"),
            "weekly_5y": t.history(period="5y", interval="1wk"),
            "index_weekly_5y": yf.Ticker(index_ticker).history(period="5y", interval="1wk"),
            "info": dict(t.info or {}),
            "index_ticker": index_ticker,
        }
        currency = str(raw["info"].get("financialCurrency") or "INR").upper()
        raw["financial_currency"] = currency
        if currency != "INR":
            raw["fx_daily"] = yf.Ticker(f"{currency}INR=X").history(period="6y", interval="1d")
    except Exception as exc:  # network, rate-limit, parsing
        raise DataUnavailableError(
            f"Could not fetch data for {ticker} from yfinance: {exc}"
        ) from exc
    return raw


def fetch_live_price(
    ticker: str,
    fallback_snapshot: Snapshot | None = None,
    fetcher: Callable[[str], float] | None = None,
) -> dict[str, Any]:
    """Live share price for one request; falls back to the snapshot price if the fetch fails."""

    def _default(tk: str) -> float:
        import urllib.parse

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(tk)}?range=1d&interval=1d"
        payload = json.loads(_http_get(url, timeout=8, user_agent="Mozilla/5.0"))
        price = _clean(payload["chart"]["result"][0]["meta"].get("regularMarketPrice"))
        if price is None or price <= 0:
            raise ValueError("no price")
        return price

    try:
        price = (fetcher or _default)(ticker)
        return {
            "price": price,
            "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "Yahoo Finance chart API (live)",
            "fallback": False,
        }
    except Exception:
        if fallback_snapshot is None or not fallback_snapshot.get("market", {}).get("price"):
            raise DataUnavailableError(
                "Live price unavailable and no snapshot price to fall back on."
            ) from None
        m = fallback_snapshot["market"]
        return {
            "price": m["price"],
            "as_of": m.get("price_date") or fallback_snapshot.get("fetched_at"),
            "source": "snapshot (live fetch failed)",
            "fallback": True,
        }


# ---------------------------------------------------------------------------
# Snapshot construction
# ---------------------------------------------------------------------------
def _extract_section(
    df: pd.DataFrame | None,
    mapping: dict[str, list[str]],
    section: str,
    cols: dict[str, Any],
    provenance: dict[str, str],
    money: bool = True,
    flip_sign: tuple[str, ...] = (),
    rates: dict[str, float] | None = None,
) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for item, aliases in mapping.items():
        series: dict[str, float | None] = {}
        for fy, col in cols.items():
            v, label = _pick(df, aliases, col)
            if v is not None:
                if item in flip_sign:
                    v = abs(v)
                v = v * (rates[fy] if rates else 1.0) / CRORE if money else v
                provenance.setdefault(f"{section}.{item}", f"yfinance: {label}")
            series[fy] = v
        out[item] = series
    return out


def build_snapshot(
    ticker: str,
    raw: dict[str, Any],
    now: datetime | None = None,
    fy_end_month: int = 3,
) -> Snapshot:
    """Turn raw yfinance frames into a validated, dated snapshot. Raises DataUnavailableError."""
    import pandas as pd

    now = now or datetime.now(UTC)
    income = raw.get("income")
    if income is None or income.empty:
        raise DataUnavailableError(f"No income statement returned for {ticker}.")

    # Fiscal years come from the income statement columns that actually contain revenue
    period_cols: list[Any] = []
    for c in sorted(income.columns, key=pd.Timestamp):
        rev, _ = _pick(income, YF_INCOME["revenue"], c)
        if rev is not None:
            period_cols.append(c)
    if not period_cols:
        raise DataUnavailableError(f"Income statement for {ticker} has no revenue figures.")

    fiscal_years: list[str] = []
    period_ends: dict[str, str] = {}
    inc_cols: dict[str, Any] = {}
    bal_cols: dict[str, Any] = {}
    cf_cols: dict[str, Any] = {}
    for c in period_cols:
        pe = pd.Timestamp(c).date()
        fy = fy_label(pe, fy_end_month)
        fiscal_years.append(fy)
        period_ends[fy] = pe.isoformat()
        inc_cols[fy] = c
        bal_cols[fy] = _find_column(raw.get("balance"), c)
        cf_cols[fy] = _find_column(raw.get("cashflow"), c)

    provenance: dict[str, str] = {}
    currency = _effective_currency(raw, income, period_cols[-1], provenance)
    flow_rates, stock_rates = _fx_rates(raw.get("fx_daily"), period_ends, fy_end_month, currency)
    if currency != "INR":
        provenance["fx"] = (
            f"Statements reported in {currency}; converted to INR at the fiscal-year average "
            f"{currency}INR rate (income, cash flow) and period-end rate (balance sheet), "
            "source: yfinance"
        )
    inc = _extract_section(income, YF_INCOME, "income", inc_cols, provenance, rates=flow_rates)
    bal = _extract_section(
        raw.get("balance"), YF_BALANCE, "balance", bal_cols, provenance, rates=stock_rates
    )
    cf = _extract_section(
        raw.get("cashflow"),
        YF_CASHFLOW,
        "cashflow",
        cf_cols,
        provenance,
        flip_sign=("capex",),
        rates=flow_rates,
    )
    shares = _extract_section(
        income, {"diluted_average": YF_SHARES}, "shares", inc_cols, provenance, money=False
    )

    # Derived items (flagged as derived in provenance)
    inc["ebitda"] = {}
    for fy in fiscal_years:
        oi, da = inc["operating_income"][fy], inc["depreciation"][fy]
        inc["ebitda"][fy] = oi + da if oi is not None and da is not None else None
    provenance["income.ebitda"] = "derived: operating_income + depreciation"
    bal["financial_debt"] = {}
    bal["cash_and_investments"] = {}
    for fy in fiscal_years:
        td, ll = bal["total_debt"][fy], bal["lease_liabilities"][fy]
        bal["financial_debt"][fy] = (td - (ll or 0.0)) if td is not None else None
        combined = bal["cash_and_investments_total"][fy]
        c_, s_ = bal["cash_and_equivalents"][fy], bal["short_term_investments"][fy]
        bal["cash_and_investments"][fy] = (
            combined
            if combined is not None
            else ((c_ or 0.0) + (s_ or 0.0) if c_ is not None else None)
        )
    provenance["balance.financial_debt"] = "derived: total_debt - lease_liabilities"
    provenance["balance.cash_and_investments"] = (
        "yfinance: Cash Cash Equivalents And Short Term Investments (cash + short-term investments)"
    )

    # Market data and price history for beta
    market, weekly = _market_and_prices(raw, now)

    snap: Snapshot = {
        "schema_version": SCHEMA_VERSION,
        "ticker": ticker,
        "name": raw.get("info", {}).get("longName")
        or raw.get("info", {}).get("shortName")
        or ticker,
        "currency": "INR",
        "financial_currency": currency,
        "unit": "INR crore",
        "source": "yfinance",
        "fetched_at": now.isoformat(timespec="seconds"),
        "fiscal_year_end_month": fy_end_month,
        "fiscal_years": fiscal_years,
        "period_ends": period_ends,
        "income": inc,
        "balance": bal,
        "cashflow": cf,
        "shares": shares,
        "provenance": provenance,
        "market": market,
        "prices_weekly": weekly,
        "info": _trim_info(raw.get("info", {})),
    }
    snap["quality_warnings"] = check_quality(snap)
    return snap


def _effective_currency(
    raw: dict[str, Any], income: pd.DataFrame, last_col: Any, provenance: dict[str, str]
) -> str:
    """Reporting currency, guarding against wrong labels (e.g. HCLTech is labelled USD but is INR).

    If the label says non-INR but market cap (INR) divided by net income as-reported gives a
    plausible P/E (3x-150x), the figures must already be in INR.
    """
    label = str(raw.get("financial_currency") or "INR").upper()
    if label == "INR":
        return "INR"
    ni, _ = _pick(income, YF_INCOME["net_income"], last_col)
    mcap = _clean((raw.get("info") or {}).get("marketCap"))
    if ni and ni > 0 and mcap and 3 <= mcap / ni <= 150:
        provenance["fx"] = (
            f"Yahoo labels the statements {label} but market cap / net income "
            f"({mcap / ni:.0f}x) shows they are already in INR; no conversion applied."
        )
        return "INR"
    return label


def _fx_rates(
    fx: pd.DataFrame | None, period_ends: dict[str, str], fy_end_month: int, currency: str
) -> tuple[dict[str, float] | None, dict[str, float] | None]:
    """Per-fiscal-year (average, period-end) conversion rates into INR; None when already INR."""
    import pandas as pd

    if currency == "INR":
        return None, None
    if fx is None or fx.empty:
        raise DataUnavailableError(
            f"Statements are in {currency} but no {currency}INR rates were returned."
        )
    close = fx["Close"].dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    flow: dict[str, float] = {}
    stock: dict[str, float] = {}
    for fy, end in period_ends.items():
        end_ts = pd.Timestamp(end)
        window = close[(close.index > end_ts - pd.DateOffset(years=1)) & (close.index <= end_ts)]
        at_end = close[close.index <= end_ts]
        if window.empty or at_end.empty:
            raise DataUnavailableError(f"No {currency}INR rates cover {fy}.")
        flow[fy] = float(window.mean())
        stock[fy] = float(at_end.iloc[-1])
    return flow, stock


def _trim_info(info: dict[str, Any]) -> dict[str, Any]:
    keep = ["sector", "industry", "trailingEps", "trailingPE", "forwardPE", "bookValue"]
    return {k: info[k] for k in keep if k in info and info[k] is not None}


def _market_and_prices(raw: dict[str, Any], now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    import pandas as pd

    info = raw.get("info", {}) or {}
    daily = raw.get("daily_1y")
    market: dict[str, Any] = {"source": "yfinance", "fetched_at": now.isoformat(timespec="seconds")}
    if daily is not None and not daily.empty:
        close = daily["Close"].dropna()
        market["price"] = _clean(close.iloc[-1])
        market["price_date"] = pd.Timestamp(close.index[-1]).date().isoformat()
        market["week52_high"] = _clean(close.max())
        market["week52_low"] = _clean(close.min())
    else:
        market["price"] = _clean(info.get("currentPrice") or info.get("regularMarketPrice"))
        market["price_date"] = now.date().isoformat()
    market["shares_outstanding"] = _clean(info.get("sharesOutstanding"))
    mc = _clean(info.get("marketCap"))
    market["market_cap_crore"] = mc / CRORE if mc is not None else None

    weekly: dict[str, Any] = {
        "dates": [],
        "stock": [],
        "index": [],
        "index_ticker": raw.get("index_ticker"),
    }
    s, i = raw.get("weekly_5y"), raw.get("index_weekly_5y")
    if s is not None and i is not None and not s.empty and not i.empty:
        sc = s["Close"].copy()
        ic = i["Close"].copy()
        sc.index = pd.to_datetime(sc.index).tz_localize(None).normalize()
        ic.index = pd.to_datetime(ic.index).tz_localize(None).normalize()
        joined = pd.concat({"s": sc, "i": ic}, axis=1).dropna()
        weekly["dates"] = [d.date().isoformat() for d in joined.index]
        weekly["stock"] = [float(v) for v in joined["s"]]
        weekly["index"] = [float(v) for v in joined["i"]]
    return market, weekly


# ---------------------------------------------------------------------------
# Data-quality checks
# ---------------------------------------------------------------------------
def check_quality(snap: Snapshot) -> list[str]:
    """Return non-fatal warnings; raise DataUnavailableError on fatal problems."""
    warnings: list[str] = []
    years: list[str] = snap["fiscal_years"]
    if len(years) < MIN_YEARS:
        raise DataUnavailableError(
            f"Only {len(years)} fiscal year(s) of data for {snap['ticker']}; at least {MIN_YEARS} needed."
        )
    latest = years[-1]
    inc = snap["income"]
    for item in REQUIRED_INCOME:
        if inc[item].get(latest) is None:
            raise DataUnavailableError(
                f"Required field '{item}' is missing for {latest} in {snap['ticker']}. "
                "Upload a Screener.in Excel export instead."
            )
    for fy in years:
        rev = inc["revenue"].get(fy)
        if rev is not None and rev <= 0:
            raise DataUnavailableError(
                f"Revenue for {fy} is not positive ({rev}); data looks corrupt."
            )
        pbt, tax = inc["pretax_income"].get(fy), inc["tax_provision"].get(fy)
        if pbt and tax is not None and pbt > 0 and not 0 <= tax / pbt <= 0.6:
            warnings.append(f"{fy}: effective tax rate {tax / pbt:.1%} is outside 0-60%.")
        capex = snap["cashflow"]["capex"].get(fy)
        if capex is None:
            warnings.append(f"{fy}: capital expenditure missing.")
        for item in ("receivables", "payables"):
            if snap["balance"][item].get(fy) is None:
                warnings.append(f"{fy}: balance-sheet item '{item}' missing.")
        for sect, item in (("income", "operating_income"), ("balance", "total_assets")):
            v = snap[sect][item].get(fy)
            if v is not None and v < 0:
                warnings.append(f"{fy}: negative {item} ({v:,.0f}).")
    if not snap["market"].get("price"):
        warnings.append("No share price in the snapshot; a live price will be required.")
    if not snap["shares"]["diluted_average"].get(latest):
        warnings.append(
            f"Diluted share count missing for {latest}; shares_outstanding will be used."
        )
    if not snap["prices_weekly"]["dates"]:
        warnings.append("No weekly price history; beta cannot be computed by regression.")
    return warnings


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------
def snapshot_path(ticker: str, directory: str | Path, when: date | None = None) -> Path:
    d = (when or datetime.now(UTC).date()).isoformat()
    return Path(directory) / f"{ticker}_{d}.json"


def save_snapshot(snap: Snapshot, directory: str | Path) -> Path:
    path = snapshot_path(
        snap["ticker"], directory, datetime.fromisoformat(snap["fetched_at"]).date()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=1, sort_keys=False))
    return path


def latest_snapshot_path(ticker: str, directory: str | Path) -> Path:
    files = sorted(Path(directory).glob(f"{ticker}_*.json"))
    if not files:
        raise DataUnavailableError(f"No snapshot found for {ticker} in {directory}.")
    return files[-1]


def load_snapshot(ticker: str, directory: str | Path) -> Snapshot:
    path = latest_snapshot_path(ticker, directory)
    snap: Snapshot = json.loads(path.read_text())
    if snap.get("schema_version") != SCHEMA_VERSION:
        raise DataUnavailableError(f"Snapshot {path.name} has an unsupported schema version.")
    return snap


def prune_snapshots(ticker: str, directory: str | Path, keep: int) -> list[Path]:
    """Delete all but the newest ``keep`` dated snapshots of a ticker."""
    if keep < 1:
        raise ValueError("At least one snapshot must be kept.")
    old = sorted(Path(directory).glob(f"{ticker}_*.json"))[:-keep]
    for path in old:
        path.unlink()
    return old


def list_snapshot_tickers(directory: str | Path) -> list[str]:
    return sorted({p.name.rsplit("_", 1)[0] for p in Path(directory).glob("*_*.json")})


# ---------------------------------------------------------------------------
# Accessors used by the other engine modules
# ---------------------------------------------------------------------------
def series(snap: Snapshot, section: str, item: str) -> dict[str, float | None]:
    return {fy: snap[section][item].get(fy) for fy in snap["fiscal_years"]}


def latest_value(snap: Snapshot, section: str, item: str) -> float | None:
    """Most recent non-null value of an item."""
    for fy in reversed(snap["fiscal_years"]):
        v = snap[section][item].get(fy)
        if v is not None:
            return float(v)
    return None


def diluted_shares(snap: Snapshot) -> tuple[float, str]:
    """Latest diluted share count (units) and the fiscal year it comes from."""
    for fy in reversed(snap["fiscal_years"]):
        v = snap["shares"]["diluted_average"].get(fy)
        if v:
            return float(v), fy
    so = snap["market"].get("shares_outstanding")
    if so:
        return float(so), "market data"
    raise DataUnavailableError("No share count available.")


# ---------------------------------------------------------------------------
# Screener.in Excel upload (fallback)
# ---------------------------------------------------------------------------
_SCREENER_EXPENSES = [
    "Raw Material Cost",
    "Change in Inventory",
    "Power and Fuel",
    "Other Mfr. Exp",
    "Employee Cost",
    "Selling and admin",
    "Other Expenses",
]


def parse_screener_excel(
    source: str | Path | bytes, ticker: str, now: datetime | None = None
) -> Snapshot:
    """Parse a Screener.in 'Data Sheet' export into the same snapshot schema.

    Screener reports in INR crore already. Limits (recorded as quality warnings):
    no lease split (Borrowings treated as financial debt), no payables line,
    no minority interest, CapEx derived as change in net block + CWIP + depreciation.
    """
    import openpyxl

    now = now or datetime.now(UTC)
    handle = io.BytesIO(source) if isinstance(source, bytes) else source
    try:
        wb = openpyxl.load_workbook(handle, data_only=True)
    except Exception as exc:
        raise DataUnavailableError(f"Could not open the uploaded Excel file: {exc}") from exc
    sheet = next((n for n in wb.sheetnames if n.strip().lower() == "data sheet"), None)
    if sheet is None:
        raise DataUnavailableError(
            "The upload has no 'Data Sheet' tab; use the Screener.in export."
        )
    rows = [list(r) for r in wb[sheet].iter_rows(values_only=True)]

    sections: dict[str, dict[str, list[Any]]] = {}
    dates: dict[str, list[Any]] = {}
    current = ""
    for row in rows:
        label = str(row[0]).strip() if row and row[0] is not None else ""
        up = label.upper()
        if up.startswith("PROFIT & LOSS"):
            current = "pl"
        elif up.startswith("BALANCE SHEET"):
            current = "bs"
        elif up.startswith("CASH FLOW"):
            current = "cf"
        elif up.startswith("QUARTERS") or up.startswith("PRICE") or up.startswith("DERIVED"):
            current = ""
        elif label == "Report Date" and current:
            dates[current] = row[1:]
        elif current and label:
            sections.setdefault(current, {}).setdefault(label, row[1:])
    if "pl" not in dates or "Sales" not in sections.get("pl", {}):
        raise DataUnavailableError("Could not find the profit & loss block (Report Date / Sales).")

    cols = [i for i, d in enumerate(dates["pl"]) if isinstance(d, (datetime, date))]
    fiscal_years: list[str] = []
    period_ends: dict[str, str] = {}
    for i in cols:
        d = dates["pl"][i]
        d = d.date() if isinstance(d, datetime) else d
        fy = fy_label(d)
        fiscal_years.append(fy)
        period_ends[fy] = d.isoformat()

    def get(sec: str, label: str) -> list[float | None]:
        r = sections.get(sec, {}).get(label)
        return [_clean(r[i]) if r is not None and i < len(r) else None for i in cols]

    pl = {
        k: get("pl", k)
        for k in [
            "Sales",
            "Other Income",
            "Depreciation",
            "Interest",
            "Profit before tax",
            "Tax",
            "Net profit",
        ]
    }
    exp = {k: get("pl", k) for k in _SCREENER_EXPENSES}
    bs = {
        k: get("bs", k)
        for k in [
            "Borrowings",
            "Net Block",
            "Capital Work in Progress",
            "Receivables",
            "Inventory",
            "Cash & Bank",
            "Total",
        ]
    }
    cfo = get("cf", "Cash from Operating Activity")

    def per_year(vals: list[float | None]) -> dict[str, float | None]:
        return dict(zip(fiscal_years, vals, strict=True))

    ebitda: list[float | None] = []
    for j in range(len(cols)):
        if pl["Sales"][j] is None:
            ebitda.append(None)
            continue
        ebitda.append(pl["Sales"][j] - sum(exp[k][j] or 0.0 for k in _SCREENER_EXPENSES))  # type: ignore[operator]
    dep = pl["Depreciation"]
    ebit = [(e - (d or 0.0)) if e is not None else None for e, d in zip(ebitda, dep, strict=True)]
    capex: list[float | None] = [None]
    nb, cwip = bs["Net Block"], bs["Capital Work in Progress"]
    for j in range(1, len(cols)):
        if None in (nb[j], nb[j - 1], dep[j]):
            capex.append(None)
        else:
            capex.append(nb[j] - nb[j - 1] + (cwip[j] or 0.0) - (cwip[j - 1] or 0.0) + dep[j])  # type: ignore[operator]

    meta = {str(r[0]).strip(): r[1] for r in rows if r and r[0] is not None and len(r) > 1}
    price = _clean(meta.get("Current Price"))
    sh = _clean(meta.get("Number of shares"))
    if sh is not None and sh < 1e6:  # Screener sometimes gives crores of shares
        sh *= CRORE
    mcap = _clean(meta.get("Market Capitalization"))

    zero = {fy: 0.0 for fy in fiscal_years}
    none = {fy: None for fy in fiscal_years}
    src = "screener.in upload"
    snap: Snapshot = {
        "schema_version": SCHEMA_VERSION,
        "ticker": ticker,
        "name": str(meta.get("COMPANY NAME") or ticker),
        "currency": "INR",
        "unit": "INR crore",
        "source": src,
        "fetched_at": now.isoformat(timespec="seconds"),
        "fiscal_year_end_month": 3,
        "fiscal_years": fiscal_years,
        "period_ends": period_ends,
        "income": {
            "revenue": per_year(pl["Sales"]),
            "operating_income": per_year(ebit),
            "depreciation": per_year(dep),
            "interest_expense": per_year(pl["Interest"]),
            "pretax_income": per_year(pl["Profit before tax"]),
            "tax_provision": per_year(pl["Tax"]),
            "net_income": per_year(pl["Net profit"]),
            "ebitda": per_year(ebitda),
        },
        "balance": {
            "receivables": per_year(bs["Receivables"]),
            "inventory": per_year(bs["Inventory"]),
            "payables": dict(zero),  # not in the export; see the quality warning
            "total_debt": per_year(bs["Borrowings"]),
            "lease_liabilities": dict(zero),
            "financial_debt": per_year(bs["Borrowings"]),
            "cash_and_equivalents": per_year(bs["Cash & Bank"]),
            "short_term_investments": dict(none),
            "cash_and_investments": per_year(bs["Cash & Bank"]),
            "minority_interest": dict(zero),
            "total_assets": per_year(bs["Total"]),
            "equity": dict(none),
        },
        "cashflow": {
            "operating_cash_flow": per_year(cfo),
            "capex": per_year(capex),
            "depreciation_cf": per_year(dep),
        },
        "shares": {
            "diluted_average": {fy: (sh if fy == fiscal_years[-1] else None) for fy in fiscal_years}
        },
        "provenance": {
            "income.revenue": f"{src}: Sales",
            "income.operating_income": f"{src}: Sales - operating expenses - Depreciation (derived)",
            "balance.cash_and_investments": f"{src}: Cash & Bank (investments not split out)",
            "cashflow.capex": f"{src}: derived from change in Net Block + CWIP + Depreciation",
        },
        "market": {
            "price": price,
            "price_date": now.date().isoformat(),
            "market_cap_crore": mcap,
            "shares_outstanding": sh,
            "source": src,
            "fetched_at": now.isoformat(timespec="seconds"),
        },
        "prices_weekly": {"dates": [], "stock": [], "index": [], "index_ticker": None},
        "info": {},
    }
    snap["quality_warnings"] = [
        "Screener upload: payables, minority interest and lease split are not available "
        "(all set to 0, so working capital is receivables plus inventory).",
        "CapEx is derived from the change in net block, CWIP and depreciation.",
        *check_quality(snap),
    ]
    return snap


# ---------------------------------------------------------------------------
# Printing (milestone M2 check: compare with the annual report)
# ---------------------------------------------------------------------------
def format_tables(snap: Snapshot) -> str:
    """Readable text tables of the key statement lines in INR crore."""
    years = snap["fiscal_years"]
    lines = [
        f"{snap['name']} ({snap['ticker']})  source: {snap['source']}  fetched: {snap['fetched_at']}",
        f"Values in {snap['unit']}",
        "",
    ]
    header = f"{'':32}" + "".join(f"{fy:>14}" for fy in years)
    for section, title in (
        ("income", "INCOME STATEMENT"),
        ("balance", "BALANCE SHEET"),
        ("cashflow", "CASH FLOW"),
    ):
        lines += [title, header]
        for item, vals in snap[section].items():
            if item == "cash_and_investments_total":
                continue
            cells = "".join(
                f"{'n/a':>14}" if vals.get(fy) is None else f"{vals[fy]:>14,.0f}" for fy in years
            )
            lines.append(f"{item:32}{cells}")
        lines.append("")
    if snap.get("quality_warnings"):
        lines.append("DATA-QUALITY WARNINGS")
        lines += [f"  - {w}" for w in snap["quality_warnings"]]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Macro inputs fetched at build time (never typed from memory)
# ---------------------------------------------------------------------------
FRED_INDIA_10Y = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=INDIRLTLT01STM"
DAMODARAN_ERP = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"


def _http_get(url: str, timeout: int = 60, user_agent: str = "dcf-valuation-app") -> bytes:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    last: Exception | None = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed URLs)
                data: bytes = resp.read()
            return data
        except Exception as exc:
            last = exc
    raise DataUnavailableError(f"Could not download {url}: {last}")


def parse_fred_series(csv_bytes: bytes) -> tuple[float, str]:
    """Latest non-empty value (percent -> decimal) and its date from a FRED CSV."""
    import pandas as pd

    frame = pd.read_csv(io.BytesIO(csv_bytes))
    frame.columns = ["date", "value"]
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna()
    if frame.empty:
        raise DataUnavailableError("FRED returned no data points for the India 10-year yield.")
    last = frame.iloc[-1]
    return float(last["value"]) / 100.0, str(last["date"])


def parse_damodaran_erp(xlsx_bytes: bytes, country: str = "India") -> tuple[float, float, str]:
    """(total equity risk premium, country risk premium, update date) for a country."""
    import warnings

    import openpyxl
    import pandas as pd

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    ws = wb["ERPs by country"]
    update = ""
    for row in wb["ERPs by country"].iter_rows(min_row=1, max_row=3, values_only=True):
        if row and row[0] and str(row[0]).startswith("Date of update") and row[1] is not None:
            update = pd.Timestamp(row[1]).date().isoformat()
    for row in ws.iter_rows(values_only=True):
        if row and row[0] == country:
            total, crp = _clean(row[4]), _clean(row[5])
            if total is None or crp is None:
                break
            return total, crp, update
    raise DataUnavailableError(f"Country '{country}' not found in the Damodaran dataset.")


def fetch_macro_inputs(now: datetime | None = None) -> dict[str, Any]:
    """Risk-free rate (FRED/OECD India 10y) and equity risk premium (Damodaran), with sources."""
    now = now or datetime.now(UTC)
    macro: dict[str, Any] = {}
    try:
        rf, rf_date = parse_fred_series(
            # FRED stalls requests from generic python user agents but serves curl-style ones
            _http_get(FRED_INDIA_10Y, timeout=30, user_agent="curl/8.4.0")
        )
        macro["risk_free"] = {
            "value": rf,
            "as_of": rf_date,
            "source": "FRED INDIRLTLT01STM (OECD long-term government bond yield, India, monthly)",
            "fetched_at": now.isoformat(timespec="seconds"),
        }
    except Exception as exc:
        macro["risk_free_error"] = str(exc)
    try:
        total, crp, upd = parse_damodaran_erp(_http_get(DAMODARAN_ERP))
        macro["equity_risk_premium"] = {
            "value": total,
            "country_risk_premium": crp,
            "as_of": upd,
            "source": "Damodaran country risk dataset (ctryprem.xlsx), India total ERP",
            "fetched_at": now.isoformat(timespec="seconds"),
        }
    except Exception as exc:
        macro["equity_risk_premium_error"] = str(exc)
    return macro
