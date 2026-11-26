"""Daily-bar backtester with conservative execution. Decisions use bars[0..i]; orders act on bar i+1.
Fills: entry = max(open, pivot) x (1 + slippage) + half spread; entry skipped if the bar opens above the permitted range or
never trades through the pivot. Stops: if a bar's open is below the stop the fill is the OPEN (gap-through-stop), else the stop,
minus slippage and half spread. If a bar touches both stop and target, the stop is assumed first. Commission per share."""
import math
from dataclasses import dataclass, field
from ..scanners import series as S
from . import parabolic as PB, exits as X

@dataclass
class Costs: slippage: float = 0.0010; half_spread: float = 0.0010; commission_per_share: float = 0.0; min_commission: float = 0.0
@dataclass
class Trade:
    symbol: str; entry_i: int; entry: float; stop: float; qty: int; exit_i: int = None; exit: float = None; reason: str = None
    r: float = None; pnl: float = None; mfe_r: float = 0.0; mae_r: float = 0.0; costs: float = 0.0; regime: str = None; partial: list = field(default_factory=list)

def run_symbol(sym, bars, cfg, p=PB.DEFAULT, costs=Costs(), equity=100_000.0, risk_pct=0.005, max_alloc=0.10, regime=None):
    trades, pos, i = [], None, 21
    while i < len(bars):                                                               # the final bar is always managed for exits
        if pos is None:
            if i >= len(bars) - 1: break                                               # no next bar to enter on
            s = PB.setup_at(bars, i, p)
            if s:
                nb = bars[i + 1]; P = s["pivot"]; hi_ok = P * (1 + p["max_drift"])
                if nb.o > hi_ok or nb.h < P: i += 1; continue                          # gapped above range / no trigger
                fill = max(nb.o, P) * (1 + costs.slippage + costs.half_spread)
                if fill > hi_ok * (1 + costs.slippage + costs.half_spread): i += 1; continue
                stop = X.initial_stop(cfg, fill, s)
                if stop >= fill or (fill - stop) / fill > p["max_stop"]: i += 1; continue
                tgt = X.target_price(cfg, fill, stop, s["atr14"])
                if tgt is not None and (tgt - fill) / (fill - stop) < p["min_rr"]: i += 1; continue
                qty = int(min(equity * risk_pct / (fill - stop), equity * max_alloc / fill))
                if qty < 1: i += 1; continue
                fee = max(costs.min_commission, costs.commission_per_share * qty)
                pos = Trade(sym, i + 1, fill, stop, qty, costs=fee, regime=(regime or {}).get(bars[i + 1].ts.date()))
                pos.hw, pos.tgt, pos.R, pos.open_qty = fill, tgt, fill - stop, qty
                pos.mae_r = min(0.0, (nb.l - fill) / pos.R); pos.mfe_r = max(0.0, (nb.h - fill) / pos.R)
                if nb.l <= pos.stop:                                                    # stop hit on the entry bar itself (conservative)
                    _close(pos, i + 1, pos.stop, "STOP_ENTRY_BAR", costs); trades.append(pos); pos = None
                i += 2                                                                  # entry bar fully handled; manage from the next bar
                continue
            i += 1; continue
        b = bars[i]
        R = pos.R; pos.mfe_r = max(pos.mfe_r, (b.h - pos.entry) / R); pos.mae_r = min(pos.mae_r, (b.l - pos.entry) / R)
        if b.l <= pos.stop:                                                            # stop first (gap-through-stop -> open)
            _close(pos, i, b.o if b.o < pos.stop else pos.stop, "GAP_THROUGH_STOP" if b.o < pos.stop else "STOP", costs); trades.append(pos); pos = None; i += 1; continue
        if pos.tgt and b.h >= pos.tgt:
            if cfg["target"] == "partial2R" and not pos.partial:
                half = pos.open_qty // 2
                if half >= 1:
                    pos.partial.append((i, pos.tgt, half)); pos.open_qty -= half; pos.stop = max(pos.stop, pos.entry)   # stop to breakeven
                pos.tgt = None
            else:
                _close(pos, i, pos.tgt, "TARGET", costs); trades.append(pos); pos = None; i += 1; continue
        pos.hw = max(pos.hw, b.h); atr = S.atr_wilder(bars[:i + 1], 14) or pos.R
        tl = X.trail_level(cfg, bars[:i + 1], pos.hw, atr)
        if cfg.get("trail") == "sma10" and tl and b.c < tl:
            _close(pos, i, b.c, "SMA10_CLOSE", costs); trades.append(pos); pos = None; i += 1; continue
        if tl and cfg.get("trail") != "sma10" and (cfg["target"] in (None, "partial2R")) and (cfg["target"] is None or pos.partial): pos.stop = max(pos.stop, tl)
        if cfg.get("max_hold") and i - pos.entry_i + 1 >= cfg["max_hold"]:
            _close(pos, i, b.c, "TIME", costs); trades.append(pos); pos = None
        i += 1
    if pos: _close(pos, len(bars) - 1, bars[-1].c, "END_OF_DATA", costs); trades.append(pos)
    return trades

