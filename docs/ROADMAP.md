# Roadmap

Status as of 2026-11-15. One vertical slice at a time; a milestone closes only when its acceptance criteria pass.

| # | Milestone | State |
| --- | --- | --- |
| 0 | Audit, architecture, documentation | Done |
| 1 | Functional MVP: stack, auth, chart, data adapter, indicators, watchlists, scanner | Done (see caveats in PROJECT_STATUS.md) |
| 2 | Advanced technical analysis | **Next** |
| 3 | Specialized scanners + reports | Planned |
| 4 | Strategy builder + backtesting | Planned |
| 5 | AI agents | Planned |
| 6 | Paper trading | Planned |
| 7 | Commercialization (billing, quotas, admin, public pages) | Planned |
| 8 | Production hardening | Planned |

## Carry-over from Milestone 1 (do first)
1. Run `docker compose up --build` and the e2e suite on a machine with Docker (not possible in the build sandbox).
2. With real credentials, verify the Alpaca and Polygon adapters against the live APIs; record results.
3. Persist chart drawings and layouts per user (API + table) instead of browser storage.

## Milestone 2 — exact next tasks, in order
1. **Relative strength**: `rs_ratio` / RS-vs-benchmark indicator taking a second symbol; cross-symbol support in the
   registry contract and scanner operands; benchmark setting per workspace.
2. **Reference stats**: 52-week high/low, distance from high, all-time high (with history-completeness flag).
3. **Anchored VWAP UX**: anchor by date; ATH-anchored AVWAP status (ABOVE/BELOW/TESTING/CROSSING/UNVERIFIED) as a
   reusable scanner column.
4. **Swing detection** (fractal pivots, confirmed N bars later and stamped at confirmation time) — the base for
   market structure, patterns, auto trendlines and auto-Fibonacci.
5. **Market structure suite** on top of swings: HH/HL/LH/LL, BOS, CHoCH, equal highs/lows, FVG, liquidity sweeps.
6. **Pattern engine v1**: VCP contractions, flags, triangles, double top/bottom, cup-and-handle, with the report
   fields required by the brief and `developing` vs `confirmed` states.
7. **Legion Adaptive Signals v1**: ATR trailing stop, trend cloud, confluence score with visible components.
8. Ichimoku, Squeeze Momentum; chart overlays for higher timeframes; replay and screenshot wiring; multi-chart layout.

## Later milestones — prerequisites to arrange now
- M3: fundamentals + index-constituent data source and licence; job queue (Redis-backed) for scheduled scans/reports.
- M4: decide LEAN vs in-house engine after the strategy schema draft.
- M5: Anthropic API key and budget policy.
- M7: Stripe account (test keys), pricing decisions, legal review items in LICENSING.md.
