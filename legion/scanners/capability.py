"""Capability-gap report: what each mandatory input needs vs what the probed Robinhood MCP tools return.
Evidence = read-only probes on 2026-11-26 (recorded in fixtures/robinhood_recorded/)."""
GAPS = [
 # (strategy, input, needed, robinhood_status, evidence)
 ("CAN_SLIM", "Universe", "current complete IWM holdings", "PARTIAL", "preview_scan supports index code Russell2000 (index membership, not ETF holdings)"),
 ("CAN_SLIM", "C/A quarterly EPS", "E[0]..E[16], one consistent basis", "GAP", "get_earnings_results returns trailing <=8 quarters (7 reported for NVDA); basis undocumented"),
 ("CAN_SLIM", "N", "weekly highs", "AVAILABLE", "get_equity_historicals interval=week"),
 ("CAN_SLIM", "S", "completed monthly volume, >=24 months", "AVAILABLE", "get_equity_historicals interval=month"),
 ("CAN_SLIM", "L RP(yearly) for SPX500", "exact provider metric", "GAP", "not in scanner datapoints or Legend catalog"),
 ("CAN_SLIM", "I dated analyst Buy ratings", "individual ratings with dates", "GAP", "get_equity_analyst_ratings: aggregate counts + updated_at only"),
 ("CAN_SLIM", "M market SMA200", ">=290 completed daily index bars", "AVAILABLE", "get_indexes + get_index_historicals (SPX); index chosen pending owner"),
 ("MINERVINI_VCP_SEPA", "G1 trend-template signal", "authentic 10-criteria signal", "GAP", "no such indicator in Legend catalog / scanner datapoints"),
 ("MINERVINI_VCP_SEPA", "G1 market cap", "point-in-time market cap", "AVAILABLE", "get_equity_fundamentals.market_cap (market_date stamped)"),
 ("MINERVINI_VCP_SEPA", "G2-G4", "daily/weekly OHLCV", "AVAILABLE", "get_equity_historicals"),
 ("TURTLE", "System 1/2 entry signals", "platform indicator readings", "GAP", "no Turtle indicator in Legend catalog"),
 ("WEINSTEIN_STAGE_2", "Stage readings", "Weinstein Stage Analysis (30,5,sma)", "GAP", "no Weinstein indicator in Legend catalog"),
 ("WEINSTEIN_STAGE_2", "Relative volume", "weekly volume", "AVAILABLE", "get_equity_historicals interval=week"),
 ("MAGIC_FORMULA", "Operating income TTM", "reported TTM operating income", "PARTIAL", "only fundamental.operatingMargin x totalRevenue (derived; period undocumented)"),
 ("MAGIC_FORMULA", "Enterprise value", "EV > 0", "AVAILABLE", "fundamental.enterpriseValue via preview_scan"),
 ("MAGIC_FORMULA", "ROIC TTM", "documented ROIC", "GAP", "no ROIC datapoint; returnOnEquity/returnOnAssets are not substitutes"),
 ("MAGIC_FORMULA", "Universe", "broad US common equities", "PARTIAL", "preview_scan caps at 200 rows per call; must partition the universe"),
 ("PARABOLIC_MOMENTUM", "Bollinger/ROC/relvol/close", "daily OHLCV", "AVAILABLE", "computed locally from get_equity_historicals; semantics pending"),
]
def report():
    return [{"strategy": a, "input": b, "needed": c, "robinhood": d, "evidence": e} for a, b, c, d, e in GAPS]
def blocking_strategies():
    return sorted({g[0] for g in GAPS if g[3] == "GAP"})
