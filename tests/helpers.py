"""Shared test fixtures: fake yfinance frames and a synthetic Screener-style workbook."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CR = 1e7  # frames are in rupees; the loader converts to crore

PERIODS = [pd.Timestamp(f"{y}-03-31") for y in (2026, 2025, 2024, 2023)]  # yfinance: newest first


def fake_raw(
    revenue: list[float] | None = None,
    drop_rows: tuple[str, ...] = (),
    currency: str = "INR",
) -> dict[str, Any]:
    """A fake yfinance payload (values in rupees) for a tiny company; crore values are exact."""
    rev = revenue or [1400.0, 1200.0, 1000.0, 900.0]  # crore, newest first
    inc = pd.DataFrame(
        {
            p: {
                "Total Revenue": r * CR,
                "Operating Income": r * 0.25 * CR,
                "Reconciled Depreciation": r * 0.03 * CR,
                "Interest Expense": 5 * CR,
                "Pretax Income": r * 0.27 * CR,
                "Tax Provision": r * 0.27 * 0.25 * CR,
                "Net Income Common Stockholders": r * 0.2 * CR,
                "Diluted Average Shares": 100e6,
            }
            for p, r in zip(PERIODS, rev, strict=True)
        }
    )
    bal = pd.DataFrame(
        {
            p: {
                "Accounts Receivable": r * 0.2 * CR,
                "Inventory": 10 * CR,
                "Accounts Payable": r * 0.05 * CR,
                "Total Debt": 100 * CR,
                "Capital Lease Obligations": 100 * CR,
                "Cash And Cash Equivalents": 50 * CR,
                "Other Short Term Investments": 150 * CR,
                "Cash Cash Equivalents And Short Term Investments": 200 * CR,
                "Minority Interest": 5 * CR,
                "Total Assets": r * 1.5 * CR,
                "Stockholders Equity": r * 0.8 * CR,
            }
            for p, r in zip(PERIODS, rev, strict=True)
        }
    )
    cf = pd.DataFrame(
        {
            p: {
                "Operating Cash Flow": r * 0.22 * CR,
                "Capital Expenditure": -r * 0.03 * CR,
                "Depreciation And Amortization": r * 0.03 * CR,
            }
            for p, r in zip(PERIODS, rev, strict=True)
        }
    )
    inc = inc.drop(index=[d for d in drop_rows if d in inc.index])
    n = 120
    idx = pd.date_range("2021-01-04", periods=n, freq="7D")
    rng = np.random.default_rng(1)
    mkt = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.002, 0.02, n))), index=idx)
    stk = pd.Series(
        50 * np.exp(np.cumsum(0.9 * np.diff(np.log(mkt), prepend=np.log(mkt.iloc[0])))), index=idx
    )
    daily_idx = pd.date_range("2026-01-01", periods=250, freq="B")
    daily = pd.DataFrame({"Close": np.linspace(900, 1000, 250)}, index=daily_idx)
    return {
        "income": inc,
        "balance": bal,
        "cashflow": cf,
        "daily_1y": daily,
        "weekly_5y": pd.DataFrame({"Close": stk}),
        "index_weekly_5y": pd.DataFrame({"Close": mkt}),
        "info": {"longName": "Test Co", "sharesOutstanding": 100e6, "marketCap": 1000 * CR * 100},
        "index_ticker": "^NSEI",
        "financial_currency": currency,
    }


def write_screener_sample(path: Path) -> None:
    """Write a synthetic workbook that mimics Screener.in's 'Data Sheet' layout."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data Sheet"
    dates = [datetime(y, 3, 31) for y in (2022, 2023, 2024, 2025)]
    rows: list[list[Any]] = [
        ["COMPANY NAME", "Sample Screener Co"],
        ["META"],
        ["Number of shares", 100.0],
        ["Current Price", 50.0],
        ["Market Capitalization", 5000.0],
        [],
        ["PROFIT & LOSS"],
        ["Report Date", *dates],
        ["Sales", 1000, 1100, 1210, 1331],
        ["Raw Material Cost", 100, 110, 121, 133],
        ["Change in Inventory", 0, 0, 0, 0],
        ["Power and Fuel", 0, 0, 0, 0],
        ["Other Mfr. Exp", 0, 0, 0, 0],
        ["Employee Cost", 400, 440, 484, 532],
        ["Selling and admin", 100, 110, 121, 133],
        ["Other Expenses", 100, 110, 121, 133],
        ["Other Income", 10, 10, 10, 10],
        ["Depreciation", 40, 44, 48, 53],
        ["Interest", 5, 5, 5, 5],
        ["Profit before tax", 265, 291, 321, 352],
        ["Tax", 66, 73, 80, 88],
        ["Net profit", 199, 218, 241, 264],
        [],
        ["BALANCE SHEET"],
        ["Report Date", *dates],
        ["Equity Share Capital", 10, 10, 10, 10],
        ["Borrowings", 50, 40, 30, 20],
        ["Total", 900, 1000, 1100, 1200],
        ["Net Block", 300, 330, 360, 400],
        ["Capital Work in Progress", 10, 10, 20, 20],
        ["Receivables", 150, 165, 180, 200],
        ["Inventory", 20, 22, 24, 26],
        ["Cash & Bank", 100, 120, 150, 180],
        [],
        ["CASH FLOW:"],
        ["Report Date", *dates],
        ["Cash from Operating Activity", 200, 220, 240, 262],
    ]
    for r in rows:
        ws.append(r)
    wb.save(path)
