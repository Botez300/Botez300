"""Stock / options engine adapters. The real engines from the earlier instructions are NOT in this
repo, so these are thin PAPER adapters behind the same boundary: engine.on_report(report)."""
from .market_verify import verify_candidate
class _Base:
    asset = None
    def __init__(self, gateway, quotes): self.gw, self.quotes, self.log = gateway, quotes, []
    def on_report(self, report: dict):
        for c in report["candidates"]:
            if c.get("asset_class", "STOCK") != self.asset: continue
            ok, why = verify_candidate(c, self.quotes)
            self.log.append((c["symbol"], ok, why))
            if ok: self.gw.submit({"symbol": c["symbol"], "asset": self.asset, "report_id": report["report_id"],
                                   "side": c.get("side", "BUY"), "qty": c.get("qty", 1)})
class StockEngine(_Base): asset = "STOCK"
class OptionsEngine(_Base): asset = "OPTION"
