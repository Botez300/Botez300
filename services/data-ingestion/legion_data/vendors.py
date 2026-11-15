"""Adapters for licensed market-data vendors.

Both adapters are built from the vendors' public REST documentation and are exercised
in tests against recorded-shape responses (httpx.MockTransport). They have NOT been run
against the live services from this repository's CI: doing so needs your own API keys,
and what you may display or redistribute is governed by your agreement with the vendor.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pandas as pd

from .base import MarketDataProvider, daily_frame
from .calendar import NY as _NY
from .models import Adjustment, DataStatus, ProviderError, SymbolInfo, SymbolNotFound

_RETRY_STATUS = {429, 500, 502, 503, 504}


class _HttpProvider(MarketDataProvider):
    def __init__(self, client: httpx.Client, retries: int = 3, backoff: float = 0.5):
        self._client = client
        self._retries = retries
        self._backoff = backoff

    def _get(self, url: str, params: dict | None = None) -> Any:
        last: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                r = self._client.get(url, params=params)
            except httpx.HTTPError as e:  # network failure / timeout
                last = e
            else:
                if r.status_code == 404:
                    raise SymbolNotFound(f"{self.name}: not found ({r.request.url.path})")
                if r.status_code in (401, 403):
                    raise ProviderError(f"{self.name}: credentials rejected or plan lacks access (HTTP {r.status_code})")
                if r.status_code not in _RETRY_STATUS:
                    if r.is_error:
                        raise ProviderError(f"{self.name}: HTTP {r.status_code}")
                    return r.json()
                last = ProviderError(f"{self.name}: HTTP {r.status_code}")
            if attempt < self._retries:
                time.sleep(self._backoff * 2**attempt)
        raise ProviderError(f"{self.name}: request failed after {self._retries + 1} attempts: {last}")


class AlpacaProvider(_HttpProvider):
    """Alpaca Market Data v2 (stocks/ETFs). Docs: https://docs.alpaca.markets/reference/stockbars"""

    name = "alpaca"
    adjustment = Adjustment.ALL
    license_note = "Alpaca Market Data. Display/redistribution rights depend on your Alpaca agreement and feed."

    def __init__(self, key_id: str, secret: str, feed: str = "iex",
                 data_url: str = "https://data.alpaca.markets", trading_url: str = "https://paper-api.alpaca.markets",
                 transport: httpx.BaseTransport | None = None, **kw):
        headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}
        super().__init__(httpx.Client(headers=headers, timeout=20.0, transport=transport), **kw)
        self._feed, self._data_url, self._trading_url = feed, data_url.rstrip("/"), trading_url.rstrip("/")
        # IEX is a single-venue real-time feed; SIP history is delayed unless the plan says otherwise.
        self.status = DataStatus.DELAYED
        self._assets: list[SymbolInfo] | None = None

    @staticmethod
    def _info(a: dict) -> SymbolInfo:
        return SymbolInfo(a["symbol"], a.get("name") or a["symbol"], a.get("exchange") or "", "stock", provider="alpaca")

    def _all_assets(self) -> list[SymbolInfo]:
        if self._assets is None:
            rows = self._get(f"{self._trading_url}/v2/assets", {"status": "active", "asset_class": "us_equity"})
            self._assets = [self._info(a) for a in rows if a.get("tradable")]
        return self._assets

    def search(self, query: str, limit: int = 20) -> list[SymbolInfo]:
        q = query.strip().upper()
        assets = self._all_assets()
        prefix = sorted((a for a in assets if a.symbol.startswith(q)), key=lambda a: (len(a.symbol), a.symbol))
        by_name = [a for a in assets if q in a.name.upper() and not a.symbol.startswith(q)]
        return (prefix + by_name)[:limit]

    def get_symbol(self, symbol: str) -> SymbolInfo:
        return self._info(self._get(f"{self._trading_url}/v2/assets/{symbol.strip().upper()}"))

    def fetch_daily(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        rows, token = [], None
        while True:
            params = {"timeframe": "1Day", "start": start.isoformat(), "end": end.isoformat(),
                      "adjustment": "all", "feed": self._feed, "limit": 10000}
            if token:
                params["page_token"] = token
            page = self._get(f"{self._data_url}/v2/stocks/{symbol}/bars", params)
            for b in page.get("bars") or []:
                # Daily bars are stamped at the session's midnight in New York, expressed in UTC.
                day = datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(_NY).date()
                rows.append((day, b["o"], b["h"], b["l"], b["c"], b["v"]))
            token = page.get("next_page_token")
            if not token:
                return daily_frame(rows)


class PolygonProvider(_HttpProvider):
    """Polygon.io / Massive aggregates. Docs: https://polygon.io/docs/stocks (base URL is configurable)."""

    name = "polygon"
    adjustment = Adjustment.SPLIT  # `adjusted=true` adjusts for splits, not dividends
    license_note = "Polygon.io / Massive. Display/redistribution rights depend on your subscription tier."

    def __init__(self, api_key: str, base_url: str = "https://api.polygon.io", delayed: bool = True,
                 transport: httpx.BaseTransport | None = None, **kw):
        super().__init__(httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=20.0,
                                      transport=transport), **kw)
        self._base = base_url.rstrip("/")
        self.status = DataStatus.DELAYED if delayed else DataStatus.LIVE

    @staticmethod
    def _info(t: dict) -> SymbolInfo:
        kind = {"CS": "stock", "ETF": "etf", "ADRC": "stock"}.get(t.get("type", ""), "stock")
        return SymbolInfo(t["ticker"], t.get("name") or t["ticker"], t.get("primary_exchange") or "", kind,
                          currency=(t.get("currency_name") or "usd").upper(), provider="polygon")

    def search(self, query: str, limit: int = 20) -> list[SymbolInfo]:
        data = self._get(f"{self._base}/v3/reference/tickers",
                         {"search": query.strip(), "market": "stocks", "active": "true", "limit": limit})
        return [self._info(t) for t in data.get("results") or []]

    def get_symbol(self, symbol: str) -> SymbolInfo:
        data = self._get(f"{self._base}/v3/reference/tickers/{symbol.strip().upper()}")
        if not data.get("results"):
            raise SymbolNotFound(f"polygon: '{symbol}' not found")
        return self._info(data["results"])

    def fetch_daily(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        data = self._get(f"{self._base}/v2/aggs/ticker/{symbol}/range/1/day/{start.isoformat()}/{end.isoformat()}",
                         {"adjusted": "true", "sort": "asc", "limit": 50000})
        rows = []
        for b in data.get("results") or []:
            day = datetime.fromtimestamp(b["t"] / 1000.0, tz=UTC).astimezone(_NY).date()
            rows.append((day, b["o"], b["h"], b["l"], b["c"], b["v"]))
        return daily_frame(rows)



