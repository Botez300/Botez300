"""Deterministic operating calendar (America/New_York, NYSE rules from legion.calendar).
Phases are windows, not assumptions that a report has arrived: ingestion still requires the file to exist and validate."""
from datetime import time, timedelta, datetime
from . import calendar as cal

def phase(now):
    n = now.astimezone(cal.NY); d = n.date(); t = n.time()
    if d.weekday() == 6: return "SUNDAY_WEEKLY_WINDOW" if t >= time(19) else "IDLE"
    if not cal.is_trading_day(d): return "NON_TRADING_DAY"
    close = cal.close_time(d); post = (datetime.combine(d, close) + timedelta(minutes=15)).time()
    if time(9) <= t < time(9, 30): return "DAILY_REPORT_WINDOW"
    if time(9, 30) <= t < close: return "MARKET_OPEN"
    if close <= t < post: return "POST_CLOSE_SETTLE"
    if post <= t < time(20): return "POST_CLOSE_RECONCILE"
    return "IDLE"

def weekly_deadline_passed(now, hh=21):
    n = now.astimezone(cal.NY); return n.weekday() == 6 and n.time() >= time(hh)
