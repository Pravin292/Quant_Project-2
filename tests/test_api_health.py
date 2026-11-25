"""M9 spike: the API function imports the engine and reads the snapshot."""

from __future__ import annotations

from api.index import app
from fastapi.testclient import TestClient


def test_health_reads_snapshot_without_pandas() -> None:
    body = TestClient(app).get("/api/health").json()
    assert body["status"] == "ok"
    assert body["snapshot"]["ticker"] == "TCS.NS"
