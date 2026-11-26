import json, os, pytest
from datetime import datetime, timedelta, timezone
from legion import calendar as cal
from legion.rh import Quote, Bar, Contract

REC = os.path.join(os.path.dirname(__file__), "..", "fixtures", "robinhood_recorded")
# Tuesday 2026-12-01 11:00 ET: regular session open. SYNTHETIC clock for order-path tests.
NOW = datetime(2026, 12, 1, 11, 0, tzinfo=cal.NY).astimezone(timezone.utc)

def ts(**k): return (NOW + timedelta(**k)).isoformat().replace("+00:00", "Z")

def report(cands=None, **kw):
    d = {"schema_version": "1.0", "scanner_rules_version": "r1", "report_id": "DAILY_2026-12-01_01", "report_type": "DAILY",
         "generated_at": ts(hours=-2), "market_data_as_of": ts(hours=-2), "valid_until": ts(hours=8), "market_session": "REGULAR",
         "market_regime": "RISK_ON", "leading_sectors": ["Tech"], "leading_industries": [], "publication_status": "VERIFIED",
         "test_only": False, "research_only": True, "execution_authorized": False, "sources": [], "strategy_sections": [],
         "candidates": cands if cands is not None else [], "missing_data": []}
    d.update(kw); return d

def cand(**kw):
    c = {"ticker": "ACME", "company_name": "Acme Corp", "originating_strategy": "TURTLE", "additional_qualifying_strategies": [],
         "signal_id": "SIG_ACME_20261201", "signal_timestamp": ts(hours=-2), "signal_classification": "BUY_NOW", "verification_status": "VERIFIED",
         "individual_criteria_results": [{"criterion_id": "C1", "status": "PASS"}], "current_price": 100.0, "proposed_entry": 100.0,
         "entry_zone": {"low": 99.0, "high": 101.0}, "technical_invalidation": 95.0, "proposed_price_targets": [110.0, 120.0],
         "relative_strength_vs_spy": 1.2, "volume_confirmation": {"confirmed": True, "ratio": 1.8}, "earnings_date": None,
         "options_eligibility": {"eligible": True, "notes": None}, "trade_direction": "LONG", "risk_flags": [],
         "source_references": ["scan:1"], "missing_data": [], "expiration_timestamp": ts(hours=6)}
    c.update(kw); return c

def raw(d): return json.dumps(d).encode()

class Item:
    def __init__(self, name, data, age=1e9, md5=None):
        self.name, self._d, self.size, self.age, self.md5, self.token = name, data, len(data), age, md5, name + str(len(data))
    def read(self): return self._d

def bars(n=260, base=50.0, step=0.2, vol=1_000_000, last_vol=2_000_000, last_hi=None):
    out, t0 = [], NOW - timedelta(days=n * 7 // 5 + 5)
    for i in range(n):
        c = base + step * i
        out.append(Bar(t0 + timedelta(days=i), c, c + 1, c - 1, c, last_vol if i == n - 1 else vol))
    return out

@pytest.fixture
def now(): return NOW
