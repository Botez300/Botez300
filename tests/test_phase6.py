"""Phase 6 tests (SYNTHETIC unless RECORDED). No authentication; the emergency-stop drill runs the real service entry point."""
import copy, hashlib, json, os, subprocess, sys, pytest
from datetime import datetime, timedelta, timezone
from conftest import NOW, cand, report, raw, Item
from legion import calendar as cal, expiry_policy as XP, activation as ACT
from legion.backtest import contraction as CT, parabolic as PB
from legion.drive_publish import OutboxPublisher, PublishError, folder_for
from test_phase5 import parabola, P30, GEN, SHA

ROOT = os.path.join(os.path.dirname(__file__), "..")

# ---------------- contraction variants -----------------------------------------------------------------------------------
def test_three_contraction_variants_are_distinct_and_named():
    b = parabola([15.0]); r = CT.compare(b, 30, 33)
    assert set(r) == set(CT.METHODS) and len({round(v, 6) for v in r.values()}) == 3
    assert r["ATR5_OVER_ATR14"] > 0.8 >= r["CONS_TR_OVER_ATR14_ANCHOR"] and r["CONS_TR_OVER_ATR14_CURRENT"] <= 0.8   # ATR5 window still holds the spike
    with pytest.raises(ValueError): CT.ratio("ATR5_WHATEVER", b, 30, 33)
def test_defaults_unchanged_no_silent_substitution():
    assert PB.DEFAULT["contraction_method"] == "CONS_TR_OVER_ATR14_ANCHOR"
    s = PB.setup_at(parabola([15.0]), 33, P30); assert s["contraction_method"] == "CONS_TR_OVER_ATR14_ANCHOR"
    assert PB.setup_at(parabola([15.0]), 33, {**P30, "contraction_method": "ATR5_OVER_ATR14"}) is None     # behaviour genuinely differs
    src = open(os.path.join(ROOT, "legion", "scanners", "entry.py")).read(); assert 't.get("contraction_method", "CONS_TR_OVER_ATR14_CURRENT")' in src

# ---------------- proposed session-aware expiry (compatibility only) -----------------------------------------------------------
NY = cal.NY
@pytest.mark.parametrize("gen,exp", [(datetime(2026, 12, 1, 9, 0, tzinfo=NY), datetime(2026, 12, 1, 16, 0, tzinfo=NY)),
    (datetime(2026, 12, 1, 17, 0, tzinfo=NY), datetime(2026, 12, 2, 16, 0, tzinfo=NY)),
    (datetime(2026, 11, 26, 12, 35, 41, tzinfo=NY), datetime(2026, 11, 27, 13, 0, tzinfo=NY))])      # Thanksgiving -> next early close
def test_daily_expiry_at_applicable_session_close(gen, exp):
    assert XP.proposed_valid_until("DAILY", gen) == exp
def test_weekly_expiry_through_following_week():
    # Sunday rebuild covers the trading week that starts the next day
    assert XP.proposed_valid_until("WEEKLY", datetime(2026, 11, 29, 19, 0, tzinfo=NY)) == datetime(2026, 12, 4, 16, 0, tzinfo=NY)
    # Christmas Friday 2026-12-25 is closed -> last session Thu 2026-12-24, an early close
    assert XP.proposed_valid_until("WEEKLY", datetime(2026, 12, 20, 19, 0, tzinfo=NY)) == datetime(2026, 12, 24, 13, 0, tzinfo=NY)
def test_candidate_capped_by_report():
    rep = datetime(2026, 12, 1, 16, tzinfo=NY)
    assert XP.candidate_valid_until(rep, datetime(2026, 12, 1, 9, tzinfo=NY), 5) == rep
def test_genuine_report_stays_nonactionable_under_proposed_policy_and_file_untouched():
    b = open(GEN, "rb").read(); doc = json.loads(b)
    ok, why = XP.actionable_under_policy(doc, datetime(2026, 11, 26, 18, tzinfo=timezone.utc)); assert not ok and why == "NON_ACTIONABLE_STATUS"
    d2 = {**doc, "publication_status": "VERIFIED"}                                          # hypothetical: still a holiday report
    assert XP.actionable_under_policy(d2, datetime(2026, 11, 26, 18, tzinfo=timezone.utc)) == (False, "HOLIDAY_REPORT")
    assert hashlib.sha256(open(GEN, "rb").read()).hexdigest() == SHA
def test_valid_window_never_replaces_quote_freshness():
    from legion import freshness
    assert not freshness.assess(datetime(2026, 12, 1, 14, 0, tzinfo=NY) - timedelta(minutes=5), datetime(2026, 12, 1, 14, 0, tzinfo=NY))[0]

# ---------------- activation gates / observe-only --------------------------------------------------------------------------------
def gate_cfg(tmp, **k):
    c = {"paper_start_equity": None, "strategy_variants": {"PARABOLIC_MOMENTUM": "PARABOLIC_NATIVE"}}; c.update(k); return c
