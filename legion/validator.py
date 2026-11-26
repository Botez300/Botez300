"""Validation + admission gate. Every rejection reason is collected, not just the first."""
import hashlib, json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from jsonschema import Draft202012Validator, FormatChecker
from .schema import REPORT_SCHEMA, MANDATORY_NON_NULL, VALID_STATUSES

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)

@dataclass
class Result:
    filename: str
    sha256: str
    schema_ok: bool = False
    integrity_ok: bool = False
    safety_ok: bool = False          # no candidates / no execution authority for fixtures; never live
    admitted: bool = False           # may enter the trading pipeline
    report_id: str | None = None
    reasons: list = field(default_factory=list)   # rejection reasons
    notes: list = field(default_factory=list)

def validate(raw: bytes, filename: str, now: datetime | None = None,
             expected_size: int | None = None, seen_ids=frozenset(), seen_hashes=frozenset()) -> Result:
    now = now or datetime.now(timezone.utc)
    r = Result(filename, sha256(raw))
    # integrity
    r.integrity_ok = expected_size is None or expected_size == len(raw)
    if not r.integrity_ok:
        r.reasons.append(f"INTEGRITY_SIZE_MISMATCH expected={expected_size} got={len(raw)}")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as e:
        r.reasons.append(f"INVALID_JSON {e}"); return r
    errs = sorted(Draft202012Validator(REPORT_SCHEMA, format_checker=FormatChecker()).iter_errors(doc),
                  key=lambda e: list(e.path))
    r.schema_ok = not errs
    for e in errs:
        r.reasons.append(f"SCHEMA {'/'.join(map(str, e.path)) or '<root>'}: {e.message}")
    if not isinstance(doc, dict):
        return r
    r.report_id = doc.get("report_id")
    # filename must match report_id
    if r.report_id and filename != f"{r.report_id}.json":
        r.reasons.append(f"REPORT_ID_FILENAME_MISMATCH {filename} vs {r.report_id}")
    if r.report_id and f"_{doc.get('report_type','')}_" not in f"_{r.report_id}_":
        r.reasons.append("REPORT_ID_TYPE_MISMATCH")
    # safety flags
    cands = doc.get("candidates")
    if doc.get("test_only") is True:
        r.reasons.append("TEST_ONLY")
        r.safety_ok = (cands == [] and doc.get("execution_authorized") is False
                       and doc.get("research_only") is True)
        if not r.safety_ok:
            r.reasons.append("UNSAFE_TEST_FILE: must have zero candidates, research_only=true, execution_authorized=false")
    else:
        r.safety_ok = doc.get("execution_authorized") is False
        if doc.get("execution_authorized") is not False:
            r.reasons.append("EXECUTION_AUTHORIZED_NOT_ALLOWED: PAPER mode rejects reports claiming execution authority")
    # mandatory fields / status / expiry
    for k in MANDATORY_NON_NULL:
        if doc.get(k) in (None, ""):
            r.reasons.append(f"MISSING_MANDATORY {k}")
    if doc.get("publication_status") not in VALID_STATUSES:
        r.reasons.append(f"INVALID_STATUS {doc.get('publication_status')}")
    vu = doc.get("valid_until")
    try:
        if vu is None: r.reasons.append("MISSING_EXPIRY")
        elif _ts(vu) <= now: r.reasons.append(f"EXPIRED valid_until={vu}")
    except Exception:
        r.reasons.append("BAD_TIMESTAMP valid_until")
    # duplicates
    if r.report_id in seen_ids: r.reasons.append("DUPLICATE_REPORT_ID")
    if r.sha256 in seen_hashes: r.reasons.append("DUPLICATE_CONTENT_HASH")
    r.admitted = not r.reasons and r.schema_ok and r.safety_ok and r.integrity_ok
    return r
