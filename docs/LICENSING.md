# Licensing

Reviewed 2026-11 from package metadata. Re-run `npx license-checker-rseidelsohn --production --summary` (web) and
`pip-licenses` (Python) when dependencies change. This is an engineering inventory, not legal advice.

## Third-party software in the product
| Component | Licence | Obligation / note |
| --- | --- | --- |
| `@luxalgo/vela`, `@luxalgo/vela-ui` | Apache-2.0 + NOTICE | **Visible attribution on every screen that shows a chart.** We keep the built-in mark and add a "Charts by Vela" link. `NOTICE` at the repo root reproduces Vela's notice and ships in the web image. |
| Next.js, React, Tailwind CSS | MIT | — |
| FastAPI, Pydantic, SQLAlchemy, Alembic, PyJWT, argon2-cffi, redis-py | MIT | — |
| Starlette, Uvicorn, httpx, NumPy, pandas | BSD-style | — |
| psycopg 3 | LGPL-3.0 | Used unmodified as a library; LGPL permits this in closed-source software. Do not vendor a modified copy without publishing the changes. |
| `@img/sharp-libvips` (transitive, via Next.js image optimisation) | LGPL-3.0-or-later | Dynamically loaded, unmodified. We do not use `next/image`; it can be dropped from the image if required. |
| caniuse-lite (build tooling data) | CC-BY-4.0 | Build-time only. |

No GPL or AGPL components are included. PostgreSQL (PostgreSQL Licence) and Redis 7 run as separate services; check
the licence of the Redis version you deploy (7.4+ is not BSD) or use Valkey.

## Test-only
TA-Lib (BSD) is the independent reference for indicator golden tests. It is not imported by product code.

## Evaluated, not adopted yet
QuantConnect LEAN — Apache-2.0; candidate backtest engine for M4.

## Original work and third-party IP
- Indicator and scanner code is written from published, general-purpose definitions (Wilder, Bollinger, Chaikin,
  Donchian, etc.). No code or formula was taken from TrendSpider, LuxAlgo's paid toolkits or any closed product, and
  none of their names, logos or interface designs are used.
- Method names used in the roadmap (CAN SLIM®, SEPA®/VCP, Turtle, Weinstein stages) refer to publicly described
  approaches. CAN SLIM and SEPA are trademarks of their owners: scanners will be implemented from measurable public
  rules, named neutrally in the UI where required, and never presented as endorsed by or identical to the originals.
- "Pine Script" is a TradingView trademark; no Pine engine is bundled.

## Market data
Not software, but the larger legal risk: see DATA_PROVIDERS.md. Vendor and exchange agreements govern display and
redistribution.

## Pre-launch checklist (legal / compliance)
- [ ] Data vendor contract covers display to end customers for each data type shown; exchange agreements where needed.
- [ ] Index constituent data licensed for any index-based scanner universe.
- [ ] Securities counsel review: publisher's exclusion vs. investment-adviser registration; signal and "setup" wording; required disclaimers.
- [ ] Terms of service, privacy policy, cookie notice, risk disclosure; hypothetical-performance disclaimers on every backtest.
- [ ] Privacy: data map, deletion/export workflow, DPA with processors (GDPR/CCPA as applicable).
- [ ] Trademark clearance for the product name; third-party marks used only descriptively.
- [ ] Attribution notices present in the deployed UI and distributed images.
