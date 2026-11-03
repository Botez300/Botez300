"""Turtle System 1 strategy MCP server (stdio, no third-party dependencies).

This server does NOT talk to Robinhood. Claude fetches data with the
Robinhood Agentic Trading MCP tools and passes it here; this server returns
signals and the maximum allowed order size. Orders still go through
review_equity_order and the user's explicit approval.
"""
from __future__ import annotations

import json
import sys
import traceback
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from robinhood_turtle_bot import signals  # noqa: E402
from robinhood_turtle_bot.risk_gate import PendingBuy, Position, Snapshot, max_buy_shares  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"

BARS_SCHEMA = {
    "type": "array",
    "description": "Daily bars exactly as returned by Robinhood get_equity_historicals (interval=day, bounds=regular). ~1 year recommended.",
    "items": {"type": "object"},
}

TOOLS = [
    {
        "name": "turtle_strategy_config",
        "description": "Return the active Turtle System 1 (RSI>=50) strategy config: scanner id, entry/exit rules and portfolio gates.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "turtle_evaluate_entry",
        "description": "Evaluate a scanner candidate for a Turtle System 1 long entry: completed-bar RSI(14)>=50, 20-day breakout with skip-after-winner filter, 55-day failsafe, N, initial 2N stop and pyramid levels. A scanner match alone is not a signal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "bars": BARS_SCHEMA,
                "live_price": {"type": "number", "description": "Current last trade price from get_equity_quotes"},
                "last_bar_complete": {"type": "boolean", "description": "true only if the newest bar is a finished session. Default false (newest bar dropped)."},
            },
            "required": ["symbol", "bars"],
        },
    },
    {
        "name": "turtle_evaluate_position",
        "description": "Check an open Turtle position for exits (10-day low, 2N stop below the latest unit; RSI ignored) and the next 0.5N pyramid add.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "bars": BARS_SCHEMA,
                "live_price": {"type": "number"},
                "unit_fill_prices": {"type": "array", "items": {"type": "number"}, "description": "Actual fill price of each unit, oldest first"},
                "entry_N": {"type": "number", "description": "N at the initial entry"},
                "last_bar_complete": {"type": "boolean"},
            },
            "required": ["symbol", "bars", "live_price", "unit_fill_prices", "entry_N"],
        },
    },
    {
        "name": "turtle_size_buy",
        "description": "Fail-closed max whole shares for a proposed BUY under the account gates: 5 occupied symbols (holdings + open buy orders), >=$500 cash reserve left after purchase; deployable cash split evenly across open slots (per-symbol caps per strategy config). Pass expected_fill_price = the order's limit price. Proposal only, not authorization.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "net_liquidation_value": {"type": "number", "description": "get_portfolio total_value"},
                "cash": {"type": "number", "description": "get_portfolio cash (actual cash, NOT buying power)"},
                "positions": {
                    "type": "array",
                    "description": "ALL stock/ETF holdings in the agentic account",
                    "items": {"type": "object", "properties": {"symbol": {"type": "string"}, "market_value": {"type": "number"}, "risk_at_stop": {"type": "number"}}, "required": ["symbol", "market_value"]},
                },
                "pending_buys": {
                    "type": "array",
                    "description": "ALL unfilled/partially filled buy orders (remaining cost)",
                    "items": {"type": "object", "properties": {"symbol": {"type": "string"}, "estimated_cost": {"type": "number"}, "reserved_risk_at_stop": {"type": "number"}}, "required": ["symbol", "estimated_cost"]},
                },
                "symbol": {"type": "string"},
                "expected_fill_price": {"type": "number"},
                "N": {"type": "number"},
                "order_fee_estimate": {"type": "number"},
            },
            "required": ["net_liquidation_value", "cash", "positions", "pending_buys", "symbol", "expected_fill_price", "N"],
        },
    },
]


def _d(x) -> Decimal:
    return Decimal(str(x or 0))


def _opt(x):
    return None if x is None else _d(x)


def call_tool(name: str, args: dict) -> dict:
    if name == "turtle_strategy_config":
        return signals.load_config()
    if name == "turtle_evaluate_entry":
        return signals.evaluate_entry(
            args["symbol"], args["bars"], args.get("live_price"), bool(args.get("last_bar_complete", False))
        ).to_dict()
    if name == "turtle_evaluate_position":
        return signals.evaluate_position(
            args["symbol"], args["bars"], float(args["live_price"]),
            [float(p) for p in args["unit_fill_prices"]], float(args["entry_N"]),
            bool(args.get("last_bar_complete", False)),
        )
    if name == "turtle_size_buy":
        g = signals.load_config()["portfolio_gates"]
        snap = Snapshot(
            _d(args["net_liquidation_value"]), _d(args["cash"]),
            tuple(Position(p["symbol"], _d(p["market_value"]), _d(p.get("risk_at_stop"))) for p in args["positions"]),
            tuple(PendingBuy(o["symbol"], _d(o["estimated_cost"]), _d(o.get("reserved_risk_at_stop"))) for o in args["pending_buys"]),
        )
        dec = max_buy_shares(
            snap, args["symbol"], _d(args["expected_fill_price"]), _d(args["N"]),
            order_fee_estimate=_d(args.get("order_fee_estimate")),
            max_symbols=g["max_distinct_open_symbols_in_agentic_account"],
            min_cash_fraction=_d(g.get("min_post_trade_cash_as_fraction_of_net_liquidation_value", 0)),
            min_cash_usd=_d(g.get("min_post_trade_cash_usd", 500)),
            exclude_reserve_from_sizing_nav=bool(g.get("exclude_cash_reserve_from_sizing_nav", True)),
            max_symbol_fraction=_opt(g.get("max_gross_market_value_per_symbol_fraction_of_net_liquidation_value")),
            max_symbol_stop_risk_fraction=_opt(g.get("max_risk_at_stop_per_symbol_fraction_of_net_liquidation_value")),
            split_cash_across_open_slots=bool(g.get("split_deployable_cash_evenly_across_open_slots", False)),
        )
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in dec.__dict__.items()}
    raise KeyError(f"Unknown tool: {name}")


def handle(msg: dict):
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        return {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL_VERSION),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "robinhood-turtle-bot", "version": "1.0.0"}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        p = msg.get("params", {})
        try:
            result = call_tool(p.get("name"), p.get("arguments") or {})
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]}
        except Exception as e:  # report tool errors to the model, keep server alive
            return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
    if method == "ping":
        return {}
    if mid is None:
        return None  # notification
    raise NotImplementedError(method)


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        mid = msg.get("id")
        try:
            result = handle(msg)
            if mid is None:
                continue
            out = {"jsonrpc": "2.0", "id": mid, "result": result}
        except NotImplementedError as e:
            out = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {e}"}}
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            out = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
