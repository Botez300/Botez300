"""Phase 4 tests. Labels: SYNTHETIC (hand-built), RECORDED (replayed real responses captured 2026-11-26 via the Claude
connector session), LIVE (only with LEGION_LIVE_RH=1 on an authenticated host; skipped otherwise). Nothing here
authenticates to Robinhood or Google, and a mocked response is never reported as authenticated connectivity."""
import copy, hashlib, json, os, pytest
from datetime import datetime, timedelta, timezone, date
from conftest import NOW, REC, report, cand, raw, Item, ts
from legion import evidence as EV, eligibility as E, strategies as ST
from legion.config import SystemParams
from legion.rh import RobinhoodClient, RecordedTransport, ResilientTransport, McpHttpTransport, ToolBlocked, ConnectionFailure, Bar
from legion.research import sec, etf
from legion.research.hub import ResearchHub
from legion.scanners import native as N, defs as D
from legion.scanners.tri import PASS, FAIL, UNV
from legion.rh_auth import KeyringTokenStorage, InsecureCredentialStore
from test_phase3 import bars, P, kid, cs_data, CSP, pdata, mv_data, wdata, mf, MFP

ROOT = os.path.join(os.path.dirname(__file__), "..")
NSPEC = {k[:-5]: json.load(open(os.path.join(ROOT, "specs", "native", k))) for k in os.listdir(os.path.join(ROOT, "specs", "native"))}
NOWS = NOW.isoformat()

# ---------------- provenance / evidence (SYNTHETIC) ------------------------------------------------------------------
def ev(**k):
    d = dict(criterion="C", source="SEC_EDGAR_VIA_ROBINHOOD", observed_at=(NOW - timedelta(hours=1)).isoformat(), value=1.0, threshold=0.5, methodology="m"); d.update(k)
    return EV.Evidence(**d)
@pytest.mark.parametrize("kw,st,why", [({}, "VERIFIED", "ok"), ({"source": "RANDOM_BLOG"}, "UNVERIFIED", "not authorized"),
    ({"source": "ALPHA_VANTAGE"}, "UNVERIFIED", "not authorized"), ({"source": "CHATGPT_LEGION_REPORT"}, "UNVERIFIED", "independent reproduction"),
    ({"source": "TRADINGVIEW_PINE"}, "UNVERIFIED", "not mapped"), ({"methodology": ""}, "UNVERIFIED", "missing methodology"),
    ({"value": None}, "UNVERIFIED", "missing value"), ({"observed_at": (NOW + timedelta(minutes=5)).isoformat()}, "UNVERIFIED", "future"),
    ({"observed_at": (NOW - timedelta(days=3)).isoformat()}, "UNVERIFIED", "stale")])
def test_evidence_check(kw, st, why):
    s, r = EV.check(ev(**kw), NOW, 86400); assert s == st and why in r
def test_unauthorized_provider_raises():
    with pytest.raises(EV.UnauthorizedSource): EV.require_authorized("SOME_SCRAPER")
    with pytest.raises(EV.UnauthorizedSource): EV.require_authorized("BIGDATA_COM")
def test_conflicting_sources_unverified_and_agreeing_verified():
    a, b = ev(source="SEC_EDGAR_VIA_ROBINHOOD", value=2.02), ev(source="SEC_EDGAR_DIRECT", value=2.05)
    assert EV.reconcile([a, b], NOW, None)[1] == "UNVERIFIED" and "CONFLICT" in EV.reconcile([a, b], NOW, None)[2]
    assert EV.reconcile([a, ev(source="SEC_EDGAR_DIRECT", value=2.02)], NOW, None)[:2] == (2.02, "VERIFIED")
    assert EV.reconcile([a, b], NOW, None, rel_tol=0.02)[1] == "VERIFIED"
    assert EV.reconcile([ev(source="CHATGPT_LEGION_REPORT")], NOW, None)[1] == "UNVERIFIED"     # claims never self-verify

def ecrit(**k):
    d = {"criterion_id": "C1", "status": "PASS", "source": "ROBINHOOD_MCP", "observed_at": (NOW - timedelta(minutes=10)).isoformat(),
         "value": 1.8, "threshold": 1.4, "methodology": "volume / 50d avg"}; d.update(k); return d
