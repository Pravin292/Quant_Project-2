"""p50 / p95 response times of every endpoint on a deployed site (F28).

Usage: python scripts/measure_latency.py [--base https://...] [--runs 20]
Requests are paced to stay under the API's rate limit, and every POST uses a slightly
different share price so cached results are not what gets timed.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from datetime import UTC, datetime
from typing import Any

PACE_SECONDS = 0.65  # about 90 requests a minute


def call(base: str, path: str, body: Any = None) -> tuple[float, bytes]:
    request = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "dcf-latency-check"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=60) as response:
        data: bytes = response.read()
    return time.perf_counter() - start, data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://quant-project-2.vercel.app")
    parser.add_argument("--runs", type=int, default=20)
    args = parser.parse_args()
    first, data = call(args.base, "/api/defaults")
    assumptions = json.loads(data)["assumptions"]
    gets = [
        "/api/health",
        "/api/defaults",
        "/api/historical",
        "/api/beta",
        "/api/peers",
    ]
    posts = [
        ("/api/valuation", False),
        ("/api/reverse-dcf", True),
        ("/api/sensitivity", False),
        ("/api/surface", False),
        ("/api/tornado", True),
        ("/api/scenarios", True),
        ("/api/montecarlo", True),
        ("/api/export", True),
        ("/api/report", True),
    ]
    print(f"Measured {datetime.now(UTC):%Y-%m-%d %H:%M} UTC, {args.runs} requests each.")
    print(f"First request of this run (GET /api/defaults): {first:.2f} s\n")
    print("| Endpoint | p50 (ms) | p95 (ms) |\n|---|---|---|")
    run_id = 0
    for path, wrapped, method in [(p, False, "GET") for p in gets] + [
        (p, w, "POST") for p, w in posts
    ]:
        times: list[float] = []
        for _ in range(args.runs):
            body = None
            if method == "POST":
                run_id += 1
                price = assumptions["bridge"]["price"] + run_id / 1000
                a = {**assumptions, "bridge": {**assumptions["bridge"], "price": price}}
                body = {"assumptions": a} if wrapped else a
            seconds, _ = call(args.base, path, body)
            times.append(seconds * 1000)
            time.sleep(max(0.0, PACE_SECONDS - seconds))
        p95 = statistics.quantiles(times, n=20, method="inclusive")[-1]
        print(f"| {method} {path} | {statistics.median(times):.0f} | {p95:.0f} |", flush=True)


if __name__ == "__main__":
    main()
