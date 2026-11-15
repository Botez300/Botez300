"""Deterministic synthetic market for demo mode.

Everything here is SIMULATED. Tickers and company names are fictional and prices come
from a seeded factor model (market + sector + idiosyncratic regime-switching returns),
so they are reproducible but bear no relation to any real security. Used when no
licensed data provider is configured; never mixed into provider-backed research.
"""

from __future__ import annotations

import hashlib
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from . import calendar
from .base import COLUMNS, MarketDataProvider, utcnow
from .models import Adjustment, DataStatus, SymbolInfo, SymbolNotFound

MODEL_VERSION = "demo-1"
EPOCH = date(2014, 1, 2)
MARKET = "SIMX"
EXCHANGE = "SIM"

_SECTORS: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "Technology": ("SXTK", [("ALFA", "Alfa Dynamics", "Software"), ("QBIT", "Qubit Foundry", "Semiconductors"),
                            ("NEXA", "Nexa Cloudworks", "Software"), ("VYRO", "Vyro Devices", "Hardware"),
                            ("LUMO", "Lumo Photonics", "Semiconductors"), ("ZENT", "Zentry Systems", "IT Services")]),
    "Health Care": ("SXHC", [("MEDA", "Medara Therapeutics", "Biotechnology"), ("CURA", "Curavia Health", "Providers"),
                             ("GENX", "Genoxa Labs", "Biotechnology"), ("ORTH", "Orthelion Devices", "Medical Devices"),
                             ("PHAR", "Pharos Pharma", "Pharmaceuticals"), ("VITA", "Vitaline Diagnostics", "Diagnostics")]),
    "Financials": ("SXFN", [("BANC", "Bancora Holdings", "Banks"), ("LEDG", "Ledgerline Capital", "Capital Markets"),
                            ("INSU", "Insura Mutual", "Insurance"), ("PAYX", "Payonix Networks", "Payments"),
                            ("TRST", "Trustmark Northern", "Banks"), ("ASTM", "Astrum Asset Mgmt", "Asset Management")]),
    "Consumer Discretionary": ("SXCD", [("MOTO", "Motiva Motors", "Automobiles"), ("SHOP", "Shopwell Retail", "Retail"),
                                        ("LUXE", "Luxera Brands", "Apparel"), ("TRVL", "Travelon Group", "Leisure"),
                                        ("HOMR", "Homerun Builders", "Homebuilding"), ("DINE", "Dineworks Inc", "Restaurants")]),
    "Consumer Staples": ("SXCS", [("FARM", "Farmstead Foods", "Food Products"), ("BEVY", "Bevyline Drinks", "Beverages"),
                                  ("CLEN", "Cleanwell Home", "Household Products"), ("GROC", "Grocerama", "Food Retail"),
                                  ("SNAK", "Snackwise Co", "Food Products")]),
    "Industrials": ("SXIN", [("AERO", "Aerovance", "Aerospace"), ("RAIL", "Railhead Freight", "Transportation"),
                             ("MACH", "Machina Tools", "Machinery"), ("BLDR", "Buildright Corp", "Construction"),
                             ("LOGI", "Logistar", "Logistics"), ("ROBO", "Robotica Works", "Machinery")]),
    "Energy": ("SXEN", [("PETR", "Petrana Energy", "Oil & Gas"), ("DRIL", "Drillcore Services", "Energy Services"),
                        ("PIPE", "Pipeway Midstream", "Midstream"), ("SOLR", "Solarix Power", "Renewables"),
                        ("FUEL", "Fuelgate Refining", "Refining")]),
    "Materials": ("SXMT", [("STEL", "Stelcor Metals", "Steel"), ("CHEM", "Chemvera", "Chemicals"),
                           ("MINE", "Minecrest Resources", "Mining"), ("PACK", "Packwell", "Packaging"),
                           ("LITH", "Lithara Minerals", "Mining")]),
    "Utilities": ("SXUT", [("GRID", "Gridstone Electric", "Electric Utilities"), ("AQUA", "Aquaterra Water", "Water Utilities"),
                           ("VOLT", "Voltaic Power", "Electric Utilities"), ("GASC", "Gascony Distribution", "Gas Utilities")]),
    "Real Estate": ("SXRE", [("REIT", "Realtora Trust", "Diversified REITs"), ("TOWR", "Towerline REIT", "Specialized REITs"),
                             ("WARE", "Warehouse Partners", "Industrial REITs"), ("APTS", "Aptside Living", "Residential REITs")]),
    "Communication Services": ("SXCM", [("STRM", "Streamora Media", "Entertainment"), ("TELE", "Telenova", "Telecom"),
                                        ("ADVT", "Adverta Digital", "Interactive Media"), ("GAME", "Gamewright Studios", "Entertainment"),
                                        ("WAVE", "Wavelink Wireless", "Telecom")]),
}

_MARKET_STATES = [(0.0007, 0.007), (0.0003, 0.011), (-0.0009, 0.019), (0.0011, 0.009)]
_SECTOR_STATES = [(0.0003, 0.005), (-0.0003, 0.006), (0.0, 0.004)]
_STOCK_STATES = [(0.0011, 0.014), (0.0, 0.012), (-0.0010, 0.018), (0.0002, 0.006)]


