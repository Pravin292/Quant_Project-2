"""API tests (M10): every endpoint, valid and invalid input."""

from __future__ import annotations

import io
from collections.abc import Iterator
from typing import Any

import openpyxl
import pytest
from api import index, middleware, service
from fastapi.testclient import TestClient

from conftest import chai_dict
from dcf import loader
from dcf.config import load_config


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No network in tests: the live quote always falls back to the snapshot price."""

    def fake(ticker: str, snap: Any = None, fetcher: Any = None) -> dict[str, Any]:
        def boom(_: str) -> float:
            raise OSError("offline")

        return real(ticker, snap, boom)

    real = loader.fetch_live_price
    monkeypatch.setattr(loader, "fetch_live_price", fake)
    service._PRICE_CACHE.clear()
    index._CACHE.clear()
    middleware.reset_rate_limit()
    yield


client = TestClient(index.app)


def chai_body() -> dict[str, Any]:
    d = chai_dict()
    keys = ("operating", "wacc", "terminal", "bridge")
    body: dict[str, Any] = {k: dict(d[k]) for k in keys}
    body["mid_year"] = d.get("mid_year", False)
    return body


def tcs() -> dict[str, Any]:
    out: dict[str, Any] = client.get("/api/defaults").json()["assumptions"]
    return out


def test_chai_corner_returns_26_8() -> None:
    r = client.post("/api/valuation", json=chai_body())
    assert r.status_code == 200, r.text
    assert round(r.json()["fair_value_per_share"], 1) == 26.8


def test_defaults_round_trip_into_valuation() -> None:
    d = client.get("/api/defaults?ticker=TCS.NS").json()
    assert d["price"]["fallback"] is True
    assert d["sources"]["bridge"]
    r = client.post("/api/valuation", json=d["assumptions"])
    assert r.status_code == 200, r.text
    assert r.json()["fair_value_per_share"] > 0
    assert r.json()["price"] == d["price"]["price"]


def test_get_endpoints() -> None:
    h = client.get("/api/historical").json()
    assert len(h["years"]) >= 3 and h["summary"]["ebit_margin"]["mean"]
    assert 0 < client.get("/api/beta").json()["beta"]["raw"] < 3
    p = client.get("/api/peers").json()
    assert p["median_pe"] and all(row["fetched_at"] for row in p["peers"])


@pytest.mark.parametrize("ticker", ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"])
def test_every_peer_ticker_values(ticker: str) -> None:
    d = client.get(f"/api/defaults?ticker={ticker}")
    assert d.status_code == 200, d.text
    r = client.post("/api/valuation", json=d.json()["assumptions"])
    assert r.status_code == 200, r.text


def test_analysis_endpoints() -> None:
    a = tcs()
    base = client.post("/api/valuation", json=a).json()["fair_value_per_share"]
    s = client.post("/api/sensitivity", json=a).json()
    for grid in s.values():
        row, col = grid["centre"]
        assert grid["values"][row][col] == pytest.approx(base)
    t = client.post("/api/tornado", json={"assumptions": a}).json()
    swings = [row["swing"] for row in t["rows"]]
    assert swings == sorted(swings, reverse=True)
    sc = client.post("/api/scenarios", json={"assumptions": a}).json()
    values = [sc["scenarios"][n]["fair_value_per_share"] for n in ("bear", "base", "bull")]
    assert values[0] < values[1] < values[2] and values[1] == pytest.approx(base)
    mc = client.post("/api/montecarlo", json={"assumptions": a}).json()
    assert mc["runs"] == 10_000
    assert mc["percentiles"]["p5"] < base < mc["percentiles"]["p95"]
    rev = client.post("/api/reverse-dcf", json={"assumptions": a}).json()
    assert rev["status"] == "solved"


def test_export_returns_workbook() -> None:
    r = client.post("/api/export", json={"assumptions": tcs()})
    assert r.status_code == 200
    assert "TCS.NS_dcf.xlsx" in r.headers["content-disposition"]
    assert "Valuation" in openpyxl.load_workbook(io.BytesIO(r.content)).sheetnames


def test_results_are_cached() -> None:
    first = client.post("/api/valuation", json=chai_body())
    second = client.post("/api/valuation", json=chai_body())
    assert (first.headers["x-cache"], second.headers["x-cache"]) == ("miss", "hit")
    assert first.json() == second.json()


@pytest.mark.parametrize(
    ("section", "field", "value", "words"),
    [
        ("bridge", "diluted_shares", -1, "shares"),
        ("terminal", "growth", 0.08, "growth"),
        ("operating", "tax_rate", 0.9, "Tax rate"),
        ("wacc", "beta", 9, "Beta"),
    ],
)
def test_invalid_inputs_get_plain_422(section: str, field: str, value: float, words: str) -> None:
    body = chai_body()
    body[section][field] = value
    if field == "growth":
        body["wacc_override"] = 0.07
    for path, payload in (
        ("/api/valuation", body),
        ("/api/sensitivity", body),
        ("/api/tornado", {"assumptions": body}),
        ("/api/montecarlo", {"assumptions": body}),
        ("/api/export", {"assumptions": body}),
    ):
        r = client.post(path, json=payload)
        assert r.status_code == 422, (path, r.text)
        assert words.lower() in r.json()["error"]["message"].lower()


def test_malformed_requests() -> None:
    assert client.post("/api/valuation", json={}).status_code == 422
    body = chai_body()
    body["surprise"] = 1
    r = client.post("/api/valuation", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_REQUEST"
    bad = client.post(
        "/api/valuation", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert bad.status_code == 422


def test_unknown_ticker_is_503_and_bad_ticker_422() -> None:
    r = client.get("/api/defaults?ticker=NOPE.NS")
    assert r.status_code == 503 and "Available" in r.json()["error"]["message"]
    assert client.get("/api/defaults?ticker=..%2F..%2Fetc").status_code == 422


def test_oversized_body_is_413() -> None:
    r = client.post("/api/valuation", content=b"x" * 200_000)
    assert r.status_code == 413


def test_rate_limit() -> None:
    limit = load_config()["api"]["rate_limit_per_minute"]
    for _ in range(limit):
        client.get("/api/beta")
    r = client.get("/api/beta")
    assert r.status_code == 429 and r.headers["retry-after"] == "60"


def test_cors_only_for_allowed_origins() -> None:
    ok = client.get("/api/health", headers={"origin": "http://localhost:3000"})
    other = client.get("/api/health", headers={"origin": "https://evil.example"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in other.headers
