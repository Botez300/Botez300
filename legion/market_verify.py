"""Independent market-data check. Provider is injected: in a Claude session it wraps the read-only
Robinhood MCP quote tools; in tests it is a stub. No order tools are ever referenced."""
from typing import Protocol
class QuoteProvider(Protocol):
    def last_price(self, symbol: str) -> float | None: ...

def verify_candidate(c: dict, provider: QuoteProvider, tol=0.01):
    ref, px = c.get("reference_price"), provider.last_price(c["symbol"])
    if px is None: return False, "NO_INDEPENDENT_QUOTE"
    if ref is None: return False, "NO_REFERENCE_PRICE"
    return (abs(px - ref) / ref <= tol), f"ref={ref} independent={px}"
