from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from threading import Lock

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from legion_data import BarSet, MarketDataProvider, build_provider
from legion_data.base import to_timeframe

from .config import get_settings
from .db import get_db
from .models import AuditLog, Membership, Organization, User
from .security import COOKIE_NAME, RateLimiter, decode_token

WRITE_ROLES = {"owner", "admin", "member"}


@dataclass(frozen=True)
class Principal:
    user: User
    org: Organization
    role: str

    @property
    def org_id(self) -> str:
        return self.org.id


def _token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME)


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    claims = decode_token(_token(request) or "")
    if not claims:
        raise unauthorized
    # Membership is re-checked on every request so removing a member takes effect immediately.
    row = db.execute(
        select(User, Organization, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .join(Organization, Organization.id == Membership.org_id)
        .where(User.id == claims["sub"], Organization.id == claims["org"])
    ).first()
    if row is None:
        raise unauthorized
    return Principal(user=row[0], org=row[1], role=row[2])


def writer(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.role not in WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role is read-only in this workspace")
    return principal


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def audit(db: Session, action: str, *, request: Request | None = None, principal: Principal | None = None,
          target: str | None = None, detail: dict | None = None) -> None:
    db.add(AuditLog(action=action, target=target, detail=detail,
                    org_id=principal.org_id if principal else None,
                    user_id=principal.user.id if principal else None,
                    ip=client_ip(request) if request else None))


@lru_cache
def get_rate_limiter() -> RateLimiter:
    url = get_settings().redis_url
    client = None
    if url:
        import redis

        client = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
    return RateLimiter(client)


class CachedBars:
    """Short-lived in-process cache of daily bars so vendors are not re-queried per indicator or scan row."""

    def __init__(self, provider: MarketDataProvider, ttl: int):
        self.provider = provider
        self._ttl = ttl
        self._data: dict[str, tuple[float, BarSet]] = {}
        self._loading: dict[str, Lock] = {}
        self._lock = Lock()

    def get(self, symbol: str, timeframe: str = "1D", start: date | None = None, end: date | None = None,
            now: datetime | None = None) -> BarSet:
        if start or end or now:
            return self.provider.get_bars(symbol, timeframe, start, end, now)
        key = symbol.strip().upper()
        with self._lock:
            hit = self._data.get(key)
            if hit is not None and hit[0] >= time.monotonic():
                return to_timeframe(hit[1], timeframe)
            key_lock = self._loading.setdefault(key, Lock())
        # One loader per symbol: concurrent requests for a cold symbol wait for it instead of repeating the work.
        with key_lock:
            with self._lock:
                hit = self._data.get(key)
            if hit is not None and hit[0] >= time.monotonic():
                daily = hit[1]
            else:
                daily = self.provider.get_bars(key, "1D")
                with self._lock:
                    if len(self._data) > 5000:
                        self._data.clear()
                    self._data[key] = (time.monotonic() + self._ttl, daily)
        with self._lock:
            self._loading.pop(key, None)
        return to_timeframe(daily, timeframe)

    # The scan engine only needs `get_bars`, `name` and `status`.
    def get_bars(self, symbol: str, timeframe: str = "1D", start=None, end=None, now=None) -> BarSet:
        return self.get(symbol, timeframe)

    def now(self) -> datetime:
        return self.provider.now()

    @property
    def name(self) -> str:
        return self.provider.name

    @property
    def status(self):
        return self.provider.status


@lru_cache
def get_market() -> CachedBars:
    s = get_settings()
    provider = build_provider(
        s.data_provider, alpaca_key_id=s.alpaca_api_key_id, alpaca_secret=s.alpaca_api_secret_key,
        alpaca_feed=s.alpaca_feed, polygon_api_key=s.polygon_api_key, polygon_base_url=s.polygon_base_url)
    return CachedBars(provider, s.bars_cache_seconds)
