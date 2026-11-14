"""Hard-coded PAPER-TRADING execution boundary.

This module is the single source of truth for the system's execution mode.
There is deliberately NO configuration switch, environment variable or CLI
flag that can enable live trading. The constants below are checked at import
time and by every simulated execution path.

The Python engine never talks to a broker. Robinhood data reaches it only as
read-only JSON snapshots captured by Claude Code through the official
Robinhood Trading MCP (see ``src/broker/robinhood_mcp.py``). Every snapshot
manifest is validated against ``READ_ONLY_MCP_TOOLS`` before import.
"""

from __future__ import annotations

from typing import Final

PAPER_TRADING: Final[bool] = True
LIVE_TRADING: Final[bool] = False
EXECUTION_LABEL: Final[str] = "PAPER"

# Read-only Robinhood MCP tools the system may consume data from.
READ_ONLY_MCP_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "get_equity_quotes",
        "get_equity_historicals",
        "get_option_chains",
        "get_option_instruments",
        "get_option_quotes",
        "get_option_historicals",
        "get_index_quotes",
        "get_index_historicals",
        "get_indexes",
        "get_earnings_calendar",
        "search",
    }
)

# Any MCP tool whose name starts with one of these prefixes, or appears in the
# explicit set, is excluded from the application's permitted operations.
FORBIDDEN_MCP_TOOL_PREFIXES: Final[tuple[str, ...]] = (
    "place_",
    "cancel_",
    "review_",
    "preview_",
    "exercise_",
    "decline_",
    "create_",
    "update_",
    "delete_",
    "add_",
    "remove_",
    "follow_",
    "unfollow_",
    "mark_",
    "set_",
)
FORBIDDEN_MCP_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "get_accounts",  # account identifiers are not needed by the engine
        "get_portfolio",
        "get_bank_accounts",
        "get_banking_transactions",
        "get_credit_card_account",
        "get_credit_transactions",
        "get_equity_positions",
        "get_option_positions",
        "get_crypto_positions",
        "get_equity_orders",
        "get_option_orders",
        "get_trade_approvals",
        "get_trade_approval_setting",
    }
)


class LiveTradingForbiddenError(RuntimeError):
    """Raised whenever anything attempts to leave the paper boundary."""


def _strip_server_prefix(tool_name: str) -> str:
    # "mcp__Robinhood_Agentic_Trading__get_option_quotes" -> "get_option_quotes"
    return tool_name.rsplit("__", 1)[-1]


def is_tool_allowed(tool_name: str) -> bool:
    name = _strip_server_prefix(tool_name)
    if name in FORBIDDEN_MCP_TOOLS:
        return False
    if any(name.startswith(p) for p in FORBIDDEN_MCP_TOOL_PREFIXES):
        return False
    return name in READ_ONLY_MCP_TOOLS


def assert_tool_allowed(tool_name: str) -> None:
    if not is_tool_allowed(tool_name):
        raise LiveTradingForbiddenError(
            f"MCP tool '{tool_name}' is not in the read-only allowlist; "
            "the paper engine refuses data produced by it."
        )


def assert_paper_mode() -> None:
    """Called by every simulated execution path."""
    if PAPER_TRADING is not True or LIVE_TRADING is not False:  # pragma: no cover
        raise LiveTradingForbiddenError("Execution boundary violated: system is PAPER ONLY.")


def submit_live_order(*_args: object, **_kwargs: object) -> None:
    """There is no production order pathway. This always raises."""
    raise LiveTradingForbiddenError(
        "Live order submission does not exist in this system. PAPER TRADING ONLY."
    )


# Import-time self-check.
assert_paper_mode()
