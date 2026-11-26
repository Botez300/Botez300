"""Trade-entry gate for v2 (Phase 3) strategy specs. Mechanical qualification is necessary but never sufficient."""
from .defs import STRATEGIES

def gate_v2(c, snap, spec, sp):
    from ..strategies import common
    sid = spec["strategy"]; a = spec["activation"]; why = []
    if not a.get("approved"): why.append("NOT_ACTIVATED_PENDING_OWNER_APPROVAL")
    if spec.get("pending_semantics"): why.append(f"PENDING_SEMANTICS {len(spec['pending_semantics'])}")
    if spec.get("data_gaps"): why.append(f"DATA_GAPS {len(spec['data_gaps'])}")
    if not spec.get("entry_confirmation", {}).get("defined"): why.append("ENTRY_CONFIRMATION_RULES_UNDEFINED")
    if why: return False, [], [f"STRATEGY_INCOMPLETE {sid}: {w}" for w in why]
    data = snap.extra.get("scanner_data")
    if data is None: return False, [], ["SCANNER_DATA_UNAVAILABLE"]
    tree = STRATEGIES[sid](data, spec["params"])
    if tree["status"] != "PASS": return False, [tree], [f"MECHANICAL_{tree['status']}"]
    if sid in ("TURTLE", "MAGIC_FORMULA") and not c.get("additional_qualifying_strategies"):
        return False, [tree], [f"{sid}_ONLY_NOT_BUY_NOW"]
    res = common(c, snap, sp)
    bad = [f"{r['criterion_id']}_{r['status']}" for r in res if r["status"] != "PASS"]
    return not bad, [tree] + res, bad

NATIVE_SPEC_DIR = __import__("os").path.join(__import__("os").path.dirname(__file__), "..", "..", "specs", "native")

def gate_native(c, snap, spec, sp, max_equity_spread=0.005):
    """Trade-entry gate for LEGION_NATIVE variants. Owner-approved mechanics are necessary but not sufficient."""
    from ..strategies import common
    from .native import NATIVE, parabolic_native, turtle_native
    from .entry import confirm
    nid = spec["scanner"]; why = []
    if spec.get("classification") != "LEGION_NATIVE": why.append("NOT_A_NATIVE_SPEC")
    if not spec.get("mechanical_semantics_approved"): why.append("NATIVE_MECHANICS_NOT_APPROVED")
    if spec.get("data_gaps"): why.append(f"DATA_GAPS {len(spec['data_gaps'])}")
    if not spec["entry_confirmation"].get("approved"): why.append("ENTRY_CONFIRMATION_THRESHOLDS_PENDING_APPROVAL")
    if why: return False, [], [f"STRATEGY_INCOMPLETE {nid}: {w}" for w in why]
    d = snap.extra.get("scanner_data")
    if d is None: return False, [], ["SCANNER_DATA_UNAVAILABLE"]
    diag = {}
    if nid == "PARABOLIC_NATIVE": tree, diag = parabolic_native(d, spec["params"])
    else: tree = NATIVE[nid](d, spec["params"])
    if nid == "TURTLE_NATIVE": diag["sizing"] = tree.get("sizing")
    diag["mechanical"] = tree["status"]
    if tree["status"] != "PASS": return False, [tree], [f"MECHANICAL_{tree['status']}"]
    if nid in ("TURTLE_NATIVE", "MAGIC_FORMULA_NATIVE") and not c.get("additional_qualifying_strategies"):
        return False, [tree], [f"{nid}_ONLY_NOT_BUY_NOW"]
    ent = confirm(nid, d, c, spec["entry_confirmation"]["proposed_thresholds"], diag)
    if ent["status"] != "PASS": return False, [tree, ent], [f"ENTRY_CONFIRMATION_{ent['status']}"]
    q = snap.quote; bid, ask = getattr(q, "bid", None), getattr(q, "ask", None)
    spread = None if not bid or not ask or ask < bid else (ask - bid) / ((ask + bid) / 2)
    res = common(c, snap, sp) + [{"criterion_id": "EQUITY_SPREAD_LE_0.5PCT", "status": "UNVERIFIED" if spread is None else "PASS" if spread <= max_equity_spread else "FAIL", "detail": spread}]
    bad = [f"{r['criterion_id']}_{r['status']}" for r in res if r["status"] != "PASS"]
    return not bad, [tree, ent] + res, bad
