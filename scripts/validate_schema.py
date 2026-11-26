"""CI: the canonical schema is itself valid, the checked-in fixtures are structurally valid, and the legacy
fixtures are not tradeable. Exits non-zero on any failure."""
import glob, json, sys
from datetime import datetime, timezone
from jsonschema import Draft202012Validator
sch = json.load(open("schemas/legion_signal_v1.schema.json")); Draft202012Validator.check_schema(sch)
sys.path.insert(0, ".")
from legion.eligibility import evaluate_report
bad = 0
for f in sorted(glob.glob("fixtures/03_Verified_Signals/*.json")):
    d = evaluate_report(open(f, "rb").read(), f.split("/")[-1], datetime.now(timezone.utc))
    ok = d.schema_valid and not d.tradeable and d.test_only
    print(("OK  " if ok else "FAIL"), f); bad += not ok
for f in glob.glob("specs/*.json"):
    json.load(open(f))
sys.exit(bad)