def test_v10_pass_labels_are_unsupported():
    a = EV.audit_report_candidate(cand(), NOW); assert a == [{"criterion_id": "C1", "claimed": "PASS", "status": "UNVERIFIED", "reason": "UNSUPPORTED_LABEL"}]
def test_v11_schema_requires_evidence_fields():
    r = report([cand(individual_criteria_results=[ecrit()])], schema_version="1.1")
    assert E.evaluate_report(raw(r), "DAILY_2026-12-01_01.json", NOW).schema_valid
    bad = ecrit(); del bad["methodology"]
    assert not E.evaluate_report(raw(report([cand(individual_criteria_results=[bad])], schema_version="1.1")), "DAILY_2026-12-01_01.json", NOW).schema_valid
    assert EV.audit_report_candidate(cand(individual_criteria_results=[ecrit()]), NOW)[0]["status"] == "VERIFIED"
    assert EV.audit_report_candidate(cand(individual_criteria_results=[ecrit(source="CHATGPT_LEGION_REPORT")]), NOW)[0]["status"] == "UNVERIFIED"
def test_production_orchestrator_rejects_unsupported_labels(tmp_path):
    from test_phase2 import make
    o, br = make(tmp_path); o.require_evidence = True
    o.ingest(Item("DAILY_2026-12-01_01.json", raw(report([cand()]))), NOW)
    d = json.loads(open(tmp_path / "dec.jsonl").readlines()[-1]); assert d["reasons"] == ["REPORT_CRITERIA_EVIDENCE_UNVERIFIED"] and br.s["stocks"] == []

# ---------------- EPS accounting consistency (RECORDED + SYNTHETIC) ------------------------------------------------------
def fct(c, v, s=None, e="2026-06-27", fid="F1", axes=()):
    d = {"concept": c, "value": str(v), "end_date": e, "axises": list(axes), "filing_id": fid}
    if s: d["start_date"] = s
    return d
def test_recorded_sec_quarterly_gaap_diluted_eps():
    facts = json.load(open(os.path.join(REC, "get_sec_filing_facts.AAPL_10Q_2026-07-31.trimmed.json")))["data"]["facts"]
    rows, conf = sec.quarterly_eps({"f": facts}, {"f": "2026-07-31"})
    assert [(r["end"], r["eps"]) for r in rows] == [("2026-06-27", 2.02), ("2025-06-28", 1.57)] and conf == []        # 9-month YTD (6.88) excluded
def test_first_filed_value_wins_and_restatement_is_recorded():
    f1 = [fct("EarningsPerShareDiluted", 1.00, "2026-03-29", "2026-06-27", "A")]; f2 = [fct("EarningsPerShareDiluted", 0.90, "2026-03-29", "2026-06-27", "B")]
    rows, conf = sec.quarterly_eps({"A": f1, "B": f2}, {"A": "2026-07-31", "B": "2027-07-30"})
    assert rows[0]["eps"] == 1.00 and conf == [("2026-06-27", 1.00, 0.90, "B")]
def test_q4_slot_unverified_and_contiguity():
    fy = [fct("EarningsPerShareDiluted", 6.0, "2025-09-28", "2026-09-26", "K")]
    q3 = [fct("EarningsPerShareDiluted", 2.0, "2026-03-29", "2026-06-27", "Q")]
    rows, _ = sec.quarterly_eps({"K": fy, "Q": q3}, {"K": "2026-11-01", "Q": "2026-07-31"})
    assert rows[0]["eps"] is None and rows[0]["reason"] == "Q4_NOT_SEPARATELY_REPORTED" and rows[1]["eps"] == 2.0
    gap = [{"end": "2026-06-27"}, {"end": "2026-03-28"}, {"end": "2025-06-28"}]
    assert len(sec.contiguous(gap)) == 2
def test_segment_axes_excluded():
    c = sec.consolidated([fct("OperatingIncomeLoss", 5, "2026-03-29"), fct("OperatingIncomeLoss", 99, "2026-03-29", axes=["Seg: X"])])
    assert [r[2] for r in c["OperatingIncomeLoss"]] == [5.0]
def test_can_slim_native_rejects_mixed_basis():
    assert kid(N.can_slim_native(cs_data(eps_basis="ADJUSTED"), CSP()), "C")["status"] == UNV
    assert kid(N.can_slim_native(cs_data(eps_basis="GAAP_DILUTED"), CSP()), "C")["status"] == PASS

