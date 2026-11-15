"""Plan entitlements as configuration. Code asks `limit(plan, key)`; nothing hardcodes a tier name.

Only limits for features that exist today are listed. Prices and billing are not implemented yet.
"""

from __future__ import annotations

PLANS: dict[str, dict[str, int]] = {
    "free": {"max_watchlists": 3, "max_symbols_per_watchlist": 30, "max_saved_scans": 5, "max_scan_symbols": 100},
    "pro": {"max_watchlists": 25, "max_symbols_per_watchlist": 200, "max_saved_scans": 50, "max_scan_symbols": 1000},
    "quant": {"max_watchlists": 100, "max_symbols_per_watchlist": 500, "max_saved_scans": 250, "max_scan_symbols": 5000},
    "institutional": {"max_watchlists": 1000, "max_symbols_per_watchlist": 2000, "max_saved_scans": 2000,
                      "max_scan_symbols": 10000},
}
DEFAULT_PLAN = "free"


def limit(plan: str, key: str) -> int:
    return PLANS.get(plan, PLANS[DEFAULT_PLAN])[key]
