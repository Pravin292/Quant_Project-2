# ADR 0002: Daily JSON snapshot of statements
**Decision:** A scheduled GitHub Action fetches statements and commits a dated JSON snapshot; the API reads it. Only the live share price is fetched per request, with fallback to the snapshot price.
**Why:** yfinance can be slow, incomplete or blocked from cloud servers. Each number keeps its source and fetch date.
