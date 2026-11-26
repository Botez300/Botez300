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
