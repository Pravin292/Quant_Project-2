# Final acceptance checklist (SPEC section 18), 28 November 2026

Legend: [x] done and checked · [ ] still open, with the reason.

## Valuation engine
- [x] Chai Corner example reproduces 26.8 per share
- [x] TCS runs end to end from the snapshot, inputs show source and date
- [x] Python matches an independent Excel recalculation
- [x] Beta by regression; ROIC reinvestment check runs
- [x] Reverse DCF returns the implied growth

## Testing and quality
- [x] Unit, property-based and API tests pass
- [x] CI green on `main`, badge in the README
- [x] Type check, lint and `next build` pass

## Web app
- [x] Inputs panel and all tabs, including scenarios, Monte Carlo and peers
- [x] Waterfall, FCFF chart, heatmaps, tornado and football field render
- [x] Share link reproduces a valuation (covered by the smoke test)
- [x] Phone width and plain error messages checked in a desktop browser
- [ ] Tried on a real phone (owner)
- [ ] Excel export opened in Excel to see the live formulas (owner)

## Deployment
- [x] Live link works; first-request time noted
- [ ] Checked in a private window (owner)
- [x] Daily snapshot Action ran, committed and redeployed (first scheduled run still to be seen)
- [x] README has link, screenshots, diagram, assumptions, validation, limitations, p50/p95 table

## Portfolio and interview readiness
- [x] 2-page case study PDF; LinkedIn post drafted
- [x] `v1.0` tag pushed and GitHub release published (28 November)
- [x] Repository description, topics and website link set
- [ ] Repository pinned on your profile (owner)
- [x] Resume bullets use measured numbers
- [ ] You can explain section 7 and answer section 14.2 (owner)

## Known gaps against the spec
- M17 AI explainer (optional) is not built: it needs an LLM API key and the annual report.
- Annual report not read directly (owner). A secondary source matches revenue, tax, net income
  and operating cash flow; EBIT and CapEx differ slightly (docs/verification.md).
- Branches were merged directly instead of through pull requests (section 16).
- The plain black-and-white redesign is parked on branch `design-v3` at the owner's request.