# ---------------- ROIC (SYNTHETIC) ----------------------------------------------------------------------------------------
PRE = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"
def roic_facts(oi=(90, 100, 30), tax=(18, 20, 6), pre=(90, 100, 30), eq=(500, 400), cash=(100, 100), debt=(200, 200)):
    """FY(2025-09-27) + 9M YTD(2026-06-27) + prior 9M YTD(2025-06-28); balance sheet at 2026-06-27 and 2025-06-28."""
    out = []
    for c, (ytd, fy, pytd) in (("OperatingIncomeLoss", oi), ("IncomeTaxExpenseBenefit", tax), (PRE, pre)):
        out += [fct(c, ytd, "2025-09-28", "2026-06-27"), fct(c, fy, "2024-09-29", "2025-09-27"), fct(c, pytd, "2024-09-29", "2025-06-28")]
    for c, (e1, e0) in (("StockholdersEquity", eq), ("CashAndCashEquivalentsAtCarryingValue", cash), ("LongTermDebtNoncurrent", debt)):
        out += [fct(c, e1, None, "2026-06-27"), fct(c, e0, None, "2025-06-28")]
    return sec.consolidated(out)
E1, E0 = date(2026, 6, 27), date(2025, 6, 28)
def test_ttm_flow_construction():
    assert sec.ttm_flow(roic_facts(), "OperatingIncomeLoss", E1) == (160.0, "YTD + FY(prior) - YTD(prior year)")
def test_native_roic_value_and_provenance():
    v, p = sec.native_roic(roic_facts(), E1, E0)
    # TTM OI 160, tax 32/pretax 160 = 20%, NOPAT 128, IC end 600 / begin 500 -> avg 550
    assert v == pytest.approx(128 / 550) and p["effective_tax_rate"] == pytest.approx(0.2) and p["definition"] == "LEGION_NATIVE_ROIC_V1" and p["source"] == sec.SOURCE
@pytest.mark.parametrize("kw,reason", [({"eq": (-600, -600)}, "NEGATIVE_OR_ZERO_INVESTED_CAPITAL"), ({"tax": (90, 100, 30)}, "UNUSUAL_TAX_RATE"),
    ({"pre": (-10, -5, -3)}, "UNUSUAL_TAX_RATE"), ({"cash": (None, None)}, "incomplete balance sheet")])
def test_native_roic_edge_cases(kw, reason):
    if kw.get("cash") == (None, None):
        c = roic_facts(); c.pop("CashAndCashEquivalentsAtCarryingValue")
    else: c = roic_facts(**kw)
    v, p = sec.native_roic(c, E1, E0); assert v is None and reason in p["reason"]
def test_native_roic_financials_excluded():
    assert sec.native_roic(roic_facts(), E1, E0, sector="Financial Services")[1]["reason"] == "FINANCIAL_INSTITUTION_EXCLUDED"
def test_magic_native_requires_native_sources():
    d = mf(); d.operating_income_source, d.roic_definition = "SEC_TTM_OPERATING_INCOME", "LEGION_NATIVE_ROIC_V1"
    assert N.magic_native(d, NSPEC["MAGIC_FORMULA_NATIVE"]["params"])[0]["status"] == PASS
    d.roic_definition = "ROE"; assert N.magic_native(d, NSPEC["MAGIC_FORMULA_NATIVE"]["params"])[0]["status"] == UNV

# ---------------- independent variants & same-candle groups (SYNTHETIC) ----------------------------------------------------
def test_specs_exact_and_native_are_separate():
    for k in D.STRATEGIES: assert json.load(open(os.path.join(ROOT, "specs", f"{k}.json")))["classification"] == "EXACT_PLATFORM"
    for k, s in NSPEC.items():
        assert s["classification"] == "LEGION_NATIVE" and s["entry_confirmation"]["approved"] is False and "never an exact" in s["label"]
    assert NSPEC["MINERVINI_NATIVE_PROPOSED"]["mechanical_semantics_approved"] is False
