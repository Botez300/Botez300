"""Universe scan: evaluate a strategy for every ticker, keep PASS results only, rank, cap. Never forces results."""
from .defs import STRATEGIES, parabolic, weinstein_long_base, turtle_research
from .tri import flatten

RANKERS = {   # ASSUMPTION (owner did not specify ranking keys except Magic Formula): see docs/ASSUMPTIONS_APPROVAL.md
    "PARABOLIC_MOMENTUM": lambda d, diag: -(diag["extension_vs_sma20_pct"] or 0),
    "WEINSTEIN_STAGE_2": lambda d, diag: d.ticker, "CAN_SLIM": lambda d, diag: d.ticker,
    "MINERVINI_VCP_SEPA": lambda d, diag: d.ticker, "TURTLE": lambda d, diag: d.ticker}

def scan(sid, datas, spec):
    p, out, counts = spec["params"], [], {"PASS": 0, "FAIL": 0, "UNVERIFIED": 0}
    unv_reasons = {}
    for d in datas:
        tree = STRATEGIES[sid](d, p); counts[tree["status"]] += 1
        if tree["status"] == "UNVERIFIED":
            for n in flatten(tree):
                if n["status"] == "UNVERIFIED" and "children" not in n: unv_reasons[n["detail"]] = unv_reasons.get(n["detail"], 0) + 1
        if tree["status"] != "PASS": continue
        diag = parabolic(d, p)[1] if sid == "PARABOLIC_MOMENTUM" else {}
        if sid == "WEINSTEIN_STAGE_2": diag["long_base"] = weinstein_long_base(d)
        if sid == "TURTLE": diag["research"] = turtle_research(d)
        out.append((RANKERS[sid](d, diag), d.ticker, {"ticker": d.ticker, "status": "MECHANICALLY_QUALIFIED", "diagnostics": diag,
                                                      "label": "NOT_A_TRADE_SIGNAL"}))
    out.sort(key=lambda t: (t[0], t[1]))
    return {"strategy": sid, "counts": counts, "candidates": [x[2] for x in out[: spec["max_candidates"]]],
            "unverified_reasons": dict(sorted(unv_reasons.items(), key=lambda kv: -kv[1])), "activation_approved": spec["activation"]["approved"]}
