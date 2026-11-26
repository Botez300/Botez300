# Data capability (updated Phase 4, 2026-11-26)

Sources are authorized per `legion/evidence.py`. Each status below was established in this session.

| Need | Source | Status |
|---|---|---|
| Daily, weekly and monthly OHLCV | Robinhood MCP | AVAILABLE (recorded) |
| Diluted GAAP quarterly EPS | SEC XBRL via Robinhood `get_sec_filing_facts` | AVAILABLE for Q1-Q3 (3-month facts). Q4 is not separately filed, so Q4 slots stay UNVERIFIED. 17 quarters needs about 12 filings, i.e. 4 facts calls per ticker |
| TTM operating income, taxes, pretax income, balance sheet | SEC XBRL via Robinhood | AVAILABLE (recorded AAPL 10-Q) |
| Native ROIC, EV | derived from SEC plus Robinhood market cap | IMPLEMENTED, with provenance |
| IWM point-in-time constituents | iShares official holdings file | PARSER READY. Direct download is blocked in the build sandbox (proxy 403), so the format is unverified until the first host download |
| SEC EDGAR direct (data.sec.gov) | official | blocked in the sandbox; works on the host only if network allows |
| Dated individual analyst Buy ratings | none authorized | GAP. Robinhood gives aggregate counts only. Alpha Vantage and Bigdata.com are proposed below, not connected |
| RP(yearly) for SPX500 | none | GAP. Stays UNVERIFIED (your instruction) |
| Minervini 10-criteria signal, Weinstein Stage, Turtle (yes,yes,yes,yes,2) | TradingView MCP (authorized research platform in this session) | Several community scripts share these names. Which exact script and version is your platform's is UNKNOWN (C18). There is no "Turtle Trading Strategy (Long-Only)" script. The import path exists, but readings count only after you map script_id+version |
| Options chains, quotes, Greeks | Robinhood MCP | AVAILABLE (recorded) |

## Proposed providers (NOT connected; your approval needed)
| Provider | Would close | Notes |
|---|---|---|
| Alpha Vantage (MCP connected to the Claude session) | analyst rating counts, earnings, statements, ETF profile | Analyst data is aggregate, so it still does not close CAN SLIM "I". A premium API key may be needed for volume |
| Bigdata.com (MCP connected to the Claude session) | analyst actions in news and documents | Could provide dated rating actions if a licensed broker-research source is included. Verify licensing |
| A licensed analyst-actions feed (e.g. Benzinga/Zacks/FactSet via a paid plan) | CAN SLIM "I" exactly | paid; not evaluated |
| The platform that defines RP(yearly) and the named indicators | CAN SLIM "L", the EXACT Minervini, Weinstein and Turtle scanners | you need to name the platform |
