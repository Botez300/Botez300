"""US equity-exchange calendar (NYSE rules), America/New_York. Rule-based, so it is deterministic and offline.
Verify against the exchange's published calendar each year; the rules are encoded, not downloaded."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
OPEN, CLOSE, EARLY_CLOSE = time(9, 30), time(16, 0), time(13, 0)

def _nth(y, m, wd, n):
    d = date(y, m, 1); d += timedelta((wd - d.weekday()) % 7); return d + timedelta(7 * (n - 1))
def _last(y, m, wd):
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(1); return d - timedelta((d.weekday() - wd) % 7)
def _easter(y):
    a, b, c = y % 19, y // 100, y % 100; d, e = b // 4, b % 4; f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30; i, k = c // 4, c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451; mo = (h + l - 7 * m + 114) // 31; da = (h + l - 7 * m + 114) % 31 + 1
    return date(y, mo, da)
def _obs(d):
    return d - timedelta(1) if d.weekday() == 5 else d + timedelta(1) if d.weekday() == 6 else d

def holidays(y):
    h = {_nth(y, 1, 0, 3), _nth(y, 2, 0, 3), _easter(y) - timedelta(2), _last(y, 5, 0), _obs(date(y, 7, 4)),
         _nth(y, 9, 0, 1), _nth(y, 11, 3, 4), _obs(date(y, 12, 25))}
    if y >= 2022: h.add(_obs(date(y, 6, 19)))
    if date(y, 1, 1).weekday() != 5: h.add(_obs(date(y, 1, 1)))      # Sat 1 Jan: no holiday observed
    return h

def is_trading_day(d): return d.weekday() < 5 and d not in holidays(d.year)
def early_close(d):
    if not is_trading_day(d): return False
    return d == _nth(d.year, 11, 3, 4) + timedelta(1) or (d.month, d.day) in ((12, 24), (7, 3))
def close_time(d): return EARLY_CLOSE if early_close(d) else CLOSE
def session_bounds(d):
    return datetime.combine(d, OPEN, NY), datetime.combine(d, close_time(d), NY)

def state(now: datetime) -> str:
    """OPEN | PRE_MARKET | AFTER_HOURS | CLOSED_HOLIDAY | CLOSED_WEEKEND (naive datetimes are rejected)."""
    if now.tzinfo is None: raise ValueError("timezone-aware datetime required")
    n = now.astimezone(NY); d = n.date()
    if d.weekday() >= 5: return "CLOSED_WEEKEND"
    if d in holidays(d.year): return "CLOSED_HOLIDAY"
    o, c = session_bounds(d)
    return "PRE_MARKET" if n < o else "OPEN" if n < c else "AFTER_HOURS"

def last_session_date(now: datetime):
    n = now.astimezone(NY); d = n.date()
    if is_trading_day(d) and n >= session_bounds(d)[0]: return d
    d -= timedelta(1)
    while not is_trading_day(d): d -= timedelta(1)
    return d
def utc(dt): return dt.astimezone(timezone.utc)
