from .base import MarketDataProvider
from .demo import DemoProvider
from .models import TIMEFRAMES, Adjustment, BarSet, DataStatus, ProviderError, SymbolInfo, SymbolNotFound, Verification
from .vendors import AlpacaProvider, PolygonProvider

__all__ = ["TIMEFRAMES", "Adjustment", "AlpacaProvider", "BarSet", "DataStatus", "DemoProvider",
           "MarketDataProvider", "PolygonProvider", "ProviderError", "SymbolInfo", "SymbolNotFound",
           "Verification", "build_provider"]


def build_provider(name: str, *, alpaca_key_id: str = "", alpaca_secret: str = "", alpaca_feed: str = "iex",
                   polygon_api_key: str = "", polygon_base_url: str = "https://api.polygon.io") -> MarketDataProvider:
    """Create the configured provider. Fails loudly rather than falling back to demo data."""
    if name == "demo":
        return DemoProvider()
    if name == "alpaca":
        if not (alpaca_key_id and alpaca_secret):
            raise ProviderError("DATA_PROVIDER=alpaca requires ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY")
        return AlpacaProvider(alpaca_key_id, alpaca_secret, alpaca_feed)
    if name == "polygon":
        if not polygon_api_key:
            raise ProviderError("DATA_PROVIDER=polygon requires POLYGON_API_KEY")
        return PolygonProvider(polygon_api_key, polygon_base_url)
    raise ProviderError(f"unknown DATA_PROVIDER '{name}' (expected demo, alpaca or polygon)")
