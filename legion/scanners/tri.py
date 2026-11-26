"""Three-state logic. AND passes only when every child passes; OR passes when at least one child is verified true."""
PASS, FAIL, UNV = "PASS", "FAIL", "UNVERIFIED"

def node(id, status, detail="", children=None, op=None):
    n = {"id": id, "status": status, "detail": detail}
    if children is not None: n["children"], n["op"] = children, op
    return n
def AND(id, kids, detail=""):
    s = FAIL if any(k["status"] == FAIL for k in kids) else PASS if kids and all(k["status"] == PASS for k in kids) else UNV
    return node(id, s, detail, kids, "AND")
def OR(id, kids, detail=""):
    s = PASS if any(k["status"] == PASS for k in kids) else FAIL if kids and all(k["status"] == FAIL for k in kids) else UNV
    return node(id, s, detail, kids, "OR")

def cmp(id, a, op, b, detail=""):
    """Comparison with explicit strictness. None on either side => UNVERIFIED (unknown data never passes)."""
    if a is None or b is None: return node(id, UNV, detail or "missing data")
    ok = {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b, "==": a == b}[op]
    return node(id, PASS if ok else FAIL, f"{detail}{a!r} {op} {b!r}")
def within_pct(id, x, ref, pct):
    """Inclusive band: |x/ref - 1| <= pct."""
    if x is None or ref is None or ref == 0: return node(id, UNV, "missing data")
    d = abs(x / ref - 1)
    return node(id, PASS if d <= pct + 1e-12 else FAIL, f"|{x}/{ref}-1|={d:.6f} <= {pct}")
def unv(id, why): return node(id, UNV, why)

def window_group(id, conds, window, mode):
    """conds: list of (cid, fn(j)->node) evaluated j candles back (0 = latest completed).
    mode 'common_anchor': all conditions true on the same candle within the window.
    mode 'independent':  each condition true on at least one (possibly different) candle within the window."""
    if mode == "common_anchor":
        return OR(id, [AND(f"{id}@{j}", [fn(j) for _, fn in conds]) for j in range(window)], "common_anchor")
    if mode == "independent":
        return AND(id, [OR(f"{cid}@any", [fn(j) for j in range(window)]) for cid, fn in conds], "independent")
    return unv(id, f"unknown window mode {mode}")

def flatten(n, out=None):
    out = [] if out is None else out; out.append(n)
    for k in n.get("children", []): flatten(k, out)
    return out
