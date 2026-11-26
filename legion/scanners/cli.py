"""Run a mechanical scan on the deployment host (needs a working Robinhood transport):
python -m legion.scanners.cli --strategy MINERVINI_VCP_SEPA --tickers tickers.txt --out scan.json
Output is research only. It never creates orders, never writes a scan to Robinhood, and never marks anything BUY_NOW."""
import argparse, json
from datetime import datetime, timezone
from ..rh import RobinhoodClient, McpHttpTransport
from ..strategies import load_spec
from .rh_data import build
from .runner import scan
from .capability import report

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--strategy", required=True); ap.add_argument("--tickers", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(argv); spec = load_spec(a.strategy); now = datetime.now(timezone.utc)
    c = RobinhoodClient(McpHttpTransport()); tickers = [t.strip().upper() for t in open(a.tickers) if t.strip()]
    datas = [build(c, t, now, spec["params"].get("market_index")) for t in tickers]
    out = scan(a.strategy, datas, spec); out["capability_gaps"] = [g for g in report() if g["strategy"] == a.strategy]; out["generated_at"] = now.isoformat()
    json.dump(out, open(a.out, "w"), indent=2, default=str); print(json.dumps(out["counts"]))
if __name__ == "__main__": main()
