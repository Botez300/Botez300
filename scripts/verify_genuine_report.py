"""Phase 5 genuine-report integration check. Usage: python scripts/verify_genuine_report.py <raw.json> <expected_sha256> <out.json>
Validates bytes against the PINNED schema, the expected hash, timestamps/session/expiry/status/safety flags, provenance,
then ingests twice through the production orchestrator path (SQLite ledger) and proves the duplicate is rejected."""
import hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jsonschema import Draft202012Validator, FormatChecker
from legion import calendar as cal
from legion.eligibility import evaluate_report
from legion.engine import Orchestrator
from legion.evidence import SOURCES
from legion.paper import PaperBroker
from legion.store import SqliteLedger, verify_expected_hash

class Item:
    def __init__(s, n, b): s.name, s._b, s.size, s.age, s.md5, s.token = n, b, len(b), 1e9, None, n
    def read(s): return s._b
class NoMarket:
    def snapshot(self, t, now): raise RuntimeError("market data not reached for non-tradeable reports")

def main(path, expected, out, now=None):
    now = now or datetime.now(timezone.utc); raw = open(path, "rb").read(); name = os.path.basename(path); R = {}
    R["sha256"] = verify_expected_hash(raw, expected, name, os.path.join(tempfile.gettempdir(), "legion_quarantine"))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    blob = subprocess.run(["git", "hash-object", "schemas/legion_signal_v1_1.schema.json"], cwd=root, capture_output=True, text=True).stdout.strip()
    R["schema_blob_sha"] = blob
    doc = json.loads(raw); sch = json.load(open(os.path.join(root, "schemas", "legion_signal_v1_1.schema.json")))
    errs = [e.message for e in Draft202012Validator(sch, format_checker=FormatChecker()).iter_errors(doc)]
    R["schema_v1_1_errors"] = errs
    ts = lambda s: datetime.fromisoformat(s)
    g, m, v = ts(doc["generated_at"]), ts(doc["market_data_as_of"]), ts(doc["valid_until"])
    R["checks"] = {
        "report_id_matches_filename": name == doc["report_id"] + ".json",
        "report_id_type_prefix": doc["report_id"].startswith(doc["report_type"] + "_"),
        "generated_at": doc["generated_at"], "market_data_as_of": doc["market_data_as_of"], "valid_until": doc["valid_until"],
        "market_data_is_last_completed_session_close": m.astimezone(cal.NY).date() == cal.last_session_date(g) and m.astimezone(cal.NY).hour == 16,
        "calendar_state_at_generation": cal.state(g), "report_market_session": doc["market_session"],
        "session_consistent": cal.state(g) == "CLOSED_HOLIDAY" and "CLOSED" in doc["market_session"],
        "valid_until_minus_generated_s": (v - g).total_seconds(), "expired_at_check_time": v <= now,
        "publication_status": doc["publication_status"], "test_only": doc["test_only"], "research_only": doc["research_only"],
        "execution_authorized": doc["execution_authorized"], "candidates": len(doc["candidates"])}
    R["provenance"] = [{"provider": s.get("provider"), "ref": s.get("url") or s.get("reference"),
                        "legion_status": "authorized (reproducible)" if "Robinhood" in (s.get("provider") or "") else
                        "reference document" if s.get("provider") in ("schema", "native", "calendar") else "NOT an authorized Legion source: claims UNVERIFIED"} for s in doc["sources"]]
    with tempfile.TemporaryDirectory() as sd:
        led = SqliteLedger(f"{sd}/ledger.sqlite"); br = PaperBroker(f"{sd}/p.json", f"{sd}/j.jsonl")
        o = Orchestrator(led, br, NoMarket(), None, f"{sd}/dec.jsonl", require_report_evidence=True, variants={"PARABOLIC_MOMENTUM": "PARABOLIC_NATIVE"})
        d1 = o.ingest(Item(name, raw), now); d2 = o.ingest(Item(name, raw), now)
        R["ingestion_1"] = {"schema_valid": d1.schema_valid, "tradeable": d1.tradeable, "reasons": d1.reasons}
        R["ingestion_2"] = {"tradeable": d2.tradeable, "reasons": d2.reasons}
        R["sqlite_attempts"] = [{k: a[k] for k in ("filename", "report_id", "outcome")} for a in led.attempts()]
        R["paper_orders"] = len(br.s["stocks"]) + len(br.s["options"]); R["journal_lines"] = sum(1 for _ in open(f"{sd}/j.jsonl")) if os.path.exists(f"{sd}/j.jsonl") else 0
    R["checked_at"] = now.isoformat()
    json.dump(R, open(out, "w"), indent=2); return R

if __name__ == "__main__":
    r = main(*sys.argv[1:4]); print(json.dumps({k: r[k] for k in ("sha256", "schema_v1_1_errors", "ingestion_1", "ingestion_2", "sqlite_attempts", "paper_orders")}, indent=1))
