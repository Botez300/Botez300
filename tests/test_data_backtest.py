import json
from datetime import date
from pathlib import Path

import pytest

from src.backtest.chains import HistoricalOptionsUnavailable, load_chain_history
from src.backtest.engine import MarketData, SyntheticOptions, run_backtest
from src.backtest.metrics import summarize
from src.broker.robinhood_mcp import import_equity_historicals, load_snapshot
from src.data.history import detect_splits, load_bars
from src.options.pricing import bs_put, bs_put_delta, implied_vol_put
from src.reports.projections import project
from src.safety import LiveTradingForbiddenError


def test_black_scholes_sanity():
    p = bs_put(100, 90, 30 / 365, 0.04, 0.5)
    assert 0 < p < 10
    assert -0.5 < bs_put_delta(100, 90, 30 / 365, 0.04, 0.5) < 0
    assert implied_vol_put(p, 100, 90, 30 / 365, 0.04) == pytest.approx(0.5, abs=1e-4)


def test_import_drops_interpolated(tmp_path):
    payload = {"data": {"results": [{"symbol": "XYZ", "interval": "day", "bars": [
        {"begins_at": "2026-01-02T00:00:00Z", "open_price": "10", "close_price": "10.5", "high_price": "11", "low_price": "9.5", "volume": 1},
        {"begins_at": "2026-01-05T00:00:00Z", "open_price": "10", "close_price": "10", "high_price": "10", "low_price": "10", "volume": 0, "interpolated": True},
    ]}]}}
    f = tmp_path / "h.json"
    f.write_text(json.dumps(payload))
    assert import_equity_historicals([f], "raw", tmp_path) == {"XYZ": 1}


def test_snapshot_refuses_forbidden_tool(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"as_of": "2026-11-14", "captured_at": "2026-11-14T20:00:00Z",
                                                        "source_tools": ["place_option_order"]}))
    with pytest.raises(LiveTradingForbiddenError):
        load_snapshot(tmp_path)


def test_real_snapshot_loads():
    snap = load_snapshot(Path("data/snapshots/2026-11-14"))
    assert len(snap.option_quotes) == 117 and not snap.problems
    assert all(q.delta is not None and q.delta < 0 for q in snap.option_quotes)


def test_split_detection_on_verified_data():
    ev = detect_splits(load_bars("SOXL", "raw"), load_bars("SOXL", "adjusted"), "SOXL")
    assert [(str(e.effective_date), round(1 / e.price_factor)) for e in ev] == [("2021-03-02", 15)]


def test_no_genuine_options_dataset_claimed():
    with pytest.raises(HistoricalOptionsUnavailable):
        load_chain_history("TQQQ")


def test_synthetic_skew_direction(cfg):
    o = SyntheticOptions(cfg)
    assert o.iv(0.6, 50, 40, "TQQQ") > o.iv(0.6, 50, 50, "TQQQ")   # bull: OTM put IV higher
    assert o.iv(0.6, 50, 40, "SQQQ") < o.iv(0.6, 50, 50, "SQQQ")   # inverse: skew flips


@pytest.fixture(scope="module")
def md(cfg):
    return MarketData(cfg)


@pytest.mark.parametrize("pid", ["A", "B"])
def test_backtest_pnl_reconciles(md, cfg, pid):
    r = run_backtest(md, cfg, pid, date(2020, 1, 1), date(2023, 12, 31))
    s = summarize(r)
    assert abs(s["pnl_reconciliation_gap"]) < 1e-6
    assert r.equity.iloc[0] == pytest.approx(cfg["portfolios"][pid]["starting_cash"], rel=0.01)


def test_backtest_deterministic(md, cfg):
    a = run_backtest(md, cfg, "B", date(2022, 1, 1), date(2022, 12, 31))
    b = run_backtest(md, cfg, "B", date(2022, 1, 1), date(2022, 12, 31))
    assert a.equity.equals(b.equity)


def test_backtest_respects_collateral(md, cfg):
    r = run_backtest(md, cfg, "A", date(2018, 1, 1), date(2026, 11, 13))
    for t in r.trades:
        assert t.collateral <= 0.40 * 5000 * 1.35  # 40% of equity (equity may have grown modestly)
    assert (r.collateral <= 0.41 * r.equity).all()


def test_projection_formula():
    s = project(5000, 0.05, 15)
    assert s.iloc[12] == pytest.approx(5000 * 1.05 ** 12) and len(s) == 181
