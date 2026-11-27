"""PDF report (F25) and Screener upload (F1 fallback in the app)."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from api import index, middleware, service
from fastapi.testclient import TestClient
from pypdf import PdfReader

from dcf import loader
from dcf.pdf import Pdf, wrap

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = (ROOT / "data/samples/screener_sample.xlsx").read_bytes()
client = TestClient(index.app)


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    real = loader.fetch_live_price

    def offline(ticker: str, snap: object = None, fetcher: object = None) -> object:
        def boom(_: str) -> float:
            raise OSError("offline")

        return real(ticker, snap, boom)  # type: ignore[arg-type]

    monkeypatch.setattr(loader, "fetch_live_price", offline)
    service._PRICE_CACHE.clear()
    index._CACHE.clear()
    middleware.reset_rate_limit()
    yield


def test_pdf_writer_is_readable_and_escapes_text() -> None:
    pdf = Pdf()
    pdf.text(40, 40, "Price (₹) \\ 10")
    pdf.add_page()
    pdf.text(40, 40, "second")
    reader = PdfReader(io.BytesIO(pdf.to_bytes()), strict=True)
    assert len(reader.pages) == 2
    assert "Price (INR ) \\ 10" in reader.pages[0].extract_text()
    assert all(len(line) < 20 for line in wrap("one two three four five six", 10, 60))


def test_report_is_two_pages_with_the_valuation() -> None:
    a = client.get("/api/defaults").json()["assumptions"]
    fair = client.post("/api/valuation", json=a).json()["fair_value_per_share"]
    r = client.post("/api/report", json={"assumptions": a})
    assert r.status_code == 200, r.text
    assert "TCS.NS_report.pdf" in r.headers["content-disposition"]
    pages = PdfReader(io.BytesIO(r.content), strict=True).pages
    assert len(pages) == 2
    first, second = (p.extract_text() for p in pages)
    assert f"INR {fair:,.0f}" in first and "Scenarios" in first
    assert "Limitations" in second and "not investment" in second


def test_upload_runs_the_whole_model() -> None:
    r = client.post("/api/upload", content=SAMPLE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company"]["name"] == "Sample Screener Co"
    assert body["assumptions"]["ticker"] is None
    assert "assumed 1" in body["sources"]["wacc.beta"]
    assert len(body["historical"]["years"]) == 4
    a = body["assumptions"]
    for path, payload in (
        ("/api/valuation", a),
        ("/api/surface", a),
        ("/api/scenarios", {"assumptions": a}),
        ("/api/montecarlo", {"assumptions": a}),
        ("/api/export", {"assumptions": a}),
        ("/api/report", {"assumptions": a}),
    ):
        assert client.post(path, json=payload).status_code == 200, path


def test_bad_uploads_are_rejected() -> None:
    assert client.post("/api/upload", content=b"not excel").status_code == 503
    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("hello.txt", "hi")
    assert client.post("/api/upload", content=empty.getvalue()).status_code == 503
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("big.xml", b"0" * 31_000_000)
    r = client.post("/api/upload", content=bomb.getvalue())
    assert r.status_code == 503 and "unpacked" in r.json()["error"]["message"]
    assert client.post("/api/upload", content=b"x" * 2_100_000).status_code == 413
