# Data providers

Set `DATA_PROVIDER` and the matching credentials (`.env.example`). The API refuses to start if the selected provider
is missing credentials — it never falls back to demo data.

| Provider | State | Coverage in this build | Credentials | Notes |
| --- | --- | --- | --- | --- |
| `demo` | **Working** | 70 fictional symbols (58 stocks, 11 sector ETFs, 1 market ETF), daily bars from 2014 | none | Synthetic, deterministic, labelled `SIMULATED`. Real tickers do not resolve. |
| `alpaca` | **Built, not run against the live service** | Daily bars (split+dividend adjusted), symbol lookup | `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, `ALPACA_FEED` | Tested against documented response shapes with a mock transport. Marked `DELAYED`. Cannot enumerate a scan universe: scan watchlists. |
| `polygon` (Polygon.io / Massive) | **Built, not run against the live service** | Daily aggregates (split-adjusted), ticker search | `POLYGON_API_KEY`, `POLYGON_BASE_URL` | Same caveats. Massive customers set the base URL from their account documentation. |
| SEC EDGAR, FRED, fundamentals, options, ownership | Planned | — | — | Needed for scanners B, K and the regime model (M3). |

Why the vendor adapters are unverified: this development environment has no vendor credentials and its network
policy blocks the vendor hosts. First task when credentials exist: run `tests/python/test_data.py`-style checks
against the live API and record the result in PROJECT_STATUS.md.

## Licensing — read before showing vendor data to anyone else
A data subscription normally licenses **your own use**. Displaying vendor data to your customers (redistribution),
real-time exchange data, and index constituents (e.g. Russell 2000 / IWM holdings) each need rights you must
confirm with the vendor and, for real-time US equities, the exchanges. Nothing in this codebase grants those rights.

## What every bar set carries
Provider, symbol, exchange, timeframe, timezone, adjustment (`raw`/`split`/`all`/`n/a`), data status
(`LIVE`/`DELAYED`/`HISTORICAL`/`SIMULATED`), fetch time, first/last bar, whether the last bar is still forming,
completeness, and data-quality warnings.

## Quality checks (`legion_data/quality.py`)
Unsorted or duplicate bars (fixed and reported), missing prices, invalid OHLC relationships, non-positive prices,
negative or unexpected zero volume, weekend bars (timezone errors), sessions missing versus the NYSE calendar,
day-over-day moves that look like an unadjusted split, and a stale last bar.
Not yet covered: early closes and one-off closures, cross-provider reconciliation, intraday checks.

## Verification states
`VERIFIED` — bars present, no hard errors, last bar closed, no gaps. `PROVISIONAL` — last bar forming or sessions
missing. `UNVERIFIED` — no bars or a hard error. `SIMULATED` — demo provider. Scan rows computed on completed bars
of a provisional set are reported `VERIFIED` only when the sole issue was the forming bar that the scan excluded.

## Adding a provider
Subclass `MarketDataProvider` (`search`, `get_symbol`, `fetch_daily`, optionally `universe`), return frames built
with `daily_frame`, add it to `build_provider`, and add mock-transport tests. The base class supplies quality
checks, resampling and forming-bar detection.
