"""Robinhood MCP adapter. READ-ONLY by construction: an allowlist of market-data tools; every other tool
(orders, cancels, exercises, watchlists, alerts, ...) raises ToolBlocked before any transport is touched.
Tool names/parameters come from the schemas discovered in-session on 2026-11-26."""
import json, os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

READ_ONLY_TOOLS = frozenset({"get_equity_quotes", "get_equity_historicals", "get_equity_fundamentals",
    "get_equity_technical_indicators", "get_option_chains", "get_option_instruments", "get_option_quotes",
    "get_earnings_calendar", "get_earnings_results", "get_equity_analyst_ratings", "get_financials", "get_indexes",
    "get_index_historicals", "get_scanner_datapoints", "get_scanner_filter_specs", "preview_scan",
    "get_sec_filing_index", "get_sec_filing_facts"})
# preview_scan evaluates filters WITHOUT saving (read-only). create_scan / update_scan_* are writes and stay blocked.
class ToolBlocked(PermissionError): pass
class ConnectionFailure(RuntimeError): pass
class DataError(ValueError): pass

def _f(x):
    try: return None if x in (None, "") else float(x)
    except (TypeError, ValueError): return None
def _t(s):
    if not s: return None
    s = s.replace("Z", "+00:00"); i = s.find("."); 
    if i > 0:                                   # trim ns -> us
        j = i + 1
        while j < len(s) and s[j].isdigit(): j += 1
        s = s[:i + 1] + s[i + 1:j][:6].ljust(6, "0") + s[j:]
    return datetime.fromisoformat(s)

@dataclass
class Quote: symbol: str; price: float | None; ts: datetime | None; bid: float | None; ask: float | None; prev_close: float | None; state: str; has_traded: bool
@dataclass
class Bar: ts: datetime; o: float; h: float; l: float; c: float; v: float
@dataclass
class Contract:
    id: str; underlying: str; type: str; strike: float; expiry: str; bid: float | None = None; ask: float | None = None
    mark: float | None = None; delta: float | None = None; gamma: float | None = None; theta: float | None = None
    vega: float | None = None; iv: float | None = None; oi: int | None = None; volume: int | None = None; updated: datetime | None = None
    multiplier: int = 100; tradable: bool = True

