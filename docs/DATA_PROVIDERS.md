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

## Phase 6 vendor comparison (sources: vendor pages read 2026-11-26; prices change, so re-check before buying. Nothing has been purchased.)
| Need | Candidate | Coverage (as published) | Cost (as published) | Integration | Notes |
|---|---|---|---|---|---|
| Point-in-time universe, delisted, adjusted OHLCV | **Norgate Data Platinum** | delisted securities and historical index constituents; history back to 1990 (Diamond: 1950) | US$630/yr (Platinum), US$787.50/yr (Diamond) | Windows desktop data updater + Python access (verify current API terms) | Best fit for survivorship-free CAN SLIM/IWM backtests; licensing is for personal use (verify) |
| Historical options chains + Greeks | **ORATS** | end-of-day history from 2007, about 6,000 symbols, quotes + Greeks + IV rank; delayed or live APIs | Delayed Data API US$199/mo; Live US$299/mo | REST + token | Only claims about historical options returns need this |
| Analyst rating history (dated actions) | not verified this phase | - | - | - | Bigdata.com (already connected to the Claude session) is the first candidate to evaluate for licensing; otherwise a licensed broker-actions feed |
| Proprietary indicator evidence | the platform the specs came from (C18) | - | - | - | cannot be replaced; must be authentic readings |

**Recommendation:** Norgate Platinum is the single largest unblocker (multi-year, survivorship-free stock backtests for all six scanners). ORATS is only needed for historical options validation. Do not buy until P1-P8 are settled.
