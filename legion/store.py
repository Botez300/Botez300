"""SQLite ingestion store. Drop-in replacement for the JSON Ledger (same ids/hashes/record API) that also logs EVERY
ingestion attempt, including rejected duplicates, and supports expected-hash verification with quarantine."""
import json, os, shutil, sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (sha256 TEXT PRIMARY KEY, report_id TEXT, filename TEXT, decision TEXT, reasons TEXT, first_seen TEXT);
CREATE INDEX IF NOT EXISTS reports_id ON reports(report_id);
CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, filename TEXT, sha256 TEXT, report_id TEXT, outcome TEXT, reasons TEXT);
"""
class IntegrityError(ValueError): pass

class SqliteLedger:
    def __init__(self, path):
        self.path = path; self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL"); self.db.executescript(SCHEMA)
    @property
    def ids(self): return {r[0] for r in self.db.execute("SELECT report_id FROM reports WHERE report_id IS NOT NULL")}
    @property
    def hashes(self): return {r[0] for r in self.db.execute("SELECT sha256 FROM reports")}
    @property
    def d(self):                                           # JSON-Ledger compatibility for callers that inspect entries
        return {"entries": [dict(zip(("sha256", "report_id", "filename", "decision"), r)) for r in self.db.execute("SELECT sha256, report_id, filename, decision FROM reports")]}
    def record(self, res, decision):
        now = datetime.now(timezone.utc).isoformat()
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO reports VALUES (?,?,?,?,?,?)", (res.sha256, res.report_id, res.filename, decision, json.dumps(res.reasons), now))
            self.db.execute("INSERT INTO attempts(at, filename, sha256, report_id, outcome, reasons) VALUES (?,?,?,?,?,?)", (now, res.filename, res.sha256, res.report_id, decision, json.dumps(res.reasons)))
    def attempt(self, res, outcome):
        self.db.execute("INSERT INTO attempts(at, filename, sha256, report_id, outcome, reasons) VALUES (?,?,?,?,?,?)",
                        (datetime.now(timezone.utc).isoformat(), res.filename, res.sha256, res.report_id, outcome, json.dumps(res.reasons)))
    def attempts(self): return [dict(zip(("id", "at", "filename", "sha256", "report_id", "outcome", "reasons"), r)) for r in self.db.execute("SELECT * FROM attempts ORDER BY id")]

def verify_expected_hash(raw: bytes, expected: str, name: str, quarantine_dir: str):
    """Never edit `expected` to make a mismatch disappear: a mismatch quarantines the bytes and raises."""
    import hashlib
    got = hashlib.sha256(raw).hexdigest()
    if got != expected:
        os.makedirs(quarantine_dir, exist_ok=True)
        open(os.path.join(quarantine_dir, name + ".hash_mismatch"), "wb").write(raw)
        raise IntegrityError(f"{name}: sha256 {got} != expected {expected}; quarantined")
    return got