def test_parabolic_native_requires_same_candle():
    c = [10.0] * 36 + [15.0] * 4; v = [100_000] * 39 + [300_000]           # conditions met on DIFFERENT candles
    assert N.parabolic_native(pdata(c, v), NSPEC["PARABOLIC_NATIVE"]["params"])[0]["status"] == FAIL
    assert D.parabolic(pdata(c, v), P("PARABOLIC_MOMENTUM", window_mode="independent"))[0]["status"] == PASS   # exact-variant alt mode differs
    t, diag = N.parabolic_native(pdata([10.0] * 40 + [15.0], [100_000] * 40 + [300_000]), NSPEC["PARABOLIC_NATIVE"]["params"])
    assert t["status"] == PASS and t["id"] == "PARABOLIC_NATIVE"
def test_parabolic_native_anchor_outside_ten_candles():
    c = [10.0] * 30 + [15.0] + [15.0] * 10; v = [100_000] * 30 + [300_000] + [100_000] * 10
    assert N.parabolic_native(pdata(c, v), NSPEC["PARABOLIC_NATIVE"]["params"])[0]["status"] == FAIL
def test_weinstein_native_common_anchor_and_stage_evidence_required():
    st, v = [1] * 27 + [1, 2, 2], [100] * 28 + [50, 400]
    assert N.weinstein_native(wdata(st, v), NSPEC["WEINSTEIN_NATIVE"]["params"])["status"] == FAIL
    assert N.weinstein_native(wdata([1] * 29 + [2], [100] * 29 + [300]), NSPEC["WEINSTEIN_NATIVE"]["params"])["status"] == PASS
    assert N.weinstein_native(wdata(None, [100] * 29 + [300]), NSPEC["WEINSTEIN_NATIVE"]["params"])["status"] == UNV
def test_can_slim_native_m_uses_stock_and_l_i_still_block():
    d = cs_data(market_daily=None, daily=bars([20 + 0.1 * i for i in range(300)], vols=[1_000_000] * 300))
    d.weekly = bars([50.0] * 60, highs=[55.0] * 60, step=7); d.daily[-1] = Bar(d.daily[-1].ts, 50.0, 51, 49, 50.0, 1e6)
    t = N.can_slim_native(d, CSP()); assert kid(t, "M")["status"] == PASS
    d2 = copy.copy(d); d2.proprietary = {}; d2.analyst_buy_dates = None
    t2 = N.can_slim_native(d2, CSP()); assert kid(t2, "L")["status"] == UNV and kid(t2, "I")["status"] == UNV and t2["status"] == UNV
def test_minervini_native_proposal_blocked_by_rs():
    d = mv_data(); d.daily = bars([50 + 0.2 * i for i in range(300)], vols=[1e6 - 2000 * i for i in range(300)])
    t = N.minervini_native_proposed(d, NSPEC["MINERVINI_NATIVE_PROPOSED"]["params"])
    assert kid(t, "RS_RATING")["status"] == UNV and t["id"] == "MINERVINI_NATIVE_PROPOSED" and t["status"] != PASS
def test_turtle_native_s2_emergence_and_s1_skip_rule():
    c = [50.0] * 70 + [60.0]; d = D.Data("T", NOW, daily=bars(c, vols=[200_000] * 71), spread_pct=0.001)
    t = N.turtle_native(d, P("TURTLE")); assert kid(t, "S2_EMERGED")["status"] == PASS and t["sizing"]["N"] > 0
    c2 = [50.0] * 70 + [60.0, 61.0]; d2 = D.Data("T", NOW, daily=bars(c2, vols=[200_000] * 72), spread_pct=0.001)
    assert N.turtle_native(d2, P("TURTLE"))["status"] == FAIL                                 # already active, not emerging
    # prior S1 breakout that ran to a profit -> skip the next S1 signal
    c3 = [50.0] * 25 + [55.0, 58, 62, 66, 70] + [69.0] * 12 + [65.0] + [64.0] * 21 + [75.0]
    t3 = N.turtle_native(D.Data("T", NOW, daily=bars(c3, vols=[200_000] * len(c3)), spread_pct=0.001), P("TURTLE"))
    assert "prior_winner=True" in kid(t3, "S1_EMERGED_NOT_SKIPPED")["detail"] and kid(t3, "S1_EMERGED_NOT_SKIPPED")["status"] == FAIL

# ---------------- native gate + entry confirmation + simulated fills (SYNTHETIC) -------------------------------------------
class Q:
    def __init__(s, p, t, bid=None, ask=None): s.price, s.ts, s.bid, s.ask = p, t, bid, ask
