"""Robinhood MCP adapter. READ-ONLY by construction: an allowlist of market-data tools; every other tool
(orders, cancels, exercises, watchlists, alerts, ...) raises ToolBlocked before any transport is touched.
Tool names/parameters come from the schemas discovered in-session on 2026-11-26."""
import json, os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

READ_ONLY_TOOLS = frozenset({"get_equity_quotes", "get_equity_historicals", "get_equity_fundamentals",
    "get_equity_technical_indicators", "get_option_chains", "get_option_instruments", "get_option_quotes",
    "get_earnings_calendar"})
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

class RecordedTransport:
    """Replays fixtures/robinhood_recorded/*. Test use only."""
    FILES = {"get_equity_quotes": "get_equity_quotes.SPY.json", "get_equity_historicals": "get_equity_historicals.SPY.json",
             "get_equity_fundamentals": "get_equity_fundamentals.SPY.json", "get_option_chains": "get_option_chains.SPY.json",
             "get_option_instruments": "get_option_instruments.SPY.json", "get_option_quotes": "get_option_quotes.SPY.json"}
    def __init__(self, d): self.d = d
    def __call__(self, tool, args):
        return json.load(open(os.path.join(self.d, self.FILES[tool])))

class McpHttpTransport:
    """UNTESTED. Needs `pip install mcp`, the Robinhood MCP URL and an OAuth/bearer token supplied via the
    environment (LEGION_RH_MCP_URL, LEGION_RH_MCP_TOKEN). The endpoint and auth scheme were not available in
    the build sandbox; nothing here proves they work."""
    def __init__(self, url=None, token=None):
        self.url, self.token = url or os.environ["LEGION_RH_MCP_URL"], token or os.environ["LEGION_RH_MCP_TOKEN"]
    def __call__(self, tool, args):
        if tool not in READ_ONLY_TOOLS: raise ToolBlocked(tool)
        import asyncio
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
        async def go():
            async with streamablehttp_client(self.url, headers={"Authorization": f"Bearer {self.token}"}) as (r, w, _):
                async with ClientSession(r, w) as s:
                    await s.initialize(); res = await s.call_tool(tool, args)
                    return json.loads(res.content[0].text)
        return asyncio.run(go())
