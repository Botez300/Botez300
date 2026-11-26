import json, os
from datetime import datetime, timezone
class Alerts:
    """Local alert log (state/alerts.jsonl). Pushing to 09_Alerts would need a write-scoped Drive credential: not implemented."""
    def __init__(self, path): self.path = path
    def __call__(self, kind, msg=""):
        with open(self.path, "a") as f: f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "kind": kind, "msg": str(msg)}) + "\n")
