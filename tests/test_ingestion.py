import json, os, shutil, pytest
from datetime import datetime, timezone
from legion.validator import validate
from legion.ledger import Ledger
from legion.sources import LocalDirSource
from legion.pipeline import Pipeline
from legion.watcher import Watcher
from legion.engines import StockEngine, OptionsEngine
from legion.orders import PaperOrderGateway, LiveTradingForbidden

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "03_Verified_Signals")
NOW = datetime(2026, 11, 26, 17, 0, tzinfo=timezone.utc)
FILES = {"TEST_ONLY_DAILY_2026-11-26_01.json": 598, "TEST_ONLY_WEEKLY_2026-11-26_01.json": 600}

def good(**kw):
    d = {"schema_version": "1.0", "scanner_rules_version": "r1", "report_id": "DAILY_2026-11-27_01",
         "report_type": "DAILY", "generated_at": "2026-11-26T16:00:00Z", "market_data_as_of": "2026-11-26T15:59:00Z",
         "valid_until": "2026-11-27T21:00:00Z", "market_session": "REGULAR", "market_regime": "RISK_ON",
         "leading_sectors": [], "leading_industries": [], "publication_status": "VERIFIED", "test_only": False,
         "research_only": True, "execution_authorized": False, "sources": [], "strategy_sections": [],
         "candidates": [], "missing_data": []}
    d.update(kw); return d
def v(d, name=None, **kw):
    raw = json.dumps(d).encode(); return validate(raw, name or d["report_id"] + ".json", NOW, **kw)

class Q:
    def __init__(s, px): s.px = px
    def last_price(s, sym): return s.px.get(sym)

@pytest.mark.parametrize("name,size", FILES.items())
def test_real_files_valid_but_rejected(name, size):
    raw = open(os.path.join(FIX, name), "rb").read()
    r = validate(raw, name, NOW, expected_size=size)
    assert r.schema_ok and r.integrity_ok and r.safety_ok
    assert r.report_id == name[:-5]
    assert not r.admitted and "TEST_ONLY" in r.reasons
    # also rejected for missing mandatory fields / invalid status / no expiry
    assert any(x.startswith("MISSING_MANDATORY") for x in r.reasons)
    assert any(x.startswith("INVALID_STATUS") for x in r.reasons)

def test_real_files_zero_candidates():
    for n in FILES:
        d = json.load(open(os.path.join(FIX, n)))
        assert d["candidates"] == [] and d["execution_authorized"] is False and d["test_only"] is True

def test_test_file_with_candidate_is_unsafe():
    r = v(good(test_only=True, candidates=[{"symbol": "AAPL"}]))
    assert not r.safety_ok and not r.admitted

def test_size_mismatch():
    assert not v(good(), expected_size=1).integrity_ok

def test_valid_report_admitted():
    r = v(good()); assert r.admitted, r.reasons

@pytest.mark.parametrize("kw,reason", [
    ({"valid_until": "2026-11-26T16:59:00Z"}, "EXPIRED"),
    ({"valid_until": None}, "MISSING_EXPIRY"),
    ({"generated_at": None}, "MISSING_MANDATORY"),
    ({"publication_status": "DRAFT"}, "INVALID_STATUS"),
    ({"publication_status": "BOGUS"}, "SCHEMA"),
    ({"execution_authorized": True}, "EXECUTION_AUTHORIZED_NOT_ALLOWED"),
    ({"test_only": True}, "TEST_ONLY"),
    ({"schema_version": "2.0"}, "SCHEMA"),
])
def test_rejections(kw, reason):
    r = v(good(**kw)); assert not r.admitted and any(reason in x for x in r.reasons), r.reasons

def test_missing_field_and_bad_json():
    d = good(); del d["candidates"]
    assert not v(d).schema_ok
    assert "INVALID_JSON" in validate(b"{nope", "x.json", NOW).reasons[0]

def test_filename_mismatch():
    assert any("FILENAME_MISMATCH" in x for x in v(good(), "other.json").reasons)

def test_duplicates():
    assert "DUPLICATE_REPORT_ID" in v(good(), seen_ids={"DAILY_2026-11-27_01"}).reasons
    r = v(good()); assert "DUPLICATE_CONTENT_HASH" in v(good(), seen_hashes={r.sha256}).reasons

def setup(tmp_path, quotes=None):
    src = tmp_path / "inbox"; src.mkdir()
    gw = PaperOrderGateway(str(tmp_path / "paper.jsonl"))
    eng = [StockEngine(gw, Q(quotes or {})), OptionsEngine(gw, Q(quotes or {}))]
    p = Pipeline(Ledger(str(tmp_path / "ledger.json")), eng, str(tmp_path / "quar"))
    return src, gw, Watcher(LocalDirSource(str(src)), p), p

def test_watcher_end_to_end_real_files(tmp_path):
    src, gw, w, p = setup(tmp_path)
    for n in FILES: shutil.copy(os.path.join(FIX, n), src)
    res = w.poll_once(NOW)
    assert len(res) == 2 and not any(r.admitted for r in res)
    assert gw.orders == []
    assert w.poll_once(NOW) == []                       # no reprocessing
    w2 = Watcher(LocalDirSource(str(src)), p)           # restart: new watcher, same ledger
    assert all("DUPLICATE_CONTENT_HASH" in r.reasons for r in w2.poll_once(NOW))
    assert len(p.ledger.d["entries"]) == 2              # duplicates not re-recorded
    assert len(os.listdir(tmp_path / "quar")) == 2

def test_watcher_detects_new_file_and_paper_order(tmp_path):
    src, gw, w, p = setup(tmp_path, {"AAPL": 100.0, "MSFT": 300.0})
    assert w.poll_once(NOW) == []
    d = good(candidates=[{"symbol": "AAPL", "reference_price": 100.2},
                         {"symbol": "MSFT", "reference_price": 250.0}])   # MSFT fails independent check
    (src / "DAILY_2026-11-27_01.json").write_text(json.dumps(d))
    r, = w.poll_once(NOW)
    assert r.admitted
    assert [o["symbol"] for o in gw.orders] == ["AAPL"] and gw.orders[0]["mode"] == "PAPER"

def test_no_live_orders():
    gw = PaperOrderGateway("/dev/null")
    with pytest.raises(LiveTradingForbidden): gw.submit({"symbol": "X", "live": True})