class RobinhoodClient:
    def __init__(self, transport: Callable[[str, dict], dict]): self.transport = transport
    def call(self, tool: str, args: dict) -> dict:
        if tool not in READ_ONLY_TOOLS: raise ToolBlocked(f"{tool} is not on the read-only allowlist")
        try: out = self.transport(tool, args)
        except ToolBlocked: raise
        except Exception as e: raise ConnectionFailure(f"{tool}: {e}") from e
        if not isinstance(out, dict) or "data" not in out: raise DataError(f"{tool}: malformed response")
        return out["data"]
    def quote(self, sym) -> Quote:
        r = self.call("get_equity_quotes", {"symbols": [sym]})["results"]
        if not r: raise DataError(f"no quote for {sym}")
        q = r[0]["quote"]
        return Quote(q["symbol"], _f(q.get("last_trade_price")), _t(q.get("venue_last_trade_time")), _f(q.get("bid_price")),
                     _f(q.get("ask_price")), _f(q.get("previous_close")), q.get("state", ""), bool(q.get("has_traded")))
    def bars(self, sym, start, end=None, interval="day") -> list[Bar]:
        a = {"symbols": [sym], "start_time": start, "interval": interval}
        if end: a["end_time"] = end
        r = self.call("get_equity_historicals", a)["results"]
        if not r: raise DataError(f"no bars for {sym}")
        return [Bar(_t(b["begins_at"]), _f(b["open_price"]), _f(b["high_price"]), _f(b["low_price"]), _f(b["close_price"]), float(b["volume"]))
                for b in r[0]["bars"] if not b.get("interpolated")]
    def fundamentals(self, sym) -> dict:
        r = self.call("get_equity_fundamentals", {"symbols": [sym]})["results"]
        if not r: raise DataError(f"no fundamentals for {sym}")
        x = r[0]; return {k: (_f(v) if k not in ("symbol", "sector", "market_date", "bounds") else v) for k, v in x.items() if k != "description"}
    def indicator(self, sym, type_, period, start, interval="day"):
        r = self.call("get_equity_technical_indicators", {"symbols": [sym], "type": type_, "period": period,
                      "interval": interval, "start_time": start, "output": "latest"})["results"]
        s = r[0]["indicators"][0]["series"] if r else []
        return s[-1]["value"] if s else None
    def chain(self, sym) -> dict:
        cs = self.call("get_option_chains", {"underlying_symbol": sym})["chains"]
        if not cs: raise DataError(f"no option chain for {sym}")
        c = cs[0]; return {"id": c["id"], "expirations": c["expiration_dates"], "multiplier": int(float(c["trade_value_multiplier"])),
                           "can_open": c.get("can_open_position", False)}
    def contracts(self, chain_id, expiry, type_) -> list[Contract]:
        out, cursor = [], None
        while True:
            a = {"chain_id": chain_id, "expiration_dates": expiry, "type": type_}
            if cursor: a["cursor"] = cursor
            d = self.call("get_option_instruments", a)
            out += [Contract(i["id"], i["chain_symbol"], i["type"], float(i["strike_price"]), i["expiration_date"],
                             multiplier=int(float(i.get("trade_value_multiplier", 100))), tradable=i.get("tradability") == "tradable")
                    for i in d["instruments"] if i.get("state") == "active"]
            cursor = d.get("next")
            if not cursor: return out
    def option_quotes(self, contracts: list[Contract]) -> list[Contract]:
        by = {c.id: c for c in contracts}
        for i in range(0, len(contracts), 20):
            for r in self.call("get_option_quotes", {"instrument_ids": [c.id for c in contracts[i:i + 20]]})["results"]:
                q = r["quote"]; c = by[q["instrument_id"]]
                c.bid, c.ask, c.mark = _f(q.get("bid_price")), _f(q.get("ask_price")), _f(q.get("mark_price"))
                c.delta, c.gamma, c.theta, c.vega, c.iv = (_f(q.get(k)) for k in ("delta", "gamma", "theta", "vega", "implied_volatility"))
                c.oi, c.volume, c.updated = q.get("open_interest"), q.get("volume"), _t(q.get("updated_at"))
        return contracts
    def earnings_dates(self, sym, start, days=31):
        """Returns list of date strings, or None when the response shape is not understood (=> unknown, block)."""
        rs = self.call("get_earnings_calendar", {"symbols": [sym], "start_date": start, "days": days})["results"]
        out = []
        for e in rs:
            d = (e.get("report") or {}).get("date")
            if not d: return None
            out.append(d[:10])
        return out

def _ext(cls):
    def earnings_history(self, sym):
        """Reported quarters only, newest first. Basis is not documented by the tool => 'UNDOCUMENTED'."""
        rs = self.call("get_earnings_results", {"symbol": sym})["results"]
        rep = [r for r in rs if (r.get("eps") or {}).get("actual") is not None]
        rep.sort(key=lambda r: (r["year"], r["quarter"]), reverse=True)
        return [{"eps": _f(r["eps"]["actual"]), "fiscal": f"{r['year']}Q{r['quarter']}", "report_date": (r.get("report") or {}).get("date")} for r in rep], "UNDOCUMENTED"
    def analyst_ratings(self, sym):
        r = self.call("get_equity_analyst_ratings", {"symbols": [sym]})["results"]
        return (r[0] or {}).get("ratings") if r else None
    def index_id(self, sym):
        ix = self.call("get_indexes", {"symbols": sym})["indexes"]
        if not ix: raise DataError(f"no index {sym}")
        return ix[0]["id"]
    def index_bars(self, sym, start, interval="day"):
        r = self.call("get_index_historicals", {"instrument_ids": [self.index_id(sym)], "start_time": start, "interval": interval})["results"]
        return [Bar(_t(b["begins_at"]), _f(b["open_value"]), _f(b["high_value"]), _f(b["low_value"]), _f(b["close_value"]), 0.0)
                for b in (r[0]["bars"] if r else []) if not b.get("interpolated")]
    def scan_universe(self, index_code, extra_filters=(), columns=()):
        """Robinhood scanner, read-only preview. Caps at 200 rows per call (total_items 201 => truncated)."""
        d = self.call("preview_scan", {"filters": [{"expression": "symbol", "predicate": "PREDICATE_IN_LIST", "values": [index_code]}, *extra_filters],
                                       "columns": list(columns) or None})["result"]
        return d["results"], d["total_items"] > len(d["results"])
    for f in (earnings_history, analyst_ratings, index_id, index_bars, scan_universe): setattr(cls, f.__name__, f)
