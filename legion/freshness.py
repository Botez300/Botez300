"""Quote-freshness gate. A quote is ACTIONABLE only if the regular session is open now and the quote was
printed during *this* session within max_age. Holiday / previous-session / extended-hours prints are not live."""
from datetime import timedelta
from . import calendar as cal

def assess(ts, now, max_age_s=60):
    """Returns (actionable: bool, reason: str)."""
    if ts is None: return False, "NO_TIMESTAMP"
    if ts.tzinfo is None: return False, "NAIVE_TIMESTAMP"
    st = cal.state(now)
    if st != "OPEN": return False, f"MARKET_{st}"
    if ts > now + timedelta(seconds=5): return False, "FUTURE_TIMESTAMP"
    o, c = cal.session_bounds(now.astimezone(cal.NY).date())
    if ts < o: return False, "QUOTE_FROM_PREVIOUS_SESSION_OR_PREMARKET"
    if (now - ts).total_seconds() > max_age_s: return False, f"STALE_{int((now - ts).total_seconds())}s"
    return True, "FRESH"
