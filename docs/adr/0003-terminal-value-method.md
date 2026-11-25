# ADR 0003: Terminal value method
**Decision:** Perpetuity-growth (Gordon) terminal value is the default; exit-multiple is shown as a cross-check. The model refuses to run when terminal growth >= WACC and warns when terminal value exceeds about 75% of enterprise value.
**Why:** standard, explainable, and the biggest driver of the result, so it gets the most scrutiny (sensitivity grid, exit multiple, peer multiples, ROIC reinvestment check).