def approved_native(tmp_path, nid, **thr):
    s = copy.deepcopy(NSPEC[nid]); s["entry_confirmation"]["approved"] = True; s["entry_confirmation"]["proposed_thresholds"].update(thr); s["data_gaps"] = []
    os.makedirs(tmp_path / "native", exist_ok=True); json.dump(s, open(tmp_path / "native" / f"{nid}.json", "w")); return str(tmp_path / "native")
def para_setup():
    c = [10.0] * 40 + [15.0, 14.6, 14.7, 14.65, 15.2]; v = [100_000] * 40 + [300_000, 90_000, 80_000, 85_000, 150_000]
    hi = [x + 0.3 for x in c]; lo = [x - 0.3 for x in c]; hi[40], lo[40] = 16.0, 10.0
    return D.Data("ACME", NOW, daily=bars(c, hi, lo, v))
def test_native_gate_blocks_until_entry_thresholds_approved():
    for nid in NSPEC:
        snap = ST.Snapshot("ACME", Q(15.2, NOW), [], [], {}, [], NOW, {"scanner_data": para_setup()})
        ok, _, bad = ST.verify_candidate(cand(originating_strategy="PARABOLIC_MOMENTUM"), snap, variant=nid)
        assert not ok and bad[0].startswith("STRATEGY_INCOMPLETE")
def test_parabolic_native_no_chase_and_consolidation_entry(tmp_path, monkeypatch):
    from legion.scanners import gate
    monkeypatch.setattr(gate, "NATIVE_SPEC_DIR", approved_native(tmp_path, "PARABOLIC_NATIVE", max_atr5_over_atr14=0.8, max_extension_vs_sma20_pct=60.0, max_stop_distance_pct=40.0, min_reward_risk=1.0))
    d = para_setup(); c = cand(originating_strategy="PARABOLIC_MOMENTUM", current_price=15.2, proposed_entry=15.2, entry_zone={"low": 15.0, "high": 15.4},
                              technical_invalidation=9.9, proposed_price_targets=[22.0])
    sp = SystemParams(min_avg_volume=1, min_dollar_volume=1)
    snap = ST.Snapshot("ACME", Q(15.2, NOW - timedelta(seconds=5), 15.19, 15.21), d.daily, d.daily, {}, [], NOW, {"scanner_data": d})
    ok, crit, bad = ST.verify_candidate(c, snap, sp=sp, variant="PARABOLIC_NATIVE"); assert ok, bad
    chase = para_setup(); chase.daily = chase.daily[:41]                                    # the qualifying candle itself = chasing
    snap2 = ST.Snapshot("ACME", Q(15.0, NOW - timedelta(seconds=5), 14.99, 15.01), chase.daily, chase.daily, {}, [], NOW, {"scanner_data": chase})
    ok, _, bad = ST.verify_candidate(cand(originating_strategy="PARABOLIC_MOMENTUM", current_price=15.0), snap2, sp=sp, variant="PARABOLIC_NATIVE")
    assert not ok and bad == ["ENTRY_CONFIRMATION_FAIL"]
    wide = ST.Snapshot("ACME", Q(15.2, NOW - timedelta(seconds=5), 15.1, 15.3), d.daily, d.daily, {}, [], NOW, {"scanner_data": d})
    ok, _, bad = ST.verify_candidate(c, wide, sp=sp, variant="PARABOLIC_NATIVE"); assert not ok and "EQUITY_SPREAD_LE_0.5PCT_FAIL" in bad
