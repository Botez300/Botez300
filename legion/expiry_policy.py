"""PROPOSED session-aware report expiration (Phase 6; NOT owner-approved, NOT enforced by the gate).
Used for compatibility testing only: it never edits an incoming file, and a valid report window never substitutes for
fresh market-data verification (quotes still need <= 60 s age during an OPEN session).

- DAILY: expires at the close of the first trading session that ends after generation (same day if generated before the close).
- WEEKLY: research-valid through the close of the final trading session of the FOLLOWING trading week.
- Candidate: strategy-specific horizon, capped at the report expiration.
- Holiday / DRAFT / TEST_ONLY reports: never actionable, whatever their window."""
from datetime import datetime, timedelta
from . import calendar as cal

def _next_session_close(t):
    d = t.astimezone(cal.NY).date()
    while True:
        if cal.is_trading_day(d):
            c = cal.session_bounds(d)[1]
            if c > t: return c
        d += timedelta(days=1)

def proposed_valid_until(report_type, generated_at):
    if report_type == "DAILY": return _next_session_close(generated_at)
    if report_type == "WEEKLY":
        d = generated_at.astimezone(cal.NY).date()
        mon = d + timedelta(days=(7 - d.weekday()) % 7 or 7)          # Monday of the following week
        last = None
        for k in range(5):
            x = mon + timedelta(days=k)
            if cal.is_trading_day(x): last = x
        while last is None:                                            # whole week closed (theoretical)
            mon += timedelta(days=7); last = next((mon + timedelta(days=k) for k in range(4, -1, -1) if cal.is_trading_day(mon + timedelta(days=k))), None)
        return cal.session_bounds(last)[1]
    raise ValueError(report_type)

def candidate_valid_until(report_valid_until, signal_time, horizon_sessions):
    d, n = signal_time.astimezone(cal.NY).date(), 0
    while n < horizon_sessions:
        d += timedelta(days=1)
        if cal.is_trading_day(d): n += 1
    return min(cal.session_bounds(d)[1], report_valid_until)

def actionable_under_policy(doc, now):
    """Window check only. The real gate still applies every other rule (status, evidence, quotes, risk)."""
    if doc["publication_status"] != "VERIFIED" or doc["test_only"]: return False, "NON_ACTIONABLE_STATUS"
    g = datetime.fromisoformat(doc["generated_at"])
    if cal.state(g) in ("CLOSED_HOLIDAY",) and doc["report_type"] == "DAILY" and "CLOSED" in doc["market_session"]: return False, "HOLIDAY_REPORT"
    vu = proposed_valid_until(doc["report_type"], g)
    return (now < vu), ("WITHIN_PROPOSED_WINDOW" if now < vu else "EXPIRED_UNDER_PROPOSED_POLICY")
