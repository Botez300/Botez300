"""Magic Formula universe ranking job (owner spec 2026-11-26).
1 rank earnings yield high->low; 2 rank ROIC high->low; 3 sum ranks; 4 rank combined low->high.
Ties: standard competition ranking ('1224') at every step; final ordering tie-break = EY rank, then ticker (A-Z).
Only names whose four mechanical conditions all PASS are ranked; everything else is reported in coverage."""
from .defs import Data, magic

def _competition(vals, reverse):
    order = sorted(vals, key=lambda kv: kv[1], reverse=reverse); out, prev, r = {}, object(), 0
    for i, (k, v) in enumerate(order, 1):
        if v != prev: r, prev = i, v
        out[k] = r
    return out

def rank(datas: list[Data], params: dict, top=10):
    q, cov = {}, {"universe": len(datas), "qualified": 0, "failed": 0, "unverified": 0, "missing": {}}
    for d in datas:
        tree, ey = magic(d, params)
        if tree["status"] == "PASS": q[d.ticker] = (ey, d.roic_ttm)
        else:
            cov["failed" if tree["status"] == "FAIL" else "unverified"] += 1
            for ch in tree["children"]:
                if ch["status"] == "UNVERIFIED": cov["missing"][ch["id"]] = cov["missing"].get(ch["id"], 0) + 1
    cov["qualified"] = len(q)
    if not q: return [], cov
    ry = _competition([(k, v[0]) for k, v in q.items()], True); rr = _competition([(k, v[1]) for k, v in q.items()], True)
    comb = {k: ry[k] + rr[k] for k in q}; rc = _competition(list(comb.items()), False)
    rows = sorted(({"ticker": k, "earnings_yield": q[k][0], "roic": q[k][1], "ey_rank": ry[k], "roic_rank": rr[k], "combined": comb[k],
                    "final_rank": rc[k], "label": "MECHANICAL_ONLY_NOT_BUY_NOW"} for k in q), key=lambda r: (r["final_rank"], r["ey_rank"], r["ticker"]))
    cov["ties_in_final_rank"] = len(rows) - len({r["final_rank"] for r in rows})
    return rows[:top], cov
