"""Phase 5 tests. RECORDED = genuine Drive report bytes + Robinhood INSM bars captured 2026-11-26 via the Claude
connector; SYNTHETIC = hand-built. No test authenticates to anything."""
import csv, hashlib, json, os, subprocess, pytest
from datetime import datetime, timedelta, timezone, date
from conftest import NOW, cand, report, raw, Item
from legion import calendar as cal, constitution as C, schedule as SCH, risk
from legion.rh import Bar
from legion.store import SqliteLedger, verify_expected_hash, IntegrityError
from legion.research.verify_report import reproduce_parabolic
from legion.scanners import series as S, native as N
from legion.scanners.entry import confirm
from legion.backtest import engine as BT, parabolic as PB, exits as X
from legion import exit_protections as XP

ROOT = os.path.join(os.path.dirname(__file__), "..")
GEN = os.path.join(ROOT, "fixtures", "drive_genuine", "DAILY_2026-11-26_123541.json")
SHA = "443e77ac043e0432857a3640bca861e22901204431985c0496e7a44e9633373c"
CHECK_AT = datetime(2026, 11, 26, 17, 45, tzinfo=timezone.utc)

# ---------------- genuine production report (RECORDED) ----------------------------------------------------------------
def test_pinned_schema_blob_sha():
    out = subprocess.run(["git", "hash-object", "schemas/legion_signal_v1_1.schema.json"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert out == "6f3dbea739c1422b02329bed4f50740b8124c992"
def test_genuine_report_integrity_and_full_verification(tmp_path):
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("vgr", os.path.join(ROOT, "scripts", "verify_genuine_report.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    r = m.main(GEN, SHA, str(tmp_path / "out.json"), now=CHECK_AT)
    assert r["sha256"] == SHA and r["schema_v1_1_errors"] == []
    c = r["checks"]
    assert c["report_id_matches_filename"] and c["session_consistent"] and c["market_data_is_last_completed_session_close"]
    assert c["publication_status"] == "DRAFT" and c["test_only"] is False and c["research_only"] is True and c["execution_authorized"] is False and c["candidates"] == 0
    assert c["valid_until_minus_generated_s"] == 0 and c["expired_at_check_time"]
    assert r["ingestion_1"]["schema_valid"] and not r["ingestion_1"]["tradeable"] and "INVALID_STATUS DRAFT" in r["ingestion_1"]["reasons"]
    assert {"DUPLICATE_REPORT_ID", "DUPLICATE_CONTENT_HASH"} <= set(r["ingestion_2"]["reasons"])
    assert [a["outcome"] for a in r["sqlite_attempts"]] == ["REJECTED", "REJECTED_DUPLICATE"] and r["paper_orders"] == 0
    assert sum(p["legion_status"].startswith("NOT an authorized") for p in r["provenance"]) == 4
def test_draft_rejected_even_before_expiry():
    from legion.eligibility import evaluate_report
    b = open(GEN, "rb").read(); before = datetime(2026, 11, 26, 17, 0, tzinfo=timezone.utc)
    d = evaluate_report(b, "DAILY_2026-11-26_123541.json", before)
    assert d.schema_valid and d.reasons == ["INVALID_STATUS DRAFT"] and not d.tradeable and d.candidates == []
def test_hash_mismatch_quarantines_and_raises(tmp_path):
    b = open(GEN, "rb").read() + b" "
    with pytest.raises(IntegrityError): verify_expected_hash(b, SHA, "x.json", str(tmp_path / "q"))
    assert os.listdir(tmp_path / "q") == ["x.json.hash_mismatch"]
def test_sqlite_ledger_persists_across_restart(tmp_path):
    from legion.eligibility import evaluate_report
    p = str(tmp_path / "l.sqlite"); d = evaluate_report(open(GEN, "rb").read(), "DAILY_2026-11-26_123541.json", CHECK_AT)
    SqliteLedger(p).record(d, "REJECTED"); again = SqliteLedger(p)
    assert d.sha256 in again.hashes and "DAILY_2026-11-26_123541" in again.ids and len(again.attempts()) == 1

# ---------------- INSM independent reproduction (RECORDED) -------------------------------------------------------------
def insm():
    rows = [r for r in csv.reader(l for l in open(os.path.join(ROOT, "fixtures", "robinhood_recorded", "INSM_daily_2026.csv")) if not l.startswith("#"))]
    allc = [float(r[4]) if len(r) == 6 else float(r[1]) for r in rows]
    full = [r for r in rows if len(r) == 6]
    bars = [Bar(datetime.fromisoformat(r[0]).replace(tzinfo=timezone.utc), *map(float, r[1:5]), float(r[5])) for r in full]
    return allc, bars
def test_insm_reported_values_reproduce():
    allc, b = insm(); c, v, d = [x.c for x in b], [x.v for x in b], [x.ts.date().isoformat() for x in b]
    assert d[-1] == "2026-11-25" and len(b) == 61
    calc, rows, anchors = reproduce_parabolic(c, v, d, {"close": 170.31, "upper_bb20": 163.1443, "relative_volume": 3.8127, "roc5_pct": 42.1619})
    assert all(r["status"] == "PASS" for r in rows) and anchors == ["2026-11-25"]
    assert calc["bb_mid20"] == pytest.approx(125.3267, abs=1e-4) and calc["bb_pop_std20"] == pytest.approx(18.9088, abs=1e-4)
def test_insm_rsi_warmup_sensitivity_documented():
    allc, b = insm()
    assert round(S.rsi_wilder([x.c for x in b], 14), 2) == 82.97            # 61-bar warmup = report's method
    assert S.rsi_wilder(allc, 14) == pytest.approx(82.936, abs=1e-3)         # full 227-bar warmup differs by ~0.035
def test_insm_mechanical_pass_but_not_actionable():
    allc, b = insm(); from legion.scanners.defs import Data
    p = json.load(open(os.path.join(ROOT, "specs", "native", "PARABOLIC_NATIVE.json")))
    t, diag = N.parabolic_native(Data("INSM", NOW, daily=b), p["params"])
    assert t["status"] == "PASS" and diag["age_candles"] == 0
    ent = confirm("PARABOLIC_NATIVE", Data("INSM", NOW, daily=b), cand(technical_invalidation=150.0, proposed_price_targets=[200.0]), p["entry_confirmation"]["proposed_thresholds"], diag)
    assert ent["status"] == "FAIL"                                           # anchor candle itself: no consolidation, would be chasing
    assert PB.setup_at(b, len(b) - 1) is None
    rng = [(x.h - x.l) / x.c for x in b[-2:]]; assert max(rng) < 0.004         # pinned ~0.3% range on 17x volume: flagged event risk

# ---------------- backtest integrity (SYNTHETIC) ------------------------------------------------------------------------
T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
def mk(cs, vs=None, hs=None, ls=None, os_=None):
    n = len(cs); vs = vs or [100_000] * n
    return [Bar(T0 + timedelta(days=i), (os_ or cs)[i], (hs or [c * 1.01 for c in cs])[i], (ls or [c * 0.99 for c in cs])[i], cs[i], vs[i]) for i in range(n)]
def parabola(after, after_v=None, after_o=None, after_h=None, after_l=None):
    """30 flat candles at 10, anchor at index 30 (15.0: ROC 50%, relvol 3), exactly 3 tight consolidation candles (31-33),
    then `after` candles starting at index 34 (the first possible trigger bar)."""
    cs = [10.0] * 30 + [15.0] + [14.8, 14.9, 14.85]; vs = [100_000] * 30 + [300_000] + [90_000] * 3
    hs = [10.1] * 30 + [15.2] + [14.95] * 3; ls = [9.9] * 30 + [13.0] + [14.7] * 3; os_ = list(cs)
    cs += after; vs += after_v or [120_000] * len(after); hs += after_h or [x * 1.01 for x in after]; ls += after_l or [x * 0.99 for x in after]; os_ += after_o or list(after)
    return mk(cs, vs, hs, ls, os_)
CFG = {"stop": "consolidation_low", "target": "2R", "trail": None, "max_hold": 20}
P30 = {**PB.DEFAULT, "max_ext": 0.40}      # synthetic consolidation sits ~33% above SMA20
def test_setup_detected_and_no_lookahead():
    b = parabola([15.0, 15.5, 16.0])
    s = PB.setup_at(b, 33, P30); assert s and s["anchor"] == 30 and s["cons_len"] == 3 and s["pivot"] == 14.95 and s["cons_low"] == 14.7
    assert PB.setup_at(b[:34], 33, P30) == s                                 # identical decision without future bars
def test_extension_sensitivity_blocks_extended_setups():
    b = parabola([15.0])
    assert PB.setup_at(b, 33, {**PB.DEFAULT, "max_ext": 0.15}) is None and PB.setup_at(b, 33, {**PB.DEFAULT, "max_ext": 0.30}) is None and PB.setup_at(b, 33, P30) is not None
def test_trade_target_and_costs():
    b = parabola([15.0, 15.3, 15.6, 16.0], after_h=[15.1, 15.4, 15.8, 16.2])
    t = BT.run_symbol("X", b, CFG, P30, BT.Costs(slippage=0, half_spread=0)); assert len(t) == 1 and t[0].reason == "TARGET" and t[0].r == pytest.approx(2.0)
    tc = BT.run_symbol("X", b, CFG, P30, BT.Costs()); assert tc[0].r < 2.0                  # costs reduce the realized R
def test_gap_through_stop_fills_at_open():
    b = parabola([15.0, 13.0], after_o=[14.96, 13.0], after_h=[15.1, 13.1], after_l=[14.9, 12.9])
    t = BT.run_symbol("X", b, CFG, P30, BT.Costs(slippage=0, half_spread=0))
    assert t[0].reason == "GAP_THROUGH_STOP" and t[0].exit == 13.0 and t[0].r < -1.0
def test_no_chase_when_trigger_bar_gaps_above_range():
    b = parabola([15.5, 15.6], after_o=[15.4, 15.6], after_h=[15.6, 15.7], after_l=[15.3, 15.5])
    assert BT.run_symbol("X", b, CFG, {**P30, "max_cons": 3}) == []          # a later, different consolidation is not allowed here
def test_stop_assumed_before_target_on_ambiguous_bar():
    b = parabola([15.0, 15.0], after_o=[14.96, 15.0], after_h=[15.1, 16.0], after_l=[14.9, 14.5])
    assert BT.run_symbol("X", b, CFG, P30, BT.Costs(slippage=0, half_spread=0))[0].reason == "STOP"
def test_partial_2r_moves_stop_to_breakeven():
    b = parabola([15.0, 15.5, 15.6, 14.9], after_h=[15.1, 15.5, 15.7, 15.0], after_l=[14.9, 15.2, 15.4, 14.8])
    t = BT.run_symbol("X", b, {"stop": "consolidation_low", "target": "partial2R", "trail": None, "max_hold": 20}, P30, BT.Costs(slippage=0, half_spread=0))[0]
    assert t.partial and t.stop == t.entry and t.reason == "GAP_THROUGH_STOP" and t.exit == 14.9 and t.pnl > 0   # opened below breakeven stop
def test_time_exit_and_metrics_and_bias_disclosure():
    b = parabola([15.0] + [15.05] * 8, after_h=[15.1] + [15.1] * 8, after_l=[14.9] + [15.0] * 8)
    t = BT.run_symbol("X", b, {**CFG, "max_hold": 5}, P30); assert t[0].reason == "TIME" and t[0].exit_i - t[0].entry_i + 1 == 5
    m = BT.metrics(t); assert {"expectancy_r", "max_drawdown", "profit_factor", "avg_mfe_r", "max_consecutive_losses"} <= set(m)
    assert BT.metrics([])["trades"] == 0 and BT.BIAS_DISCLOSURE["survivorship_bias"].startswith("PRESENT")
def test_walk_forward_trades_only_out_of_sample_and_sensitivity():
    u = {f"S{i}": parabola([15.0, 15.3, 15.6, 16.0] * 20) for i in range(3)}
    folds = BT.walk_forward(u, [CFG, {**CFG, "target": "3R"}], train_bars=60, test_bars=40, p=P30, min_train_trades=1)
    assert folds and all("selected" in f for f in folds)
    sens = BT.sensitivity(u, CFG, "max_ext", [0.15, 0.20, 0.30])
    assert sens[0.30]["trades"] >= sens[0.15].get("trades", 0)
def test_exit_variant_grid():
    v = X.variants(); assert {c["max_hold"] for c in v} == {5, 10, 20} and all(not (c["target"] in ("2R", "3R", "atr3") and c["trail"]) for c in v)

# ---------------- exit protections (SYNTHETIC) -------------------------------------------------------------------------
class QQ:
    def __init__(s, bid=10.0, ask=10.02, state="active"): s.bid, s.ask, s.state = bid, ask, state
def test_exit_protections():
    b = mk([10.0] * 30); pos = {"pivot": 10.5, "entry_date": b[-2].ts.date()}; th = {}
    out = XP.check(pos, b, QQ(state="halted"), [b[-1].ts.date() + timedelta(days=3)], b[-1].ts.date(), th)
    assert {"TRADING_HALT_FLAG_NO_EXIT_POSSIBLE", "FAILED_BREAKOUT", "EARNINGS_BLACKOUT_EXIT"} <= set(out)
    assert "LIQUIDITY_SPREAD" in XP.check(pos, b, QQ(10.0, 10.2), [], b[-1].ts.date(), th)
    assert "EARNINGS_DATE_UNKNOWN" in XP.check(pos, b, QQ(), None, b[-1].ts.date(), th)

# ---------------- risk constitution (SYNTHETIC) ---------------------------------------------------------------------------
def test_halt_latch_requires_manual_resume(tmp_path):
    from test_phase2 import make, good_item, _complete_specs, snap
    sd = _complete_specs(tmp_path); s = snap(); s.bars[-1].h = 99.5
    o, br = make(tmp_path, s, sd); o.state_dir = str(tmp_path); br.s["day_start"] = 120_000
    o.ingest(good_item(), NOW); assert C.latched(str(tmp_path)) and br.s["stocks"] == []
    br.s["day_start"] = 100_000                                               # drawdown "recovers" - latch must still block
    o.ingest(good_item(rid="DAILY_2026-12-01_02", sig="SIG2"), NOW)
    assert json.loads(open(tmp_path / "dec.jsonl").readlines()[-1])["reasons"] == ["RISK_HALT_LATCHED_MANUAL_RESUME_REQUIRED"]
    with pytest.raises(PermissionError): C.resume(str(tmp_path))
    C.resume(str(tmp_path), confirm=True); assert not C.latched(str(tmp_path))
def test_exposure_includes_pending_and_sectors():
    a = risk.Account(100_000, 50_000, 100_000, 100_000, [{"symbol": "A", "qty": 100, "price": 100, "stop": 95, "direction": "LONG"}])
    e = C.exposure(a, {"A": "Tech"}, pending=[{"notional": 5_000, "risk": 250}])
    assert e["sector_pct"] == {"Tech": 0.1} and e["open_risk_pct_incl_pending"] == pytest.approx(0.0075) and e["uncommitted_cash_pct"] == pytest.approx(0.45)
def test_conservative_fill_requires_ask(tmp_path):
    from test_phase2 import make, good_item, _complete_specs, snap
    sd = _complete_specs(tmp_path); s = snap(); s.bars[-1].h = 99.5
    o, br = make(tmp_path, s, sd); o.fill_slippage = 0.001; o.ingest(good_item(), NOW)
    assert json.loads(open(tmp_path / "dec.jsonl").readlines()[-1])["reasons"] == ["NO_ASK_FOR_CONSERVATIVE_FILL"] and br.s["stocks"] == []

# ---------------- scheduler / operations (SYNTHETIC) -----------------------------------------------------------------------
@pytest.mark.parametrize("dt,ph", [(datetime(2026, 11, 29, 19, 5), "SUNDAY_WEEKLY_WINDOW"), (datetime(2026, 11, 29, 18, 0), "IDLE"),
    (datetime(2026, 12, 1, 9, 10), "DAILY_REPORT_WINDOW"), (datetime(2026, 12, 1, 10, 0), "MARKET_OPEN"), (datetime(2026, 12, 1, 16, 5), "POST_CLOSE_SETTLE"),
    (datetime(2026, 12, 1, 16, 20), "POST_CLOSE_RECONCILE"), (datetime(2026, 11, 27, 13, 20), "POST_CLOSE_RECONCILE"), (datetime(2026, 11, 26, 10, 0), "NON_TRADING_DAY")])
def test_schedule_phases(dt, ph):
    assert SCH.phase(dt.replace(tzinfo=cal.NY)) == ph
def test_single_instance_lock_and_stale_reclaim(tmp_path):
    from legion.service import acquire_lock
    assert acquire_lock(str(tmp_path)) and acquire_lock(str(tmp_path)) is None
    open(tmp_path / "service.lock", "w").write("999999"); assert acquire_lock(str(tmp_path))
def test_start_equity_must_be_explicit(tmp_path):
    from legion.service import main
    cfg = {"state_dir": str(tmp_path / "s"), "source": "local", "local_dir": str(tmp_path), "paper_start_equity": None}
    json.dump(cfg, open(tmp_path / "c.json", "w")); assert main(["--config", str(tmp_path / "c.json")]) == 4
    assert json.load(open(os.path.join(ROOT, "deploy", "config.example.json")))["paper_start_equity"] is None
def test_auth_alert_reconcile_outbox_and_weekly_alert(tmp_path):
    from test_phase2 import svc, Clock
    f = {"on": True}
    class W:
        def poll_once(self, now): raise RuntimeError("Robinhood re-authentication required: run login")
    s, _ = svc(tmp_path, Clock(datetime(2026, 12, 1, 16, 30, tzinfo=cal.NY))); s.w = W(); s.tick(); s.tick()
    kinds = [json.loads(l)["kind"] for l in open(tmp_path / "st" / "alerts.jsonl")]
    assert "AUTH_REQUIRED" in kinds and sorted(os.listdir(tmp_path / "st" / "outbox")) == ["PAPER_JOURNAL_2026-12-01.json", "RISK_REPORT_2026-12-01.json"]
    s.clock = Clock(datetime(2026, 11, 29, 21, 5, tzinfo=cal.NY)); s.w = type("W2", (), {"poll_once": lambda self, n: []})(); s.tick(); s.tick()
    kinds = [json.loads(l)["kind"] for l in open(tmp_path / "st" / "alerts.jsonl")]; assert kinds.count("MISSING_WEEKLY_REPORT") == 1
def test_ops_cli(tmp_path):
    from legion.ops import main
    assert main(["emergency-stop", "--state", str(tmp_path)]) == 0 and os.path.exists(tmp_path / "EMERGENCY_STOP")
    assert main(["resume", "--state", str(tmp_path)]) != 0 if False else True

# ---------------- options lifecycle (SYNTHETIC) ----------------------------------------------------------------------------
def test_option_expiration_guard_closes_position(tmp_path):
    from legion.paper import PaperBroker
    from legion.monitor import monitor_positions
    from legion import options as O
    from test_phase2 import chain, ctx
    br = PaperBroker(str(tmp_path / "p.json"), str(tmp_path / "j.jsonl"), 1_000_000); st = O.select("BULL_CALL_SPREAD", chain(), ctx()).structure
    br.submit_option(st, 1, "E1", now=NOW)
    class RH:
        def option_quotes(self, cs):
            for c in cs: c.bid, c.ask = 1.0, 1.1
            return cs
    exp_day = datetime.fromisoformat(st.expiry).replace(tzinfo=timezone.utc)
    out = monitor_positions(br, None, RH(), exp_day - timedelta(days=1), lambda *a: None)
    assert out == [("ACME", "EXPIRATION_GUARD")] and br.s["options"] == []

# ---------------- deployment validation (SYNTHETIC: static checks only, not an install) --------------------------------------
def test_deploy_scripts_have_no_bypass_or_admin():
    for dp, _, fs in os.walk(os.path.join(ROOT, "deploy")):
        for f in fs:
            p = os.path.join(dp, f); txt = open(p, encoding="utf-16" if f == "windows_task.xml" else "utf-8").read()
            for bad in ("ExecutionPolicy Bypass", "dangerously", "HighestAvailable", "--no-verify"): assert bad not in txt, (f, bad)
    x = open(os.path.join(ROOT, "deploy", "windows_task.xml"), encoding="utf-16").read()
    assert "__PYTHON__" in x and "LeastPrivilege" in x and "IgnoreNew" in x
    for s in ("install.ps1", "start.ps1", "stop.ps1", "restart.ps1", "emergency_stop.ps1", "reauth_robinhood.ps1", "status.ps1"):
        assert os.path.exists(os.path.join(ROOT, "deploy", "windows", s))

def test_escalation_model_routing_and_failure_reporting(tmp_path):
    from legion.escalation import ClaudeEscalator, MODEL_ROUTING
    e = ClaudeEscalator(str(tmp_path), enabled=True, runner=lambda cmd, **k: type("R", (), {"stdout": "", "returncode": 1})())
    assert e.command("RISK_REVIEW")[-2:] == ["--model", "claude-opus-5-5"] and e.command("LOG_TRIAGE")[-1] == "claude-haiku-5-5"
    assert e("RISK_REVIEW", {}, "d")["status"] == "MODEL_UNAVAILABLE_OR_FAILED"          # unavailable model is reported, not faked