def _build_universe() -> dict[str, SymbolInfo]:
    out = {MARKET: SymbolInfo(MARKET, "Simulated Market Index ETF", EXCHANGE, "etf", provider="demo")}
    for sector, (etf, names) in _SECTORS.items():
        out[etf] = SymbolInfo(etf, f"Simulated {sector} Sector ETF", EXCHANGE, "etf", sector, provider="demo")
        for sym, name, industry in names:
            out[sym] = SymbolInfo(sym, f"{name} (simulated)", EXCHANGE, "stock", sector, industry, provider="demo")
    return out


UNIVERSE: dict[str, SymbolInfo] = _build_universe()
_SECTOR_OF_ETF = {etf: sector for sector, (etf, _) in _SECTORS.items()}


def _rng(*keys: str) -> np.random.Generator:
    digest = hashlib.sha256("|".join((MODEL_VERSION, *keys)).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def _unit(*keys: str) -> float:
    return float(_rng(*keys).random())


def _regime_returns(key: str, n: int, states: list[tuple[float, float]], mean_len: int) -> tuple[np.ndarray, np.ndarray]:
    """Regime-switching Gaussian log returns and the per-day sigma. Prefix-stable in n."""
    switch = _rng(key, "switch").random(n) < 1.0 / mean_len
    pick = _rng(key, "pick").integers(0, len(states), n)
    z = _rng(key, "z").standard_normal(n)
    state = int(_rng(key, "init").integers(0, len(states)))
    mu, sigma = np.empty(n), np.empty(n)
    for i in range(n):
        if switch[i]:
            state = int(pick[i])
        mu[i], sigma[i] = states[state]
    return mu + sigma * z, sigma


@lru_cache(maxsize=512)
def _series(symbol: str, n: int) -> tuple[np.ndarray, ...]:
    info = UNIVERSE[symbol]
    market, m_sigma = _regime_returns("market", n, _MARKET_STATES, 90)
    if symbol == MARKET:
        ret, sigma = market, m_sigma
    else:
        sector, s_sigma = _regime_returns(f"sector:{info.sector}", n, _SECTOR_STATES, 120)
        if info.asset_type == "etf":
            ret, sigma = market + sector, np.hypot(m_sigma, s_sigma)
        else:
            scale = 0.7 + 0.9 * _unit(symbol, "scale")
            beta = 0.6 + 0.9 * _unit(symbol, "beta")
            idio, i_sigma = _regime_returns(f"stock:{symbol}", n, _STOCK_STATES, 110)
            ret = beta * market + 0.8 * sector + scale * idio
            sigma = np.sqrt((beta * m_sigma) ** 2 + (0.8 * s_sigma) ** 2 + (scale * i_sigma) ** 2)
    p0 = 12.0 + 180.0 * _unit(symbol, "p0")
    close = p0 * np.exp(np.cumsum(ret))
    prev = np.concatenate([[p0], close[:-1]])
    open_ = prev * np.exp(0.3 * ret + 0.15 * sigma * _rng(symbol, "gap").standard_normal(n))
    hi = np.maximum(open_, close) * np.exp(0.5 * sigma * np.abs(_rng(symbol, "hi").standard_normal(n)))
    lo = np.minimum(open_, close) * np.exp(-0.5 * sigma * np.abs(_rng(symbol, "lo").standard_normal(n)))
    base = 10 ** (5.6 + 1.6 * _unit(symbol, "vol"))
    volume = base * np.exp(0.35 * _rng(symbol, "v").standard_normal(n)) * (1.0 + 5.0 * np.abs(ret) / 0.02)
    o, c = np.maximum(np.round(open_, 2), 0.01), np.maximum(np.round(close, 2), 0.01)
    h = np.maximum(np.round(hi, 2), np.maximum(o, c))
    l = np.maximum(np.minimum(np.round(lo, 2), np.minimum(o, c)), 0.01)
    return o, h, l, c, np.round(volume / 100.0) * 100.0


class DemoProvider(MarketDataProvider):
    name = "demo"
    status = DataStatus.SIMULATED
    adjustment = Adjustment.NOT_APPLICABLE
    license_note = "Synthetic data generated locally; fictional tickers. Not real market data."

    def __init__(self, clock=utcnow):
        self._clock = clock

    def now(self):
        return self._clock()

    def search(self, query: str, limit: int = 20) -> list[SymbolInfo]:
        q = query.strip().upper()
        if not q:
            return list(UNIVERSE.values())[:limit]
        prefix = [s for s in UNIVERSE.values() if s.symbol.startswith(q)]
        by_name = [s for s in UNIVERSE.values() if q in s.name.upper() and s not in prefix]
        return (prefix + by_name)[:limit]

    def get_symbol(self, symbol: str) -> SymbolInfo:
        try:
            return UNIVERSE[symbol.strip().upper()]
        except KeyError:
            raise SymbolNotFound(f"'{symbol}' is not in the simulated universe") from None

    def universe(self) -> list[SymbolInfo]:
        return list(UNIVERSE.values())

    def fetch_daily(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        last = min(end, calendar.last_completed_session(self._clock()))
        days = calendar.sessions(EPOCH, last)
        o, h, l, c, v = _series(symbol, len(days))
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in days], tz="UTC", name="time")
        frame = pd.DataFrame(dict(zip(COLUMNS, (o, h, l, c, v))), index=idx)
        return frame[frame.index >= pd.Timestamp(start, tz="UTC")]
