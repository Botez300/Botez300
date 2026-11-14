import json
import re

import pytest

from src import safety
from src.config import ROOT, load_config


def test_paper_constants_hard_coded():
    assert safety.PAPER_TRADING is True
    assert safety.LIVE_TRADING is False


def test_no_live_order_pathway():
    with pytest.raises(safety.LiveTradingForbiddenError):
        safety.submit_live_order("TQQQ", 1)


@pytest.mark.parametrize("tool", [
    "place_option_order", "place_equity_order", "cancel_option_order", "exercise_option",
    "review_option_order", "decline_trade_approval", "get_accounts", "get_portfolio",
    "mcp__Robinhood_Agentic_Trading__place_option_order", "create_alert", "add_to_watchlist",
])
def test_write_and_account_tools_forbidden(tool):
    assert not safety.is_tool_allowed(tool)
    with pytest.raises(safety.LiveTradingForbiddenError):
        safety.assert_tool_allowed(tool)


@pytest.mark.parametrize("tool", ["get_option_quotes", "get_equity_historicals",
                                  "mcp__Robinhood_Agentic_Trading__get_option_chains"])
def test_read_tools_allowed(tool):
    assert safety.is_tool_allowed(tool)


def test_config_cannot_enable_live(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text((ROOT / "config.yaml").read_text() + "\nlive_trading: true\n")
    with pytest.raises(ValueError):
        load_config(p)


def test_claude_settings_deny_order_tools():
    deny = set(json.loads((ROOT / ".claude" / "settings.json").read_text())["permissions"]["deny"])
    for t in ("place_option_order", "place_equity_order", "cancel_option_order", "exercise_option"):
        assert f"mcp__Robinhood_Agentic_Trading__{t}" in deny


def test_source_contains_no_order_tool_calls():
    pat = re.compile(r"\b(place|cancel|exercise|decline)_(option|equity|crypto|advanced)\w*\(")
    for f in (ROOT / "src").rglob("*.py"):
        if f.name == "safety.py":
            continue
        assert not pat.search(f.read_text()), f"order-tool call pattern in {f}"
