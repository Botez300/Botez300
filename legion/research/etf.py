"""Official ETF constituents (issuer holdings file). The iShares CSV layout handled here (metadata lines, then a header
row beginning 'Ticker,') is INFERRED and has not been checked against a live download: the build sandbox blocks ishares.com."""
import csv, io, re
from datetime import datetime

ISHARES_IWM_URL = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
class HoldingsFormatError(ValueError): pass

def parse_ishares(text):
    lines = text.lstrip("﻿").splitlines()
    as_of = None
    for l in lines[:15]:
        m = re.search(r'Fund Holdings as of,"?([A-Za-z]{3} \d{1,2}, \d{4})', l)
        if m: as_of = datetime.strptime(m.group(1), "%b %d, %Y").date().isoformat()
    try: h = next(i for i, l in enumerate(lines) if l.startswith("Ticker,"))
    except StopIteration: raise HoldingsFormatError("no 'Ticker,' header row")
    if as_of is None: raise HoldingsFormatError("no 'Fund Holdings as of' date: holdings are not point-in-time")
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[h:]))))
    if not rows or "Asset Class" not in rows[0]: raise HoldingsFormatError("missing Asset Class column")
    eq = sorted({r["Ticker"].strip() for r in rows if (r.get("Asset Class") or "").strip() == "Equity" and r.get("Ticker", "").strip() not in ("", "-")})
    return {"as_of": as_of, "tickers": eq, "rows": len(rows), "source": "ISHARES_OFFICIAL_HOLDINGS"}

def fetch_ishares(url=ISHARES_IWM_URL, opener=None, timeout=30):     # host only; untested in sandbox
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "LegionResearch/1.0"})
    with (opener or urllib.request.urlopen)(req, timeout=timeout) as r: return parse_ishares(r.read().decode("utf-8", "replace"))