def test_simulated_stock_and_option_fills_through_native_route(tmp_path, monkeypatch):
    from legion.scanners import gate
    from test_phase2 import make, chain, ctx
    from legion import options as O, risk
    monkeypatch.setattr(gate, "NATIVE_SPEC_DIR", approved_native(tmp_path, "PARABOLIC_NATIVE", max_atr5_over_atr14=0.8, max_extension_vs_sma20_pct=60.0, max_stop_distance_pct=40.0, min_reward_risk=1.0))
    d = para_setup()
    class M:
        def snapshot(self, t, now): return ST.Snapshot("ACME", Q(15.2, NOW - timedelta(seconds=5), 15.19, 15.21), d.daily, d.daily, {}, [], NOW, {"scanner_data": d})
    o, br = make(tmp_path); o.m = M(); o.variants = {"PARABOLIC_MOMENTUM": "PARABOLIC_NATIVE"}; o.sp = SystemParams(min_avg_volume=1, min_dollar_volume=1)
    c = cand(originating_strategy="PARABOLIC_MOMENTUM", current_price=15.2, proposed_entry=15.2, entry_zone={"low": 15.0, "high": 15.4}, technical_invalidation=9.9, proposed_price_targets=[22.0])
    o.ingest(Item("DAILY_2026-12-01_01.json", raw(report([c]))), NOW)
    st = br.s["stocks"][0]; assert st["symbol"] == "ACME" and st["price"] == 15.2 and st["qty"] == 94          # risk: $500 / $5.30 stop
    st2 = O.select("BULL_CALL_SPREAD", chain(), ctx()).structure; big = __import__("legion.paper", fromlist=["x"]).PaperBroker(str(tmp_path / "o.json"), str(tmp_path / "oj.jsonl"), 1_000_000)
    big.submit_option(st2, risk.size_option(big.account(), st2).qty, "OPT", now=NOW)
    fill = json.loads(open(tmp_path / "oj.jsonl").readline()); assert fill["mode"] == "PAPER" and fill["type"] == "OPTION_OPEN" and fill["qty"] == 7

def test_failed_bullish_screen_is_not_a_bearish_entry():
    from legion import options as O
    from test_phase2 import chain, ctx
    assert O.select("LONG_PUT", chain(), ctx(direction="LONG")).structure is None
    assert O.select("BEAR_CALL_SPREAD", chain(), ctx(direction="SHORT", bearish_verified=False)).structure is None

# ---------------- credentials (SYNTHETIC backends) ------------------------------------------------------------------------
class SecureFake:                                          # name contains no 'fail'/'plaintext': stands in for WinVault/Keychain
    def __init__(self): self.d = {}
    def get_password(self, s, k): return self.d.get((s, k))
    def set_password(self, s, k, v): self.d[(s, k)] = v
    def delete_password(self, s, k): self.d.pop((s, k), None)
class FailKeyring(SecureFake): pass
class PlaintextKeyring(SecureFake): pass
def test_token_storage_refuses_insecure_backends():
    for b in (FailKeyring(), PlaintextKeyring()):
        with pytest.raises(InsecureCredentialStore): KeyringTokenStorage(backend=b)
def test_token_round_trip_only_in_credential_store(tmp_path):
    import asyncio
    from mcp.shared.auth import OAuthToken
    be = SecureFake(); st = KeyringTokenStorage(backend=be); cwd = os.getcwd(); os.chdir(tmp_path)
    try:
        asyncio.run(st.set_tokens(OAuthToken(access_token="AT-secret", token_type="Bearer", refresh_token="RT-secret", expires_in=3600)))
        t = asyncio.run(st.get_tokens()); assert t.refresh_token == "RT-secret" and st.has_tokens()
        assert os.listdir(tmp_path) == []                                                 # nothing written to disk
        st.clear(); assert not st.has_tokens()
    finally: os.chdir(cwd)
def test_no_secrets_in_repository_templates():
    for f in ("deploy/config.example.json", "deploy/env.example"):
        txt = open(os.path.join(ROOT, f)).read().lower()
        for bad in ("access_token", "refresh_token", "password=", "secret=", "bearer "): assert bad not in txt, (f, bad)

# ---------------- connection recovery (SYNTHETIC) --------------------------------------------------------------------------
def test_resilient_transport_recovers_and_gives_up():
    calls = {"n": 0}
    def flaky(t, a):
        calls["n"] += 1
        if calls["n"] < 3: raise TimeoutError("blip")
        return {"data": {"results": []}}
    rt = ResilientTransport(flaky, retries=3, sleep=lambda s: None); assert rt("get_equity_quotes", {})["data"] == {"results": []} and calls["n"] == 3
    with pytest.raises(ConnectionFailure): ResilientTransport(lambda t, a: (_ for _ in ()).throw(OSError("down")), retries=2, sleep=lambda s: None)("get_equity_quotes", {})
    seen = []
    with pytest.raises(ToolBlocked): ResilientTransport(lambda t, a: seen.append(t), sleep=lambda s: None)("place_equity_order", {})
    assert seen == []
def test_mcp_transport_blocks_before_network():
    t = McpHttpTransport(url="https://agent.robinhood.com/mcp/trading", auth=object())
    with pytest.raises(ToolBlocked): t("place_option_order", {})
    with pytest.raises(ToolBlocked): t("exercise_option", {})

