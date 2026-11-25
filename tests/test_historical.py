"""Tests for historical ratios (F2), hand-checkable on the fake company (revenue 900/1000/1200/1400)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from dcf import historical, loader
from helpers import fake_raw

ROOT = Path(__file__).resolve().parent.parent


def fake_snapshot() -> loader.Snapshot:
    return loader.build_snapshot("TEST.NS", fake_raw(), now=datetime(2026, 11, 26, tzinfo=UTC))


def test_growth_by_hand() -> None:
    h = historical.compute_historical(fake_snapshot())
    assert h.revenue == [900.0, 1000.0, 1200.0, 1400.0]
    assert h.revenue_growth[0] is None
    assert h.revenue_growth[1] == pytest.approx(1000 / 900 - 1)
    assert h.revenue_growth[3] == pytest.approx(1400 / 1200 - 1)


def test_margins_tax_capex_nwc_by_hand() -> None:
    h = historical.compute_historical(fake_snapshot())
    assert h.ebit_margin[3] == pytest.approx(0.25)
    assert h.ebitda_margin[3] == pytest.approx(0.28)
    assert h.tax_rate[3] == pytest.approx(0.25)  # tax = 0.27*0.25*rev, pretax = 0.27*rev
    assert h.da_pct[3] == pytest.approx(0.03)
    assert h.capex_pct[3] == pytest.approx(0.03)
    # NWC = receivables (0.2 rev) + inventory 10 - payables (0.05 rev) = 0.15*1400 + 10
    assert h.nwc[3] == pytest.approx(0.15 * 1400 + 10)
    assert h.nwc_pct[3] == pytest.approx((0.15 * 1400 + 10) / 1400)
    assert h.cash_conversion[3] == pytest.approx(0.22 / 0.2)
    assert h.fcf_proxy[3] == pytest.approx(0.22 * 1400 - 0.03 * 1400)


def test_summary_stats() -> None:
    h = historical.compute_historical(fake_snapshot())
    g = h.summary["revenue_growth"]
    assert g["n"] == 3
    assert g["min"] == pytest.approx(1000 / 900 - 1)
    assert g["latest"] == pytest.approx(1400 / 1200 - 1)
    assert g["mean"] == pytest.approx(
        ((1000 / 900 - 1) + (1200 / 1000 - 1) + (1400 / 1200 - 1)) / 3
    )


def test_missing_and_zero_values_do_not_crash() -> None:
    assert historical.revenue_growth([None, 100.0, 0.0, 50.0]) == [None, None, -1.0, None]
    assert historical.margin([1.0, None], [0.0, 10.0]) == [None, None]
    assert historical.effective_tax_rate([5.0], [-10.0]) == [None]
    assert historical.net_working_capital([10.0, None], [None, 1.0], [4.0, 2.0]) == [6.0, None]
    assert historical.summarize([None, None])["mean"] is None


def test_table_and_text_render() -> None:
    h = historical.compute_historical(fake_snapshot())
    rows = h.table()
    assert rows[0]["fiscal_year"] == "FY2023" and len(rows) == 4
    assert "EBIT margin" in historical.format_history(h)


def test_committed_tcs_snapshot_relations() -> None:
    """On real data: ratios must equal their definitions (no hard-coded numbers)."""
    snap = loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots")
    h = historical.compute_historical(snap)
    rev = snap["income"]["revenue"]
    assert h.revenue_growth[-1] == pytest.approx(rev["FY2026"] / rev["FY2025"] - 1)
    assert h.tax_rate[-1] == pytest.approx(
        snap["income"]["tax_provision"]["FY2026"] / snap["income"]["pretax_income"]["FY2026"]
    )
    assert 0.1 < h.ebit_margin[-1] < 0.4  # sanity band for an IT-services company
