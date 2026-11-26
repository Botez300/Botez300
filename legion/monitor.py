"""Deterministic paper-position monitor. Pure software: no model calls."""
from . import freshness
from .rh import Contract
from .strategies import load_spec, exit_signal, SPEC_DIR

def monitor_positions(broker, market, rh, now, alert, spec_dir=SPEC_DIR, option_close_dte=1):
    out = []
    for p in list(broker.s["stocks"]):
        try: snap = market.snapshot(p["symbol"], now)
        except Exception as e: alert("MONITOR_DATA_FAILURE", f"{p['symbol']}: {e}"); continue
        ok, why = freshness.assess(snap.quote.ts, now)
        if not ok: alert("MONITOR_STALE_QUOTE", f"{p['symbol']}: {why}"); continue
        broker.mark_stock(p["symbol"], snap.quote.price)
        p = next(x for x in broker.s["stocks"] if x["symbol"] == p["symbol"])
        try: spec = load_spec(p["strategy"], spec_dir)
        except Exception: spec = None
        if (r := exit_signal(p, snap, spec)): broker.close_stock(p["symbol"], snap.quote.price, r); out.append((p["symbol"], r))
    for o in list(broker.s["options"]):
        legs = [(sd, Contract(i, o["underlying"], t, k, o["expiry"])) for sd, i, k, t in o["legs"]]
        try: rh.option_quotes([c for _, c in legs])
        except Exception as e: alert("MONITOR_DATA_FAILURE", f"{o['underlying']}: {e}"); continue
        if any(c.bid is None or c.ask is None for _, c in legs): continue
        val = sum((1 if sd == "BUY" else -1) * (c.bid + c.ask) / 2 * 100 * o["qty"] for sd, c in legs)
        o["value"] = val
        dte = (__import__("datetime").date.fromisoformat(o["expiry"]) - now.date()).days
        if dte <= option_close_dte: broker.close_option(o["signal_id"], val, "EXPIRATION_GUARD"); out.append((o["underlying"], "EXPIRATION_GUARD"))
    broker._save(); return out