@pytest.mark.skipif(os.environ.get("LEGION_LIVE_RH") != "1", reason="LIVE: requires authenticated Robinhood MCP on the host")
def test_live_authenticated_market_data_available():
    q = RobinhoodClient(ResilientTransport(McpHttpTransport())).quote("SPY"); assert q.price and q.ts

# ---------------- research hub, ETF holdings (RECORDED + SYNTHETIC) ---------------------------------------------------------
def test_research_hub_recorded_sec_and_provenance():
    d = ResearchHub(RobinhoodClient(RecordedTransport(REC)), now=datetime(2026, 11, 26, 20, tzinfo=timezone.utc)).build("AAPL")
    assert d.eps_basis == "GAAP_DILUTED" and d.eps[0]["eps"] == 2.02 and d.provenance["eps"]["source"] == "SEC_EDGAR_VIA_ROBINHOOD"
    assert len(d.eps) < 17                                       # recorded fixture is one filing: history insufficient -> CAN SLIM A stays UNVERIFIED
def test_research_hub_rejects_unauthorized_evidence_import():
    hub = ResearchHub(RobinhoodClient(RecordedTransport(REC)), now=NOW, evidence_imports={"AAPL": {D.P_WEINSTEIN: {"source": "SCRAPED_SITE", "values": [1, 2]}}})
    with pytest.raises(EV.UnauthorizedSource): hub.build("AAPL", with_sec=False)
ISH = '﻿iShares Russell 2000 ETF\nFund Holdings as of,"Nov 25, 2026"\nInception Date,"May 22, 2000"\n\xa0\nTicker,Name,Sector,Asset Class,Market Value,Weight (%)\n"AAA","A CO","Tech","Equity","1","0.1"\n"BBB","B CO","Health","Equity","1","0.1"\n"XTSLA","BLK CSH","Cash","Money Market","1","0.1"\n"-","CASH","Cash","Cash","1","0"\n'
def test_ishares_parser_point_in_time():
    h = etf.parse_ishares(ISH); assert h == {"as_of": "2026-11-25", "tickers": ["AAA", "BBB"], "rows": 4, "source": "ISHARES_OFFICIAL_HOLDINGS"}
    with pytest.raises(etf.HoldingsFormatError): etf.parse_ishares(ISH.replace("Fund Holdings as of", "Something"))
    with pytest.raises(etf.HoldingsFormatError): etf.parse_ishares("no,header\n1,2\n")

# ---------------- real-report ingestion (RECORDED: the two genuine Drive files) -------------------------------------------------
def test_genuine_drive_reports_ingested_zero_orders(tmp_path):
    from test_phase2 import make
    from legion.reporting import journal, risk_report
    o, br = make(tmp_path); o.require_evidence = True
    fx = os.path.join(ROOT, "fixtures", "03_Verified_Signals")
    for n, size in (("TEST_ONLY_DAILY_2026-11-26_01.json", 598), ("TEST_ONLY_WEEKLY_2026-11-26_01.json", 600)):
        b = open(os.path.join(fx, n), "rb").read(); assert len(b) == size
        d = o.ingest(Item(n, b), NOW); assert d.schema_valid and not d.tradeable and "TEST_ONLY" in d.reasons
    j = journal(str(tmp_path / "dec.jsonl"), str(tmp_path / "journal.jsonl")); assert j["summary"]["simulated_fills"] == 0 and j["summary"]["rejected"] == 2
    r = risk_report(br); assert r["equity"] == 100_000 and r["halt"] is None and r["positions"]["stocks"] == []

# ---------------- service graceful stop + persistent logging (SYNTHETIC) ---------------------------------------------------------
def test_graceful_stop_and_logging(tmp_path):
    from test_phase2 import svc, Clock
    from legion.service import setup_logging
    s, _ = svc(tmp_path, Clock(NOW)); open(tmp_path / "st" / "STOP_REQUEST", "w").write("x")
    assert s.run() == 0 and not os.path.exists(tmp_path / "st" / "STOP_REQUEST")
    lg = setup_logging(str(tmp_path / "st")); lg.info("hello"); [h.flush() for h in lg.handlers]
    assert "hello" in open(tmp_path / "st" / "logs" / "legion.log").read()
