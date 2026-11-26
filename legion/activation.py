"""Forward-paper activation gate. The unattended service may only SIMULATE orders when every owner/test gate below is
satisfied; otherwise it runs OBSERVE_ONLY (ingest, validate, alert, report) and every candidate is logged, never filled.
Gates are read from files the owner controls; nothing in a report or Drive file can satisfy them."""
import json, os

def evaluate(cfg, state_dir, native_spec_dir):
    g = {}
    g["starting_equity_set"] = cfg.get("paper_start_equity") not in (None, 0)
    variants = cfg.get("strategy_variants") or {}
    specs = {}
    for v in variants.values():
        try: specs[v] = json.load(open(os.path.join(native_spec_dir, f"{v}.json")))
        except Exception: specs[v] = None
    g["strategy_variant_configured"] = bool(variants)
    g["entry_parameters_owner_approved"] = bool(specs) and all(s and s["entry_confirmation"].get("approved") is True for s in specs.values())
    g["exit_rules_owner_approved"] = bool(specs) and all(s and s.get("exit_rules") for s in specs.values())
    ok = lambda f: os.path.exists(os.path.join(state_dir, "acceptance", f))
    g["robinhood_live_readonly_test_passed"] = ok("robinhood_live_readonly.json")
    g["google_drive_integration_test_passed"] = ok("google_drive_integration.json")
    g["emergency_stop_drill_passed"] = ok("emergency_stop_drill.json")
    g["owner_activation_signoff"] = ok("OWNER_ACTIVATION_SIGNOFF.json")
    g["no_emergency_stop"] = not os.path.exists(os.path.join(state_dir, "EMERGENCY_STOP"))
    return all(g.values()), g

def record_acceptance(state_dir, name, details):
    """Called by acceptance scripts on the host after a REAL test passes."""
    d = os.path.join(state_dir, "acceptance"); os.makedirs(d, exist_ok=True)
    json.dump(details, open(os.path.join(d, name), "w"), indent=1, default=str)
