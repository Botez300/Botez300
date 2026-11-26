"""Order gateway. PAPER only: there is deliberately no live-broker code path in this package."""
import json, os
from . import MODE
class LiveTradingForbidden(RuntimeError): pass

class PaperOrderGateway:
    def __init__(self, journal_path):
        if MODE != "PAPER": raise LiveTradingForbidden("MODE must be PAPER")
        self.journal_path, self.orders = journal_path, []
    def submit(self, intent: dict):
        if intent.get("live"): raise LiveTradingForbidden("live orders are not supported")
        rec = {"mode": "PAPER", **intent}
        self.orders.append(rec)
        with open(self.journal_path, "a") as f: f.write(json.dumps(rec) + "\n")
        return rec
