"""Host acceptance tests. Writes state/acceptance/<name>.json ONLY when the real test passes. Never run in CI.
  robinhood : authenticated read-only quote + bars + option chain via the app's own transport
  drive     : reads the genuine report from the configured local sync dir (or API), verifies hash, ingests twice (dup rejected)
  estop     : writes EMERGENCY_STOP, confirms the service refuses to start, removes it"""
import argparse, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from legion.activation import record_acceptance
GEN, SHA = "DAILY_2026-11-26_123541.json", "443e77ac043e0432857a3640bca861e22901204431985c0496e7a44e9633373c"

def robinhood(a):
    from legion.rh import RobinhoodClient, McpHttpTransport, ResilientTransport
    c = RobinhoodClient(ResilientTransport(McpHttpTransport())); q = c.quote("SPY"); b = c.bars("SPY", "2026-01-02"); ch = c.chain("SPY")
    if not (q.price and q.ts and len(b) > 100 and ch["expirations"]): raise SystemExit("FAIL: incomplete read-only data")
    for blocked in ("place_equity_order", "cancel_equity_order", "exercise_option"):
        try: c.call(blocked, {}); raise SystemExit(f"FAIL: {blocked} was not blocked")
        except PermissionError: pass
    record_acceptance(a.state, "robinhood_live_readonly.json", {"at": datetime.now(timezone.utc).isoformat(), "spy": q.price, "quote_ts": q.ts, "bars": len(b), "expirations": len(ch["expirations"])})
    print("PASS robinhood")

def drive(a):
    cfg = json.load(open(a.config)); p = os.path.join(cfg["local_dir"], GEN)
    raw = open(p, "rb").read(); h = hashlib.sha256(raw).hexdigest()
    if h != SHA: raise SystemExit(f"FAIL: hash {h}")
    out = os.path.join(a.state, "acceptance_genuine_verification.json")
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "verify_genuine_report.py"), p, SHA, out], check=True)
    r = json.load(open(out))
    if r["paper_orders"] != 0 or r["ingestion_1"]["tradeable"] or "DUPLICATE_CONTENT_HASH" not in r["ingestion_2"]["reasons"]: raise SystemExit("FAIL: unexpected ingestion result")
    record_acceptance(a.state, "google_drive_integration.json", {"at": datetime.now(timezone.utc).isoformat(), "path": p, "sha256": h, "dup_rejected": True})
    print("PASS drive (read). Outbox publication is verified separately once a Drive API credential exists.")

def estop(a):
    sd = a.state; f = os.path.join(sd, "EMERGENCY_STOP"); open(f, "w").write("drill")
    tmpcfg = os.path.join(sd, "estop_drill_config.json"); json.dump({"state_dir": sd, "source": "local", "local_dir": sd, "paper_start_equity": 1}, open(tmpcfg, "w"))
    rc = subprocess.run([sys.executable, "-m", "legion.service", "--config", tmpcfg], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).returncode
    os.remove(f); os.remove(tmpcfg)
    if rc != 3: raise SystemExit(f"FAIL: service exit code {rc} (expected 3)")
    record_acceptance(sd, "emergency_stop_drill.json", {"at": datetime.now(timezone.utc).isoformat(), "exit_code": rc}); print("PASS estop")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("test"); ap.add_argument("--state", required=True); ap.add_argument("--config")
    a = ap.parse_args(); os.makedirs(a.state, exist_ok=True); {"robinhood": robinhood, "drive": drive, "estop": estop}[a.test](a)