def _close(t, i, px, reason, costs):
    fill = px * (1 - costs.slippage - costs.half_spread)
    t.exit_i, t.exit, t.reason = i, fill, reason
    part = sum((pp * (1 - costs.slippage - costs.half_spread) - t.entry) * q for _, pp, q in t.partial)
    t.pnl = part + (fill - t.entry) * t.open_qty - t.costs
    t.r = t.pnl / (t.R * t.qty)

def metrics(trades, equity0=100_000.0, bars_len=None):
    if not trades: return {"trades": 0, "note": "zero trades: no qualifying setups in the data"}
    rs = [t.r for t in trades]; w = [r for r in rs if r > 0]; l = [r for r in rs if r <= 0]
    eq, peak, mdd, curve = equity0, equity0, 0.0, []
    for t in sorted(trades, key=lambda t: t.exit_i):
        eq += t.pnl; peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak); curve.append(eq)
    rets = [(b - a) / a for a, b in zip([equity0] + curve, curve)]
    mu = sum(rets) / len(rets); sd = (sum((x - mu) ** 2 for x in rets) / max(1, len(rets) - 1)) ** 0.5
    dn = [x for x in rets if x < 0]; dsd = (sum(x * x for x in dn) / max(1, len(dn))) ** 0.5
    streak = best = 0
    for r in rs:
        streak = streak + 1 if r <= 0 else 0; best = max(best, streak)
    total = (eq - equity0) / equity0
    years = (bars_len or 252) / 252
    return {"trades": len(trades), "total_return": total, "cagr": (1 + total) ** (1 / years) - 1 if years > 0 and total > -1 else None,
            "win_rate": len(w) / len(rs), "expectancy_r": sum(rs) / len(rs), "profit_factor": (sum(w) / -sum(l)) if l and sum(l) < 0 else None,
            "sharpe_per_trade": mu / sd if sd else None, "sortino_per_trade": mu / dsd if dsd else None, "max_drawdown": mdd,
            "recovery_factor": total / mdd if mdd else None, "avg_win_r": sum(w) / len(w) if w else None, "avg_loss_r": sum(l) / len(l) if l else None,
            "avg_hold_bars": sum(t.exit_i - t.entry_i + 1 for t in trades) / len(trades), "avg_mfe_r": sum(t.mfe_r for t in trades) / len(trades),
            "avg_mae_r": sum(t.mae_r for t in trades) / len(trades), "max_consecutive_losses": best, "costs": sum(t.costs for t in trades),
            "exit_reasons": {r: sum(1 for t in trades if t.reason == r) for r in {t.reason for t in trades}}}

def walk_forward(universe, configs, train_bars, test_bars, p=PB.DEFAULT, min_train_trades=5, costs=Costs()):
    """universe: {sym: bars}. Choose the config with best TRAIN expectancy (min trades), evaluate it on the next TEST window only."""
    n = min(len(b) for b in universe.values()); folds, start = [], 0
    while start + train_bars + test_bars <= n:
        tr = {s: b[start:start + train_bars] for s, b in universe.items()}
        te = {s: b[start + train_bars - 40:start + train_bars + test_bars] for s, b in universe.items()}   # 40-bar warmup, trades only in test
        scored = []
        for cfg in configs:
            ts = [t for s, b in tr.items() for t in run_symbol(s, b, cfg, p, costs)]
            if len(ts) >= min_train_trades: scored.append((sum(t.r for t in ts) / len(ts), cfg))
        if not scored: folds.append({"start": start, "selected": None, "reason": "insufficient train trades"}); start += test_bars; continue
        best = max(scored, key=lambda x: x[0])[1]
        oos = [t for s, b in te.items() for t in run_symbol(s, b, best, p, costs) if t.entry_i >= 40]
        folds.append({"start": start, "selected": best, "train_expectancy_r": max(scored, key=lambda x: x[0])[0], "oos": metrics(oos, bars_len=test_bars)})
        start += test_bars
    return folds

def sensitivity(universe, cfg, key, values, p=PB.DEFAULT, costs=Costs()):
    out = {}
    for v in values:
        pp = {**p, key: v}; ts = [t for s, b in universe.items() for t in run_symbol(s, b, cfg, pp, costs)]
        out[v] = metrics(ts, bars_len=min(len(b) for b in universe.values()))
    return out

BIAS_DISCLOSURE = {"point_in_time_universe": False, "delisted_included": False, "survivorship_bias": "PRESENT unless the caller supplies a point-in-time universe including delisted names",
                   "fills": "conservative: adverse slippage + half spread both ways; gap-through-stop fills at open; stop-before-target on ambiguous bars"}
