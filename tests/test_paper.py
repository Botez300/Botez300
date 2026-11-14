from datetime import date, datetime, timezone

import pytest

from src.paper.broker import PaperBroker
from src.paper.fills import simulate_buy, simulate_sell
from src.paper.manager import evaluate_position
from src.portfolio import portfolio as store
from src.portfolio.portfolio import new_portfolio

RTH = datetime(2026, 11, 16, 15, 5, tzinfo=timezone.utc)  # 10:05 ET Monday


def test_sell_fill_is_conservative(cfg, quote_factory):
    q = quote_factory(bid=0.80, ask=0.90)
    r = simulate_sell(q, 1, RTH, cfg["execution"], cfg["screener"])
    assert r.filled and q.bid <= r.price < q.mid


def test_buy_fill_is_conservative(cfg, quote_factory):
    q = quote_factory(bid=0.80, ask=0.90)
    r = simulate_buy(q, 1, RTH, cfg["execution"], cfg["screener"])
    assert r.filled and q.mid < r.price <= q.ask


def test_robinhood_fill_rate_cap(cfg, quote_factory):
    q = quote_factory(bid=0.80, ask=0.90, hfs=0.81)
    assert simulate_sell(q, 1, RTH, cfg["execution"], cfg["screener"]).price <= 0.81


@pytest.mark.parametrize("kw,why", [
    ({"updated": datetime(2026, 11, 16, 14, 0, tzinfo=timezone.utc)}, "age"),
    ({"bid": 0.0}, "two-sided"),
    ({"bid": 0.20, "ask": 0.60}, "spread"),
    ({"bid_size": 0}, "size"),
])
def test_no_fill_conditions(cfg, quote_factory, kw, why):
    r = simulate_sell(quote_factory(**kw), 1, RTH, cfg["execution"], cfg["screener"])
    assert not r.filled and why in r.reason


def test_no_fill_outside_rth(cfg, quote_factory):
    sat = datetime(2026, 11, 14, 20, 40, tzinfo=timezone.utc)
    q = quote_factory(updated=sat)
    assert not simulate_sell(q, 1, sat, cfg["execution"], cfg["screener"]).filled


def test_order_lifecycle_and_idempotency(cfg, quote_factory):
    p = new_portfolio("B", cfg["portfolios"]["B"])
    br = PaperBroker(cfg)
    q = quote_factory()
    o1 = br.create_sell_intent(p, q, 1, date(2026, 11, 16), RTH, 0.80, "PASS")
    o2 = br.create_sell_intent(p, q, 1, date(2026, 11, 16), RTH, 0.80, "PASS")
    assert o1 is o2 and len(p.orders) == 1 and o1.label == "PAPER"
    assert p.reserved_collateral() == 3500  # pending order collateral counts
    r = br.try_fill_sell(p, o1, q, RTH)
    assert r.filled and o1.status == "FILLED" and len(p.open_puts()) == 1
    assert p.cash == pytest.approx(10000 + r.price * 100 - 0.03)
    assert p.equity() == pytest.approx(10000 + (r.price - q.mark) * 100 - 0.03)


def test_expire_worthless_and_assignment(cfg, quote_factory):
    p = new_portfolio("B", cfg["portfolios"]["B"])
    br = PaperBroker(cfg)
    q = quote_factory()
    o = br.create_sell_intent(p, q, 1, date(2026, 11, 16), RTH, 0.80, "PASS")
    br.try_fill_sell(p, o, q, RTH)
    pos = p.open_puts()[0]
    cash_before = p.cash
    assert br.settle_expiration(p, pos, 33.0, date(2026, 12, 18)) == "ASSIGNED"
    assert p.cash == pytest.approx(cash_before - 3500)
    sh = p.shares[0]
    assert sh.shares == 100 and sh.cost_basis == 35.0 and sh.last_price == 33.0
    assert p.reserved_collateral() == 0  # collateral released into shares
    assert p.equity() == pytest.approx(cash_before - 3500 + 3300)
    pnl = br.sell_shares(p, sh, 34.0, date(2026, 12, 21), "liquidate")
    assert pnl == pytest.approx(-100.0)


def test_unfilled_day_orders_expire(cfg, quote_factory):
    p = new_portfolio("B", cfg["portfolios"]["B"])
    br = PaperBroker(cfg)
    o = br.create_sell_intent(p, quote_factory(), 1, date(2026, 11, 14), RTH, 0.8, "CONDITIONAL")
    br.expire_unfilled(p, date(2026, 11, 16))
    assert o.status == "EXPIRED" and p.reserved_collateral() == 0


def test_management_rules(cfg):
    m = cfg["management"]
    acts = evaluate_position(1.0, 0.45, date(2026, 12, 18), date(2026, 11, 30), 35, 40, True, m)
    assert any(a.action == "CLOSE" and "profit" in a.reason for a in acts)
    acts = evaluate_position(1.0, 0.9, date(2026, 12, 18), date(2026, 12, 12), 35, 40, True, m)
    assert any("DTE" in a.reason for a in acts)
    acts = evaluate_position(1.0, 2.1, date(2026, 12, 18), date(2026, 11, 30), 35, 33, True, m)
    assert any(a.action == "FLAG" and "2.0x" in a.reason for a in acts)  # flag, not auto-close/roll
    acts = evaluate_position(1.0, 0.9, date(2026, 12, 18), date(2026, 11, 30), 35, 40, False, m)
    assert any("regime" in a.reason for a in acts)


def test_reset_requires_confirmation_and_archives(cfg, tmp_path):
    base = tmp_path / "state"
    p = store.load("A", cfg, base)
    p.cash = 1.0
    store.save(p, base)
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "x.md").write_text("keep me")
    with pytest.raises(PermissionError):
        store.reset("A", cfg, "yes", base)
    arch = store.reset("A", cfg, "RESET A", base, tmp_path / "reports")
    assert (arch / "A.json").exists() and (arch / "reports" / "x.md").read_text() == "keep me"
    assert store.load("A", cfg, base).cash == 5000
