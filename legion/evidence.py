"""Multi-source evidence and provenance. A criterion is VERIFIED only when an AUTHORIZED source, an observation timestamp,
the observed value, the threshold and the methodology are all present, the observation is fresh enough, and independent
authorized sources do not conflict. A bare PASS label is never verification."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

# Registry of research sources. "authorized" ones may be used; "proposed" ones need owner approval before any connection.
SOURCES = {
    "ROBINHOOD_MCP":        {"status": "authorized", "kind": "market_data+brokerage", "note": "exclusive execution integration"},
    "SEC_EDGAR_VIA_ROBINHOOD": {"status": "authorized", "kind": "official_filings", "note": "get_sec_filing_index / get_sec_filing_facts"},
    "SEC_EDGAR_DIRECT":     {"status": "authorized", "kind": "official_filings", "note": "data.sec.gov public API (host only; blocked in build sandbox)"},
    "ISHARES_OFFICIAL_HOLDINGS": {"status": "authorized", "kind": "etf_constituents", "note": "issuer-published IWM holdings file"},
    "GOOGLE_DRIVE_LEGION":  {"status": "authorized", "kind": "report_transport", "note": "Legion folders; carries reports and evidence files"},
    "CHATGPT_LEGION_REPORT": {"status": "authorized", "kind": "claims", "note": "report claims must be independently reproduced; never self-verifying"},
    "TRADINGVIEW_PINE":     {"status": "authorized_unmapped", "kind": "indicator_readings", "note": "authenticated readings usable only once the owner maps exact script_id+version to a platform signal"},
    "ALPHA_VANTAGE":        {"status": "proposed", "kind": "fundamentals/analyst", "note": "connected in Claude session; not approved for Legion"},
    "BIGDATA_COM":          {"status": "proposed", "kind": "news/analyst", "note": "connected in Claude session; not approved for Legion"},
}
class UnauthorizedSource(PermissionError): pass
def require_authorized(source):
    s = SOURCES.get(source)
    if not s or s["status"] not in ("authorized", "authorized_unmapped"): raise UnauthorizedSource(f"research source {source!r} is not authorized")
    return s

@dataclass
class Evidence:
    criterion: str; source: str; observed_at: str; value: object; threshold: object; methodology: str; reference: str | None = None
    def dict(self): return asdict(self)

def _ts(s): return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)

def check(e: Evidence, now, max_age_s):
    """-> (status, reason). status in VERIFIED | UNVERIFIED."""
    try: require_authorized(e.source)
    except UnauthorizedSource as x: return "UNVERIFIED", str(x)
    if SOURCES[e.source]["status"] == "authorized_unmapped": return "UNVERIFIED", "indicator source not mapped to the exact platform signal"
    if SOURCES[e.source]["kind"] == "claims": return "UNVERIFIED", "report claim requires independent reproduction"
    for k in ("observed_at", "value", "threshold", "methodology"):
        if getattr(e, k) in (None, ""): return "UNVERIFIED", f"missing {k}"
    try: t = _ts(e.observed_at)
    except Exception: return "UNVERIFIED", "bad observed_at"
    if t > now: return "UNVERIFIED", "observation in the future"
    if max_age_s is not None and (now - t).total_seconds() > max_age_s: return "UNVERIFIED", f"stale: {(now - t).total_seconds():.0f}s > {max_age_s}s"
    return "VERIFIED", "ok"

def reconcile(evs, now, max_age_s, rel_tol=0.0):
    """Same metric from several sources. Conflicts beyond rel_tol => UNVERIFIED (never pick a winner silently)."""
    ok = [e for e in evs if check(e, now, max_age_s)[0] == "VERIFIED" and isinstance(e.value, (int, float))]
    if not ok: return None, "UNVERIFIED", "no verified observation"
    vals = [float(e.value) for e in ok]; lo, hi = min(vals), max(vals)
    if hi - lo > rel_tol * max(abs(lo), abs(hi), 1e-12):
        return None, "UNVERIFIED", f"CONFLICT {[(e.source, e.value) for e in ok]}"
    return vals[0], "VERIFIED", f"{len(ok)} source(s) agree"

def audit_report_candidate(c, now, max_age_s=None):
    """Classify each report criterion. v1.0 criteria carry no evidence => UNSUPPORTED (a label, not verification)."""
    out = []
    for x in c.get("individual_criteria_results", []):
        if not all(k in x for k in ("source", "observed_at", "value", "threshold", "methodology")):
            out.append({"criterion_id": x["criterion_id"], "claimed": x["status"], "status": "UNVERIFIED", "reason": "UNSUPPORTED_LABEL"}); continue
        e = Evidence(x["criterion_id"], x["source"], x["observed_at"], x["value"], x["threshold"], x["methodology"], x.get("source_reference"))
        st, why = check(e, now, max_age_s)
        out.append({"criterion_id": x["criterion_id"], "claimed": x["status"], "status": st, "reason": why})
    return out
