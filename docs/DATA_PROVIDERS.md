# Research-data provider capability matrix (Phase 5)

Robinhood remains the only brokerage. "Tested" means exercised in this session through an authorized integration. No subscriptions were purchased, nothing was scraped and no credentials were used.

| Capability | Robinhood MCP | SEC via Robinhood tools | SEC EDGAR direct | iShares official file | Alpha Vantage (connected to Claude session) | Bigdata.com (connected to Claude session) |
|---|---|---|---|---|---|---|
| Split-adjusted daily/weekly/monthly OHLCV | **tested** (INSM 227 bars; SPY) | - | - | - | available (not tested) | - |
| 17 quarters diluted GAAP EPS | aggregate only (8q, basis undocumented) | **tested** (Q1-Q3 3-month facts; Q4 not separately filed) | yes (host; sandbox proxy 403) | - | reportedEPS is consensus-basis; not GAAP | - |
| Dated analyst Buy ratings | no (counts only) | - | - | - | counts only | possibly, via news and broker actions (licensing unverified) |
| ETF constituents (IWM) | Russell2000 index code via scanner (not holdings) | - | - | parser ready; download blocked in sandbox | ETF_PROFILE (not point-in-time) | - |
| Market cap / EV | market cap **tested**; EV via scanner | debt/cash **tested** | yes | - | yes | - |
| Operating income / IC / ROIC inputs | operating margin only | **tested** (AAPL) | yes | - | statements (not tested) | - |
| Earnings dates | **tested** (calendar shape partly) | - | - | - | EARNINGS_CALENDAR | - |
| Sector classification | fundamentals sector / Morningstar via scanner | SIC in filing headers (not yet parsed) | yes | - | yes | - |
| Historical options data | no (current chains and quotes only) | - | - | - | HISTORICAL_OPTIONS (premium) | - |
| Proprietary indicators (Minervini, Weinstein, Turtle, RP) | no | - | - | - | - | - |
| Point-in-time / delisted | no | yes (filing dates) | yes | as-of dated files | partial | - |
| Auth | OAuth (host) | same | User-Agent with contact | none | API key | OAuth/API key |
| Cost | included | included | free | free | free tier limited; premium paid | paid |

## Gaps that keep criteria UNVERIFIED
- CAN SLIM "I" (dated Buy ratings).
- CAN SLIM "L" (RP yearly).
- The exact proprietary indicators.
- Historical options returns.
- A point-in-time universe that includes delisted names, needed for survivorship-free backtests.

## Recommendation
1. Use SEC + Robinhood (in place now).
2. Download iShares holdings daily on the host and archive them in Drive `08_Archive` to build your own point-in-time IWM history going forward.
3. If you want CAN SLIM "I", evaluate one licensed analyst-actions feed. Bigdata.com is already connected to the Claude session, but its licensing for automated use must be confirmed before Legion uses it.
4. Historical options data needs a paid source. Until then, options backtests stay BLOCKED and only labeled scenario analysis is possible.
