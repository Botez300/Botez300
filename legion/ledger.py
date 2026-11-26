"""Persistent duplicate-prevention ledger (report_id + content hash)."""
import json, os, tempfile
class Ledger:
    def __init__(self, path):
        self.path = path
        self.d = {"entries": []}
        if os.path.exists(path):
            with open(path) as f: self.d = json.load(f)
    @property
    def ids(self): return {e["report_id"] for e in self.d["entries"] if e.get("report_id")}
    @property
    def hashes(self): return {e["sha256"] for e in self.d["entries"]}
    def record(self, res, decision):
        self.d["entries"].append({"report_id": res.report_id, "sha256": res.sha256,
                                  "filename": res.filename, "decision": decision, "reasons": res.reasons})
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or ".")
        with os.fdopen(fd, "w") as f: json.dump(self.d, f, indent=2)
        os.replace(tmp, self.path)
