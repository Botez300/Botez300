"""Operator commands: python -m legion.ops [status|resume --confirm|emergency-stop|stop] --state <dir>"""
import argparse, json, os, sys
from . import constitution as C
def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--state", default="state"); ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "resume": C.resume(a.state, a.confirm); print("risk halt cleared by operator"); return 0
    if a.cmd == "emergency-stop": open(os.path.join(a.state, "EMERGENCY_STOP"), "w").write("operator"); print("EMERGENCY_STOP set"); return 0
    if a.cmd == "stop": open(os.path.join(a.state, "STOP_REQUEST"), "w").write("operator"); print("STOP_REQUEST set"); return 0
    if a.cmd == "status":
        hb = os.path.join(a.state, "heartbeat.json")
        print(json.dumps({"heartbeat": json.load(open(hb)) if os.path.exists(hb) else None, "risk_halt": C.latched(a.state),
                          "emergency_stop": os.path.exists(os.path.join(a.state, "EMERGENCY_STOP"))}, indent=1)); return 0
    print(__doc__); return 2
if __name__ == "__main__": sys.exit(main())