_ext(RobinhoodClient)

class RecordedTransport:
    """Replays fixtures/robinhood_recorded/*. Test use only."""
    FILES = {"get_equity_quotes": "get_equity_quotes.SPY.json", "get_equity_historicals": "get_equity_historicals.SPY.json",
             "get_equity_fundamentals": "get_equity_fundamentals.SPY.json", "get_option_chains": "get_option_chains.SPY.json",
             "get_option_instruments": "get_option_instruments.SPY.json", "get_option_quotes": "get_option_quotes.SPY.json",
             "get_earnings_results": "get_earnings_results.NVDA.json", "get_equity_analyst_ratings": "get_equity_analyst_ratings.NVDA.json",
             "get_financials": "get_financials.NVDA.json", "get_indexes": "get_indexes.SPX.json", "get_index_historicals": "get_index_historicals.SPX.json",
             "preview_scan": "preview_scan.russell2000.json",
             "get_sec_filing_index": "get_sec_filing_index.AAPL.json", "get_sec_filing_facts": "get_sec_filing_facts.AAPL_10Q_2026-07-31.trimmed.json"}
    def __init__(self, d): self.d = d
    def __call__(self, tool, args):
        return json.load(open(os.path.join(self.d, self.FILES[tool])))

DEFAULT_RH_MCP_URL = "https://agent.robinhood.com/mcp/trading"   # confirmed on robinhood.com support article "Onboarding an external agent"

class McpHttpTransport:
    """Streamable-HTTP MCP client for the official Robinhood MCP server (mcp SDK >= 2.x API: streamable_http_client +
    create_mcp_http_client). Auth: an httpx Auth object, normally legion.rh_auth.oauth_provider(), which performs the
    standard MCP OAuth flow (discovery, dynamic client registration, PKCE, refresh) and keeps tokens in the OS credential
    store. NOT verified end-to-end from the build sandbox (proxy blocks agent.robinhood.com; no interactive login)."""
    def __init__(self, url=None, auth=None):
        self.url = url or os.environ.get("LEGION_RH_MCP_URL", DEFAULT_RH_MCP_URL)
        if auth is None:
            from .rh_auth import oauth_provider
            auth = oauth_provider(self.url)
        self.auth = auth
    def __call__(self, tool, args):
        if tool not in READ_ONLY_TOOLS: raise ToolBlocked(tool)
        import asyncio
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client, create_mcp_http_client
        async def go():
            async with create_mcp_http_client(auth=self.auth) as http:
                async with streamable_http_client(self.url, http_client=http) as streams:
                    r, w = streams[0], streams[1]
                    async with ClientSession(r, w) as s:
                        await s.initialize(); res = await s.call_tool(tool, args)
                        if getattr(res, "isError", False) or getattr(res, "is_error", False): raise RuntimeError(f"tool error: {res.content[0].text[:200]}")
                        return json.loads(res.content[0].text)
        return asyncio.run(go())

class ResilientTransport:
    """Retries transient failures with exponential backoff. Never retries ToolBlocked; never changes the tool or args."""
    def __init__(self, inner, retries=3, base_delay=1.0, sleep=None):
        import time
        self.inner, self.retries, self.base, self.sleep = inner, retries, base_delay, sleep or time.sleep
        self.failures = 0
    def __call__(self, tool, args):
        if tool not in READ_ONLY_TOOLS: raise ToolBlocked(tool)
        last = None
        for i in range(self.retries + 1):
            try:
                out = self.inner(tool, args); self.failures = 0; return out
            except ToolBlocked: raise
            except Exception as e:
                last = e; self.failures += 1
                if i < self.retries: self.sleep(self.base * 2 ** i)
        raise ConnectionFailure(f"{tool} failed after {self.retries + 1} attempts: {type(last).__name__}: {last}")
