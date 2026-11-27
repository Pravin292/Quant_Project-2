"""Tests for the data loader (F1): snapshot building, quality checks, Screener parser."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from dcf import loader
from dcf.exceptions import DataUnavailableError
from helpers import PERIODS, fake_raw, write_screener_sample

NOW = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)


def test_snapshot_converts_to_crore_and_orders_years() -> None:
    snap = loader.build_snapshot("TEST.NS", fake_raw(), now=NOW)
    assert snap["fiscal_years"] == ["FY2023", "FY2024", "FY2025", "FY2026"]
    assert snap["income"]["revenue"]["FY2026"] == pytest.approx(1400.0)
    assert snap["income"]["ebitda"]["FY2026"] == pytest.approx(1400 * 0.28)
    assert snap["cashflow"]["capex"]["FY2026"] == pytest.approx(1400 * 0.03)  # stored positive
    assert snap["balance"]["financial_debt"]["FY2026"] == pytest.approx(0.0)
    assert snap["balance"]["cash_and_investments"]["FY2026"] == pytest.approx(200.0)
    assert snap["provenance"]["income.revenue"] == "yfinance: Total Revenue"
    assert snap["fetched_at"].startswith("2026-11-26")


def test_weekly_prices_aligned() -> None:
    snap = loader.build_snapshot("TEST.NS", fake_raw(), now=NOW)
    w = snap["prices_weekly"]
    assert len(w["dates"]) == len(w["stock"]) == len(w["index"]) > 50


def test_empty_response_does_not_crash() -> None:
    raw = fake_raw()
    raw["income"] = pd.DataFrame()
    with pytest.raises(DataUnavailableError, match="No income statement"):
        loader.build_snapshot("TEST.NS", raw, now=NOW)
    with pytest.raises(DataUnavailableError):
        loader.build_snapshot("TEST.NS", {}, now=NOW)


def test_missing_required_field_stops_with_clear_message() -> None:
    raw = fake_raw(drop_rows=("Operating Income",))
    with pytest.raises(DataUnavailableError, match="operating_income"):
        loader.build_snapshot("TEST.NS", raw, now=NOW)


def test_missing_optional_field_warns_not_crashes() -> None:
    raw = fake_raw()
    raw["balance"] = raw["balance"].drop(index=["Accounts Payable"])
    snap = loader.build_snapshot("TEST.NS", raw, now=NOW)
    assert any("payables" in w for w in snap["quality_warnings"])


def test_negative_revenue_rejected() -> None:
    with pytest.raises(DataUnavailableError, match="not positive"):
        loader.build_snapshot("TEST.NS", fake_raw(revenue=[1400.0, -5.0, 1000.0, 900.0]), now=NOW)


def test_too_few_years_rejected() -> None:
    raw = fake_raw()
    raw["income"] = raw["income"].iloc[:, :2]
    with pytest.raises(DataUnavailableError, match="at least 3"):
        loader.build_snapshot("TEST.NS", raw, now=NOW)


def test_negative_operating_income_flagged() -> None:
    raw = fake_raw()
    raw["income"].loc["Operating Income", PERIODS[1]] = -1e9
    snap = loader.build_snapshot("TEST.NS", raw, now=NOW)
    assert any("negative operating_income" in w for w in snap["quality_warnings"])


def test_foreign_currency_converted_with_average_rate() -> None:
    raw = fake_raw(currency="USD")
    raw["info"]["marketCap"] = 1e9  # P/E on as-reported numbers is implausible -> really USD
    idx = pd.date_range("2020-01-01", "2026-12-31", freq="D")
    raw["fx_daily"] = pd.DataFrame({"Close": 80.0}, index=idx)
    snap = loader.build_snapshot("TEST.NS", raw, now=NOW)
    # frame values are "crore-scale rupees"; as USD they become x80 more crore
    assert snap["income"]["revenue"]["FY2026"] == pytest.approx(1400.0 * 80)
    assert "converted to INR" in snap["provenance"]["fx"]


def test_mislabelled_currency_not_converted() -> None:
    raw = fake_raw(currency="USD")
    raw["info"]["marketCap"] = 5.6e10  # market cap / net income = 20x -> already INR
    snap = loader.build_snapshot("TEST.NS", raw, now=NOW)
    assert snap["income"]["revenue"]["FY2026"] == pytest.approx(1400.0)
    assert "already in INR" in snap["provenance"]["fx"]


def test_snapshot_roundtrip_and_latest(tmp_path: Path) -> None:
    snap = loader.build_snapshot("TEST.NS", fake_raw(), now=NOW)
    path = loader.save_snapshot(snap, tmp_path)
    assert path.name == "TEST.NS_2026-11-26.json"
    older = dict(snap, fetched_at="2026-11-01T00:00:00+00:00")
    loader.save_snapshot(older, tmp_path)
    assert loader.load_snapshot("TEST.NS", tmp_path)["fetched_at"] == snap["fetched_at"]
    assert loader.list_snapshot_tickers(tmp_path) == ["TEST.NS"]
    json.loads(path.read_text())  # valid JSON
    with pytest.raises(DataUnavailableError):
        loader.load_snapshot("MISSING.NS", tmp_path)


def test_accessors() -> None:
    snap = loader.build_snapshot("TEST.NS", fake_raw(), now=NOW)
    assert loader.latest_value(snap, "income", "revenue") == pytest.approx(1400.0)
    shares, fy = loader.diluted_shares(snap)
    assert (shares, fy) == (100e6, "FY2026")


def test_live_price_falls_back_to_snapshot() -> None:
    snap = loader.build_snapshot("TEST.NS", fake_raw(), now=NOW)

    def boom(_: str) -> float:
        raise RuntimeError("rate limited")

    out = loader.fetch_live_price("TEST.NS", snap, fetcher=boom)
    assert out["fallback"] is True and out["price"] == snap["market"]["price"]
    ok = loader.fetch_live_price("TEST.NS", snap, fetcher=lambda _: 123.0)
    assert ok["price"] == 123.0 and ok["fallback"] is False
    with pytest.raises(DataUnavailableError):
        loader.fetch_live_price("TEST.NS", None, fetcher=boom)


def test_screener_parser(tmp_path: Path) -> None:
    f = tmp_path / "screener.xlsx"
    write_screener_sample(f)
    snap = loader.parse_screener_excel(f, "SAMPLE", now=NOW)
    assert snap["fiscal_years"] == ["FY2022", "FY2023", "FY2024", "FY2025"]
    assert snap["income"]["revenue"]["FY2025"] == 1331
    # EBITDA = sales - all operating expenses = 1331 - (133+532+133+133)
    assert snap["income"]["ebitda"]["FY2025"] == pytest.approx(400)
    assert snap["income"]["operating_income"]["FY2025"] == pytest.approx(400 - 53)
    # capex = delta net block + delta CWIP + depreciation = 40 + 0 + 53
    assert snap["cashflow"]["capex"]["FY2025"] == pytest.approx(93)
    assert snap["cashflow"]["capex"]["FY2022"] is None
    assert snap["market"]["price"] == 50.0
    assert loader.diluted_shares(snap)[0] == pytest.approx(100 * loader.CRORE)
    assert any("payables" in w for w in snap["quality_warnings"])


def test_screener_rejects_bad_upload(tmp_path: Path) -> None:
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.title = "Other"
    f = tmp_path / "bad.xlsx"
    wb.save(f)
    with pytest.raises(DataUnavailableError, match="Data Sheet"):
        loader.parse_screener_excel(f, "BAD", now=NOW)
    with pytest.raises(DataUnavailableError):
        loader.parse_screener_excel(b"not an excel file", "BAD", now=NOW)


def test_parse_fred_and_damodaran() -> None:
    rate, d = loader.parse_fred_series(
        b"observation_date,X\n2026-09-01,7.06\n2026-10-01,7.38\n2026-11-01,.\n"
    )
    assert rate == pytest.approx(0.0738) and d == "2026-10-01"
    with pytest.raises(DataUnavailableError):
        loader.parse_fred_series(b"observation_date,X\n2026-11-01,.\n")


def test_format_tables_runs() -> None:
    snap = loader.build_snapshot("TEST.NS", fake_raw(), now=NOW)
    text = loader.format_tables(snap)
    assert "INCOME STATEMENT" in text and "FY2026" in text


def test_prune_keeps_the_newest_snapshots(tmp_path: Path) -> None:
    for day in ("2026-01-01", "2026-01-03", "2026-01-02"):
        (tmp_path / f"TCS.NS_{day}.json").write_text("{}")
    (tmp_path / "INFY.NS_2026-01-01.json").write_text("{}")
    removed = loader.prune_snapshots("TCS.NS", tmp_path, keep=2)
    assert [p.name for p in removed] == ["TCS.NS_2026-01-01.json"]
    assert len(list(tmp_path.glob("*.json"))) == 3
    with pytest.raises(ValueError):
        loader.prune_snapshots("TCS.NS", tmp_path, keep=0)


def test_market_value_is_derived_when_yahoo_omits_it() -> None:
    raw = fake_raw()
    raw["info"] = {"sharesOutstanding": 100e6}
    snap = loader.build_snapshot("T", raw)
    assert snap["market"]["market_cap_crore"] == pytest.approx(1000 * 100e6 / 1e7)
    assert "close x shares" in snap["market"]["market_cap_source"]
    raw["info"] = {}  # nothing at all: use the statements' diluted share count
    snap = loader.build_snapshot("T", raw)
    assert snap["market"]["market_cap_crore"] == pytest.approx(1000 * 100e6 / 1e7)
    assert "diluted" in snap["market"]["market_cap_source"]


def test_info_fallback_keeps_slow_changing_facts() -> None:
    previous = loader.build_snapshot("T", fake_raw())
    facts = loader.info_fallback(previous)
    assert facts == {"longName": "Test Co", "financialCurrency": "INR", "sharesOutstanding": 100e6}
    assert loader.info_fallback(None) == {}
