# Product specification

**Legion Quant Terminal** is a multi-tenant SaaS for market research: charting, technical analysis, rule-based
scanning, strategy testing, AI-assisted research and paper trading in one workflow.

## Principles
1. **Evidence over assertion.** Every number shown carries its provider, timestamp, adjustment and a state:
   `VERIFIED`, `PROVISIONAL`, `UNVERIFIED` or `SIMULATED`. Missing data is reported as missing, never as unfavourable.
2. **No lookahead.** Signals use only what was knowable at the bar they are stamped on. Forming bars are excluded from scans.
3. **One implementation per calculation.** Chart, scanner, backtester and agents read the same indicator registry.
4. **Original work.** Methods come from published, general-purpose techniques. No proprietary formulas, branding or UI copies.
5. **Research, not advice.** Setups are rule outcomes on historical data. Nothing is presented as a forecast or guarantee.
   Paper trading is the only trading mode until live execution is separately authorised.

## Users
Active self-directed traders and small research teams who today combine a charting tool, a signal overlay, a screener
and spreadsheets. Workspaces (organizations) isolate each customer's data; roles are owner, admin, member, viewer.

## Scope by phase (the owner's brief, condensed)
| Phase | Capability | Milestone |
| --- | --- | --- |
| 1 | Monorepo, API, database, auth, containers, CI | M1 ✅ |
| 2 | Charting: styles, layouts, drawings, replay, patterns, AVWAP, volume profile | M1 (core) → M2 |
| 3 | Indicator library, Legion Adaptive Signals, market structure, composite oscillators | M1 (25 indicators) → M2 |
| 4 | Scanner, query builder, Legion Command scanners A–K, unified output | M1 (rule scanner) → M3 |
| 5 | Strategy builder, event-driven backtester, statistical validation | M4 |
| 6 | Legion Quant Council (five agents, tool-grounded, risk veto) | M5 |
| 7 | Paper trading, options research | M6 |
| 8 | Alerts and scheduled reports (weekdays 09:00, Sunday 19:00 America/New_York) | M3 (reports) / M8 (alerts) |
| 9 | Premium terminal UX | continuous |
| 10 | Billing, entitlements, quotas, admin | M7 |
| 11 | Provider abstraction, data verification | M1 (daily bars) → continuous |
| 12 | Security, testing, quality gates | continuous |

## Subscription tiers
FREE, PRO, QUANT, INSTITUTIONAL. Limits are configuration (`apps/api/legion_api/entitlements.py`); only limits for
features that exist are defined. Prices and Stripe billing are M7.

## Out of scope until explicitly authorised
Live brokerage execution; redistribution of vendor data beyond what the customer's licence permits; anything that
requires reverse-engineering a closed product.
