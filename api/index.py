"""FastAPI app (F9). Routes only validate input and call src/dcf; no finance logic here.

Milestone M9 spike: a health route that proves the engine imports and the snapshot
loads inside a Vercel Python function. The full endpoints arrive in M10.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

_BOOT = time.perf_counter()

from fastapi import FastAPI  # noqa: E402

from dcf import __version__, loader  # noqa: E402
from dcf.config import load_config  # noqa: E402

app = FastAPI(title="TCS DCF Valuation API", version=__version__)
_IMPORT_SECONDS = time.perf_counter() - _BOOT


@app.get("/api/health")
def health() -> dict[str, object]:
    """Liveness plus the facts the Vercel feasibility spike needs."""
    cfg = load_config()
    snap = loader.load_snapshot(cfg["company"]["ticker"], ROOT / cfg["paths"]["snapshots_dir"])
    return {
        "status": "ok",
        "engine_version": __version__,
        "python": sys.version.split()[0],
        "import_seconds": round(_IMPORT_SECONDS, 3),
        "snapshot": {"ticker": snap["ticker"], "fetched_at": snap["fetched_at"]},
        "pandas_loaded": "pandas" in sys.modules,
    }
