"""Schema validity (structural) is separate from trading eligibility. Nothing here is brokerage authorization."""
import hashlib, json, os, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "schemas", "legion_signal_v1.schema.json")
SCHEMA = json.load(open(SCHEMA_PATH))
SCHEMA_V11 = json.load(open(os.path.join(os.path.dirname(SCHEMA_PATH), "legion_signal_v1_1.schema.json")))
_V = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
_V11 = Draft202012Validator(SCHEMA_V11, format_checker=FormatChecker())
MANDATORY = ["scanner_rules_version", "generated_at", "market_data_as_of", "valid_until", "market_regime"]
INJECTION = [re.compile(p, re.I) for p in (
    r"ignore (all |any |the )?(previous|prior|above)", r"disregard", r"system prompt", r"you are (now )?(an?|the) ",
    r"\b(place|submit|send|execute)\b.{0,20}\b(order|trade)", r"override", r"</?\s*(system|assistant|tool|user)\b", r"```",
    r"api[_ -]?key|password|bearer|secret", r"live (trading|mode)", r"disable.{0,20}(risk|limit|guard|halt)",
    r"mcp__|place_(equity|option|crypto|advanced)_order", r"increase (the )?(size|risk|limit)")]

def sha256(b): return hashlib.sha256(b).hexdigest()
def _ts(s): return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
def _strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        for k, v in o.items(): yield from _strings(k); yield from _strings(v)
    elif isinstance(o, list):
        for v in o: yield from _strings(v)
def injection_findings(doc): return sorted({p.pattern for s in _strings(doc) for p in INJECTION if p.search(s)})

@dataclass
class CandidateDecision:
    ticker: str; signal_id: str; eligible: bool; reasons: list = field(default_factory=list)
@dataclass
class ReportDecision:
    filename: str; sha256: str; report_id: str | None = None
    schema_valid: bool = False; integrity_ok: bool = False; test_only: bool = False
    tradeable: bool = False; reasons: list = field(default_factory=list)
    candidates: list = field(default_factory=list); doc: dict | None = None
    deferred: bool = False        # looks like a partial sync: retry later, do not ledger/quarantine

def evaluate_candidate(c, now, report_valid_until=None) -> CandidateDecision:
    r, d = [], CandidateDecision(c.get("ticker", "?"), c.get("signal_id", "?"), False)
    if c["signal_classification"] != "BUY_NOW": r.append(f"CLASS_{c['signal_classification']}")
    if c["verification_status"] != "VERIFIED": r.append(f"VERIFICATION_{c['verification_status']}")
    crit = c["individual_criteria_results"]
    if not crit: r.append("NO_CRITERIA_RESULTS")
    r += [f"CRITERION_{x['criterion_id']}_{x['status']}" for x in crit if x["status"] != "PASS"]
    if _ts(c["expiration_timestamp"]) <= now: r.append("SIGNAL_EXPIRED")
    if report_valid_until and _ts(c["expiration_timestamp"]) > _ts(report_valid_until): r.append("SIGNAL_OUTLIVES_REPORT")
    for k in ("proposed_entry", "entry_zone", "technical_invalidation"):
        if c[k] is None: r.append(f"MISSING_{k.upper()}")
    if not c["proposed_price_targets"]: r.append("MISSING_TARGETS")
    if c["missing_data"]: r.append("CANDIDATE_MISSING_DATA")
    z, e, s = c["entry_zone"], c["proposed_entry"], c["technical_invalidation"]
    if z and z["low"] > z["high"]: r.append("BAD_ENTRY_ZONE")
    if z and e is not None and not z["low"] <= e <= z["high"]: r.append("ENTRY_OUTSIDE_ZONE")
    if e is not None and s is not None and (s >= e if c["trade_direction"] == "LONG" else s <= e): r.append("INVALIDATION_ON_WRONG_SIDE")
    if c["volume_confirmation"] is None or not c["volume_confirmation"]["confirmed"]: r.append("VOLUME_NOT_CONFIRMED")
    d.reasons, d.eligible = r, not r
    return d

def evaluate_report(raw: bytes, filename: str, now: datetime, expected_size=None, expected_md5=None,
                    seen_ids=frozenset(), seen_hashes=frozenset(), age_s=1e9, settle_s=120) -> ReportDecision:
    d = ReportDecision(filename, sha256(raw))
    d.integrity_ok = (expected_size is None or expected_size == len(raw)) and \
                     (expected_md5 is None or expected_md5 == hashlib.md5(raw).hexdigest())
    if not d.integrity_ok:
        d.reasons.append("INTEGRITY_MISMATCH"); d.deferred = age_s < settle_s; return d
    try: doc = json.loads(raw.decode("utf-8"))
    except Exception as e:
        d.reasons.append(f"INVALID_JSON {e}"); d.deferred = age_s < settle_s; return d
    v = _V11 if isinstance(doc, dict) and doc.get("schema_version") == "1.1" else _V
    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    d.schema_valid = not errs
    d.reasons += [f"SCHEMA {'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:200] for e in errs[:25]]
    if not d.schema_valid: return d
    d.doc, d.report_id, d.test_only = doc, doc["report_id"], doc["test_only"]
    if filename != f"{d.report_id}.json": d.reasons.append("REPORT_ID_FILENAME_MISMATCH")
    if f"_{doc['report_type']}_" not in f"_{d.report_id}_": d.reasons.append("REPORT_ID_TYPE_MISMATCH")
    if doc["test_only"]: d.reasons.append("TEST_ONLY")
    if doc["test_only"] and doc["candidates"]: d.reasons.append("UNSAFE_TEST_FILE_HAS_CANDIDATES")
    if doc["publication_status"] != "VERIFIED": d.reasons.append(f"INVALID_STATUS {doc['publication_status']}")
    d.reasons += [f"MISSING_MANDATORY {k}" for k in MANDATORY if doc[k] in (None, "")]
    if doc["valid_until"] is None: d.reasons.append("MISSING_EXPIRY")
    elif _ts(doc["valid_until"]) <= now: d.reasons.append(f"EXPIRED valid_until={doc['valid_until']}")
    if d.report_id in seen_ids: d.reasons.append("DUPLICATE_REPORT_ID")
    if d.sha256 in seen_hashes: d.reasons.append("DUPLICATE_CONTENT_HASH")
    ids = [c["signal_id"] for c in doc["candidates"]]
    if len(ids) != len(set(ids)): d.reasons.append("DUPLICATE_SIGNAL_ID_IN_REPORT")
    inj = injection_findings(doc)
    if inj: d.reasons.append(f"PROMPT_INJECTION_SUSPECTED {inj}")
    d.tradeable = not d.reasons
    if d.tradeable:
        d.candidates = [evaluate_candidate(c, now, doc["valid_until"]) for c in doc["candidates"]]
    return d
