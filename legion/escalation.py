"""Claude is NOT in the hot path. When deterministic code meets something it cannot decide, it writes an escalation
request; a human (or an explicitly configured command) decides whether to invoke Claude. Nothing is auto-invoked."""
import json, os, time
def escalate(state_dir, reason, payload):
    d = os.path.join(state_dir, "escalations"); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{int(time.time())}_{reason}.json"); json.dump({"reason": reason, "payload": payload, "status": "OPEN"}, open(p, "w")); return p
