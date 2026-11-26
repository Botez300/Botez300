"""Exit-management research variants (NOT owner-approved). Each config is independently testable:
{"stop": consolidation_low|atr2|tech, "target": None|2R|3R|partial2R|atr3, "trail": None|pct10|atr3|sma10|prior_low|chandelier, "max_hold": int|None}"""
from ..scanners import series as S

STOPS = ("consolidation_low", "atr2")
TARGETS = (None, "2R", "3R", "partial2R", "atr3")
TRAILS = (None, "pct10", "atr3", "sma10", "prior_low", "chandelier")

def initial_stop(cfg, entry, setup):
    if cfg["stop"] == "atr2": return entry - 2 * setup["atr14"]
    return setup["cons_low"]

def target_price(cfg, entry, stop, atr):
    r = entry - stop
    return {"2R": entry + 2 * r, "3R": entry + 3 * r, "partial2R": entry + 2 * r, "atr3": entry + 3 * atr}.get(cfg.get("target"))

def trail_level(cfg, bars_to_now, high_water, atr):
    t = cfg.get("trail"); c = [x.c for x in bars_to_now]
    if t == "pct10": return high_water * 0.90
    if t == "atr3": return high_water - 3 * atr
    if t == "sma10": return S.sma(c, 10)                       # exit on a CLOSE below; handled by caller
    if t == "prior_low": return bars_to_now[-1].l
    if t == "chandelier": return max(x.h for x in bars_to_now[-22:]) - 3 * atr
    return None

def variants():
    out = []
    for st in STOPS:
        for tg in TARGETS:
            for tr in TRAILS:
                if tg in ("2R", "3R", "atr3") and tr is not None: continue      # full exits at target don't need a trail
                for mh in (5, 10, 20):
                    out.append({"stop": st, "target": tg, "trail": tr, "max_hold": mh})
    return out
