from datetime import date, datetime, timezone

from src.config import pair_for_symbol
from src.options.screener import evaluate_contract, screen
from src.portfolio.portfolio import ShortPut, new_portfolio
from src.regime.classifier import Regime, RegimeResult
from src.risk.engine import Verdict, drawdowns, evaluate_entry, two_contract_validation

AS_OF = date(2026, 11, 16)


def _regimes(sym="SQQQ"):
    return {"NASDAQ100": RegimeResult("NASDAQ100", Regime.BEARISH, sym, AS_OF, 0.6),
            "SP500": RegimeResult("SP500", Regime.NEUTRAL, None, AS_OF, 0.0),
            "SEMIS": RegimeResult("SEMIS", Regime.NEUTRAL, None, AS_OF, 0.0)}


def test_eligible_contract(cfg, quote_factory):
    c = evaluate_contract(quote_factory(), AS_OF, _regimes(), cfg)
    assert c.eligible, c.rejections


def test_neutral_regime_rejects(cfg, quote_factory):
    c = evaluate_contract(quote_factory(symbol="UPRO", strike=120), AS_OF, _regimes(), cfg)
    assert not c.eligible and any("regime" in r for r in c.rejections)


def test_wrong_side_rejected(cfg, quote_factory):
    c = evaluate_contract(quote_factory(symbol="TQQQ", strike=45), AS_OF, _regimes("SQQQ"), cfg)
    assert any("selects SQQQ" in r for r in c.rejections)


def test_mandatory_gates(cfg, quote_factory):
    assert any("DTE" in r for r in evaluate_contract(quote_factory(exp=date(2026, 11, 27)), AS_OF, _regimes(), cfg).rejections)
    assert any("delta" in r for r in evaluate_contract(quote_factory(delta=-0.30), AS_OF, _regimes(), cfg).rejections)
    assert any("bid" in r for r in evaluate_contract(quote_factory(bid=0.0), AS_OF, _regimes(), cfg).rejections)
    assert any("Greeks" in r for r in evaluate_contract(quote_factory(delta=None), AS_OF, _regimes(), cfg).rejections)


def test_semis_band_narrower(cfg, quote_factory):
    regs = {"SEMIS": RegimeResult("SEMIS", Regime.BULLISH, "SOXL", AS_OF, 0.5)}
    c = evaluate_contract(quote_factory(symbol="SOXL", strike=40, delta=-0.18), AS_OF, regs, cfg)
    assert any("delta" in r for r in c.rejections)


def test_preferences_are_soft(cfg, quote_factory):
    c = evaluate_contract(quote_factory(oi=200, bid=0.80, ask=0.95), AS_OF, _regimes(), cfg)
    assert c.eligible and c.preference_flags


def test_not_highest_premium_auto(cfg, quote_factory):
    qs = [quote_factory(strike=36, bid=0.95, ask=1.30, delta=-0.19, oi=60, iid="a"),
          quote_factory(strike=34, bid=0.60, ask=0.63, delta=-0.12, oi=5000, iid="b")]
    elig, _ = screen(qs, AS_OF, _regimes(), cfg)
    assert elig[0].quote.instrument_id == "b"


def test_risk_pass_and_collateral_veto(cfg):
    pB = new_portfolio("B", cfg["portfolios"]["B"])
    d = evaluate_entry(pB, "SQQQ", 35, 100, AS_OF, cfg, regime_confirmed=True, quote_fresh_for_fill=True)
    assert d.verdict is Verdict.PASS
    pA = new_portfolio("A", cfg["portfolios"]["A"])
    d = evaluate_entry(pA, "SQQQ", 35, 100, AS_OF, cfg, regime_confirmed=True, quote_fresh_for_fill=True)
    assert d.verdict is Verdict.VETO and any("collateral" in v for v in d.vetoes)


def test_stale_quote_conditional(cfg):
    pB = new_portfolio("B", cfg["portfolios"]["B"])
    d = evaluate_entry(pB, "SQQQ", 35, 100, AS_OF, cfg, regime_confirmed=True, quote_fresh_for_fill=False)
    assert d.verdict is Verdict.CONDITIONAL


def _with_put(p, sym="SQQQ", strike=30.0):
    p.puts.append(ShortPut("x", sym, "2026-12-18", strike, 1, 100, 0.5, "2026-11-10", 0.03, "o"))
    return p


def test_contract_limit_and_conflicts(cfg):
    p = _with_put(new_portfolio("B", cfg["portfolios"]["B"]))
    d = evaluate_entry(p, "SPXU", 20, 100, AS_OF, cfg, regime_confirmed=True, quote_fresh_for_fill=True)
    assert d.verdict is Verdict.VETO and any("contract limit" in v for v in d.vetoes)
    p.validated_two_contracts = True
    d = evaluate_entry(p, "TQQQ", 15, 100, AS_OF, cfg, regime_confirmed=True, quote_fresh_for_fill=True)
    assert any("opposing ETF" in v for v in d.vetoes)
    d = evaluate_entry(p, "SQQQ", 15, 100, AS_OF, cfg, regime_confirmed=True, quote_fresh_for_fill=True)
    assert any("conflicting" in v for v in d.vetoes)


def test_two_contracts_use_20pct_cap(cfg):
    p = _with_put(new_portfolio("B", cfg["portfolios"]["B"]), "SOXS", 15.0)
    p.validated_two_contracts = True
    d = evaluate_entry(p, "SPXU", 25, 100, AS_OF, cfg, regime_confirmed=True, quote_fresh_for_fill=True)
    assert any("20% of risk capital" in v for v in d.vetoes)  # $2,500 > $2,000


def test_unrealized_gains_not_capacity(cfg):
    p = _with_put(new_portfolio("B", cfg["portfolios"]["B"]))
    p.cash += 50.0  # premium received
    p.puts[0].last_mark = 0.05  # large unrealized gain
    assert p.risk_capital() <= p.equity() - p.unrealized_option_pnl() + 1e-9


def test_drawdown_breakers(cfg):
    hist = [{"date": "2026-11-10", "equity": 10000, "net_flows": 0}, {"date": "2026-11-13", "equity": 9900, "net_flows": 0}]
    d, w, pk = drawdowns(hist, 9650, date(2026, 11, 16), 10000)
    assert round(d, 4) == round(250 / 9900, 4) and round(w, 4) == 0.035 and round(pk, 4) == 0.035
    p = new_portfolio("B", cfg["portfolios"]["B"])
    p.equity_history = hist
    p.cash = 9650
    dec = evaluate_entry(p, "SQQQ", 35, 100, date(2026, 11, 16), cfg, regime_confirmed=True, quote_fresh_for_fill=True)
    assert dec.verdict is Verdict.VETO and any("daily drawdown" in v for v in dec.vetoes)


def test_flows_do_not_count_as_returns(cfg):
    hist = [{"date": "2026-11-13", "equity": 10000, "net_flows": 0}, {"date": "2026-11-16", "equity": 12000, "net_flows": 2000}]
    d, w, pk = drawdowns(hist, 12000, date(2026, 11, 17), 10000)
    assert d == 0 and pk == 0


def test_two_contract_unlock_requires_history(cfg):
    ok, msgs = two_contract_validation(new_portfolio("B", cfg["portfolios"]["B"]), cfg)
    assert not ok and msgs


def test_pair_lookup(cfg):
    assert pair_for_symbol(cfg, "SOXS").group == "semis"
