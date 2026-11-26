import json, os
from datetime import datetime, timezone
from .validator import validate
from .ledger import Ledger

class Pipeline:
    def __init__(self, ledger: Ledger, engines, quarantine_dir):
        self.ledger, self.engines, self.q = ledger, engines, quarantine_dir
        os.makedirs(quarantine_dir, exist_ok=True)
    def ingest(self, item, now=None):
        raw = item.read()
        r = validate(raw, item.name, now, item.size, self.ledger.ids, self.ledger.hashes)
        if r.admitted:
            doc = json.loads(raw)
            for e in self.engines: e.on_report(doc)
            self.ledger.record(r, "ADMITTED")
        else:
            with open(os.path.join(self.q, item.name + ".reject.json"), "w") as f:
                json.dump({"filename": r.filename, "sha256": r.sha256, "reasons": r.reasons}, f, indent=2)
            # duplicates are not re-recorded
            if not any(x.startswith("DUPLICATE") for x in r.reasons): self.ledger.record(r, "REJECTED")
        return r
