"""Peer multiples (F15) and default-input assembly."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dcf import defaults, loader, peers, valuation
from dcf.exceptions import DataUnavailableError
from helpers import fake_raw

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 26, tzinfo=UTC)


def snap(ticker: str, mcap_crore: float, rev_scale: float = 1.0) -> loader.Snapshot:
    raw = fake_raw(revenue=[1400.0 * rev_scale, 1200.0, 1000.0, 900.0])
    raw["info"]["marketCap"] = mcap_crore * loader.CRORE
    return loader.build_snapshot(ticker, raw, now=NOW)


def test_multiples_by_hand() -> None:
    m = peers.company_multiples(snap("A.NS", 5600.0))
    # fake company: net income = 0.2 x 1400 = 280, EBITDA = 0.28 x 1400 = 392
    assert m.pe == pytest.approx(5600 / 280)
    # EV = mcap + debt 100 - cash 200 + minority 5
    assert m.enterprise_value == pytest.approx(5600 + 100 - 200 + 5)
    assert m.ev_ebitda == pytest.approx((5600 + 100 - 200 + 5) / 392)
    assert m.fetched_at.startswith("2026-11-26")


def test_peer_cross_check_medians_and_implied_values() -> None:
    subject = snap("TCS.NS", 4000.0)
    group = [snap("A.NS", 5600.0), snap("B.NS", 3920.0), snap("C.NS", 2800.0), subject]
    out = peers.peer_cross_check(subject, group, dcf_fair_value=33.0)
    assert [p["ticker"] for p in out["peers"]] == ["A.NS", "B.NS", "C.NS"]  # subject excluded
    assert out["median_pe"] == pytest.approx(14.0)  # 20, 14, 10 -> 14
    # value per share at median P/E: 14 x 280 crore / 10 crore shares
    assert out["value_per_share_at_median_pe"] == pytest.approx(14 * 280 / (100e6 / loader.CRORE))
    assert out["value_per_share_at_median_ev_ebitda"] is not None
    assert out["dcf_fair_value"] == 33.0 and "differ" in out["note"]
    with pytest.raises(DataUnavailableError):
        peers.peer_cross_check(subject, [subject])


def test_missing_peer_snapshot_is_skipped(tmp_path: Path) -> None:
    loader.save_snapshot(snap("A.NS", 5000.0), tmp_path)
    got = peers.load_peer_snapshots(tmp_path, ["A.NS", "MISSING.NS"])
    assert [g["ticker"] for g in got] == ["A.NS"]


def test_fade_path() -> None:
    assert defaults.fade(0.06, 0.04, 5) == pytest.approx((0.06, 0.055, 0.05, 0.045, 0.04))
    assert defaults.fade(0.06, 0.04, 1) == (0.06,)


def test_defaults_on_committed_tcs_snapshot() -> None:
    s = loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots")
    bundle = defaults.build_defaults(s, peers_dir=ROOT / "data" / "snapshots")
    i = bundle.inputs
    assert i.operating.base_revenue == s["income"]["revenue"][s["fiscal_years"][-1]]
    assert i.operating.revenue_growth[-1] == pytest.approx(i.terminal.growth)  # fades to terminal
    assert i.terminal.growth <= i.wacc.risk_free
    assert i.bridge.diluted_shares == pytest.approx(
        s["shares"]["diluted_average"][s["fiscal_years"][-1]] / loader.CRORE
    )
    assert i.terminal.exit_multiple is not None
    assert "peer" in bundle.sources["exit_multiple"]
    r = valuation.run_valuation(i)
    assert r.fair_value_per_share > 0 and r.terminal_value_share < 0.9
    assert all(src for src in bundle.sources.values())


def test_live_price_overrides_snapshot_price() -> None:
    s = loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots")
    b = defaults.build_defaults(s, price=1234.5)
    assert b.inputs.bridge.price == 1234.5


def test_defaults_fail_clearly_without_history() -> None:
    s = deepcopy(loader.load_snapshot("TCS.NS", ROOT / "data" / "snapshots"))
    for fy in s["fiscal_years"][:-1]:
        s["income"]["revenue"][fy] = None
    with pytest.raises(DataUnavailableError):
        defaults.build_defaults(s)