def test_gates_fail_by_default():
    ok, g = ACT.evaluate(gate_cfg(None), "/nonexistent", os.path.join(ROOT, "specs", "native"))
    assert not ok and not g["starting_equity_set"] and not g["entry_parameters_owner_approved"] and not g["exit_rules_owner_approved"] and not g["robinhood_live_readonly_test_passed"]
def test_gates_pass_only_with_every_item(tmp_path):
    nd = tmp_path / "native"; nd.mkdir(); s = json.load(open(os.path.join(ROOT, "specs", "native", "PARABOLIC_NATIVE.json")))
    s["entry_confirmation"]["approved"] = True; s["exit_rules"] = [{"type": "trailing_pct", "pct": 10}]; json.dump(s, open(nd / "PARABOLIC_NATIVE.json", "w"))
    sd = str(tmp_path / "st"); cfg = gate_cfg(None, paper_start_equity=50_000)
    for f in ("robinhood_live_readonly.json", "google_drive_integration.json", "emergency_stop_drill.json"): ACT.record_acceptance(sd, f, {})
    assert not ACT.evaluate(cfg, sd, str(nd))[0]                                            # still missing owner sign-off
    ACT.record_acceptance(sd, "OWNER_ACTIVATION_SIGNOFF.json", {}); assert ACT.evaluate(cfg, sd, str(nd))[0]
    open(os.path.join(sd, "EMERGENCY_STOP"), "w").write("x"); assert not ACT.evaluate(cfg, sd, str(nd))[0]
def test_observe_only_never_fills(tmp_path):
    from test_phase2 import make, good_item, _complete_specs, snap
    sd = _complete_specs(tmp_path); s = snap(); s.bars[-1].h = 99.5; o, br = make(tmp_path, s, sd); o.observe_only = True
    o.ingest(good_item(), NOW); d = json.loads(open(tmp_path / "dec.jsonl").readlines()[-1])
    assert d["outcome"] == "OBSERVE_ONLY" and br.s["stocks"] == []
def test_installer_does_not_register_task_and_registration_is_disabled():
    inst = open(os.path.join(ROOT, "deploy", "windows", "install.ps1")).read(); reg = open(os.path.join(ROOT, "deploy", "windows", "register_task.ps1")).read()
    assert "schtasks /Create" not in inst and "/DISABLE" in reg

# ---------------- emergency-stop drill (real service entry point, subprocess) -------------------------------------------------
def test_emergency_stop_drill_records_acceptance(tmp_path):
    sd = tmp_path / "st"; r = subprocess.run([sys.executable, "scripts/acceptance.py", "estop", "--state", str(sd)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr and "PASS estop" in r.stdout
    assert json.load(open(sd / "acceptance" / "emergency_stop_drill.json"))["exit_code"] == 3 and not os.path.exists(sd / "EMERGENCY_STOP")

# ---------------- Drive outbox publisher (fake Drive service) ---------------------------------------------------------------------
class FakeFiles:
    def __init__(self, corrupt=False): self.store, self.n, self.corrupt = {}, 0, corrupt
    def files(self): return self
    def create(self, body, media_body, fields):
        self.n += 1; fid = f"id{self.n}"; data = media_body; self.store[fid] = (body, data)
        md5 = hashlib.md5(data, usedforsecurity=False).hexdigest()
        return type("X", (), {"execute": lambda s: {"id": fid, "md5Checksum": md5, "size": str(len(data))}})()
    def get_media(self, fileId):
        d = self.store[fileId][1] + (b"!" if self.corrupt else b""); return type("X", (), {"execute": lambda s: d})()
def test_outbox_publish_readback_and_restart_dedup(tmp_path):
    ob = tmp_path / "outbox"; ob.mkdir(); (ob / "PAPER_JOURNAL_2026-12-01.json").write_text("{}"); (ob / "RISK_REPORT_2026-12-01.json").write_text("{}")
    fs = FakeFiles(); p = OutboxPublisher(fs, str(ob), str(tmp_path / "pub.json"))
    out = p._publish_all(lambda b, m: b); assert len(out) == 2
    assert fs.store["id1"][0]["parents"] == [folder_for("PAPER_JOURNAL_x")] and folder_for("RISK_REPORT_x") == "1_LuRacmuH-frbZLTO0LQs-973Qub4zm9"
    assert OutboxPublisher(fs, str(ob), str(tmp_path / "pub.json"))._publish_all(lambda b, m: b) == []           # restart: nothing re-published
    (ob / "RISK_REPORT_2026-12-01.json").write_text('{"changed": 1}')
    assert len(OutboxPublisher(fs, str(ob), str(tmp_path / "pub.json"))._publish_all(lambda b, m: b)) == 1
def test_outbox_readback_mismatch_not_marked_published(tmp_path):
    ob = tmp_path / "outbox"; ob.mkdir(); (ob / "ALERTS_x.json").write_text("{}")
    p = OutboxPublisher(FakeFiles(corrupt=True), str(ob), str(tmp_path / "pub.json"))
    with pytest.raises(PublishError): p._publish_all(lambda b, m: b)
    assert not os.path.exists(tmp_path / "pub.json")
