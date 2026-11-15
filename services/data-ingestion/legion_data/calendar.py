"""NYSE regular-session calendar (full-day closures only), computed from the published rules.

Covers the standing holidays since 2012. One-off closures (weather, national days of
mourning) and early closes are NOT modelled; data-quality checks report sessions a
provider omits rather than assuming this calendar is authoritative.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
SESSION_CLOSE = time(16, 0)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _observed(d: date) -> date | None:
    if d.weekday() == 5:  # Saturday -> Friday, except when that crosses into the prior year (New Year's)
        prev = d - timedelta(days=1)
        return prev if prev.year == d.year else None
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=64)
def holidays(year: int) -> frozenset[date]:
    days = [
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _easter(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),
    ]
    if year >= 2022:
        days.append(_observed(date(year, 6, 19)))  # Juneteenth
    return frozenset(d for d in days if d is not None)


def is_session(d: date) -> bool:
    return d.weekday() < 5 and d not in holidays(d.year)


@lru_cache(maxsize=256)
def _sessions(start: date, end: date) -> tuple[date, ...]:
    out, d = [], start
    while d <= end:
        if is_session(d):
            out.append(d)
        d += timedelta(days=1)
    return tuple(out)


def sessions(start: date, end: date) -> list[date]:
    return list(_sessions(start, end))


def last_completed_session(now: datetime) -> date:
    """The most recent session whose regular close (16:00 New York) is at or before `now`."""
    local = now.astimezone(NY)
    d = local.date()
    if not (is_session(d) and local.time() >= SESSION_CLOSE):
        d -= timedelta(days=1)
    while not is_session(d):
        d -= timedelta(days=1)
    return d


def session_forming(d: date, now: datetime) -> bool:
    """True if session `d` has not yet closed at `now`."""
    return now.astimezone(NY) < datetime.combine(d, SESSION_CLOSE, NY)
