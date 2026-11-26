"""Long-running PAPER service: poll Drive every 60 s (exponential backoff on failure), US-calendar aware.
NOT proven operational until installed and run on the target host (see docs/DEPLOYMENT.md)."""
import argparse, json, os, signal, sys, time
from datetime import datetime, timezone, time as dtime
from . import MODE, calendar as cal
from .alerts import Alerts
from .monitor import monitor_positions

class Service:
    def __init__(self, cfg, watcher, orch, broker, market, rh, clock=lambda: datetime.now(timezone.utc), sleep=time.sleep):
        self.cfg, self.w, self.o, self.b, self.m, self.rh, self.clock, self.sleep = cfg, watcher, orch, broker, market, rh, clock, sleep
        self.sd = cfg["state_dir"]; os.makedirs(self.sd, exist_ok=True)
        from .escalation import ClaudeEscalator
        base = Alerts(os.path.join(self.sd, "alerts.jsonl")); ec = cfg.get("claude_escalation", {})
        self.escalator = ClaudeEscalator(self.sd, enabled=bool(ec.get("enabled")), max_per_day=ec.get("max_per_day", 5), model=ec.get("model"))
        MAP = {"MISSING_DAILY_REPORT": "MISSING_DAILY_REPORT", "CONNECTION_LOST": "REPEATED_DATA_FAILURE"}
        def alert(kind, msg=""):
            base(kind, msg)
            if kind in MAP:
                try: self.escalator(MAP[kind], {"alert": kind, "message": str(msg)}, self.clock().date().isoformat())
                except Exception as e: base("ESCALATION_ERROR", f"{type(e).__name__}: {e}")
        self.alert = alert; self.o.alert = self.alert
        self.sp = os.path.join(self.sd, "service_state.json")
        self.st = json.load(open(self.sp)) if os.path.exists(self.sp) else {"fails": 0, "last_ok": None, "daily_dates": [], "missing_alerted": []}
        self.stop = False
    def _save(self):
        tmp = self.sp + ".tmp"; json.dump(self.st, open(tmp, "w")); os.replace(tmp, self.sp)
    def emergency(self): return os.path.exists(os.path.join(self.sd, "EMERGENCY_STOP")) or self.stop
    def stop_requested(self): return os.path.exists(os.path.join(self.sd, "STOP_REQUEST"))

    def tick(self):
        """One iteration. Returns seconds to sleep, or None when the service must exit."""
        if MODE != "PAPER": raise SystemExit("refusing to run outside PAPER mode")
        from .schedule import phase, weekly_deadline_passed
        if self.emergency(): self.alert("EMERGENCY_SHUTDOWN", "stop requested"); return None
        if self.stop_requested():
            os.remove(os.path.join(self.sd, "STOP_REQUEST")); self.alert("GRACEFUL_STOP", "STOP_REQUEST file"); self.exit_code = 0; return None
        now = self.clock(); ny = now.astimezone(cal.NY); state = cal.state(now)
        if cal.is_trading_day(ny.date()): self.b.roll_periods(ny.date().isoformat(), "%d-W%02d" % ny.isocalendar()[:2])
        delay = self.cfg.get("poll_s", 60)
        try:
            for r in self.w.poll_once(now):
                if r.tradeable and r.doc and r.doc["report_type"] == "DAILY":
                    self.st["daily_dates"].append(ny.date().isoformat())
                if r.tradeable and r.doc and r.doc["report_type"] == "WEEKLY":
                    self.st.setdefault("weekly_dates", []).append(ny.date().isoformat())
            if self.st["fails"] >= 3: self.alert("CONNECTION_RESTORED", f"after {self.st['fails']} failures")
            self.st["fails"], self.st["last_ok"] = 0, now.isoformat()
        except Exception as e:
            self.st["fails"] += 1; delay = min(self.cfg.get("poll_s", 60) * 2 ** (self.st["fails"] - 1), 900)
            if "re-authentication required" in str(e).lower() or "401" in str(e): self.alert("AUTH_REQUIRED", str(e)[:200])
            if self.st["fails"] == 3: self.alert("CONNECTION_LOST", f"{type(e).__name__}: {e}")
        d = ny.date().isoformat(); hh, mm = map(int, self.cfg.get("daily_deadline_et", "09:15").split(":"))
        if cal.is_trading_day(ny.date()) and ny.time() >= dtime(hh, mm) and d not in self.st["daily_dates"] and d not in self.st["missing_alerted"]:
            self.alert("MISSING_DAILY_REPORT", f"no tradeable DAILY report admitted by {hh:02d}:{mm:02d} ET on {d}"); self.st["missing_alerted"].append(d)
        ph = phase(now); self.st["phase"] = ph
        wk = ny.date().isoformat()
        if weekly_deadline_passed(now) and wk not in self.st.setdefault("weekly_dates", []) and wk not in self.st.setdefault("weekly_alerted", []):
            self.alert("MISSING_WEEKLY_REPORT", f"no tradeable WEEKLY report by 21:00 ET {wk}"); self.st["weekly_alerted"].append(wk)
        if ph == "POST_CLOSE_RECONCILE" and self.st.get("reconciled") != d:
            try:
                from .reporting import journal, risk_report
                ob = os.path.join(self.sd, "outbox"); os.makedirs(ob, exist_ok=True)
                json.dump(journal(os.path.join(self.sd, "decisions.jsonl"), os.path.join(self.sd, "paper_journal.jsonl")), open(os.path.join(ob, f"PAPER_JOURNAL_{d}.json"), "w"), indent=1)
                json.dump(risk_report(self.b), open(os.path.join(ob, f"RISK_REPORT_{d}.json"), "w"), indent=1)
                self.st["reconciled"] = d
            except Exception as e: self.alert("RECONCILE_ERROR", f"{type(e).__name__}: {e}")
        if state == "OPEN":
            try: monitor_positions(self.b, self.m, self.rh, now, self.alert)
            except Exception as e: self.alert("MONITOR_ERROR", f"{type(e).__name__}: {e}")
        json.dump({"at": now.isoformat(), "state": state, "fails": self.st["fails"], "mode": MODE}, open(os.path.join(self.sd, "heartbeat.json"), "w"))
        self._save(); return delay

    def run(self):
        for s in (signal.SIGINT, signal.SIGTERM): signal.signal(s, lambda *_: setattr(self, "stop", True))
        self.exit_code = 3
        while (d := self.tick()) is not None: self.sleep(d)
        return self.exit_code

def acquire_lock(state_dir):
    """Single-instance lock (O_EXCL file with PID). A stale lock whose PID is gone is reclaimed."""
    p = os.path.join(state_dir, "service.lock")
    for _ in range(2):
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, str(os.getpid()).encode()); os.close(fd); return p
        except FileExistsError:
            try: pid = int(open(p).read().strip() or 0)
            except Exception: pid = 0
            if pid and _alive(pid): return None
            os.remove(p)
    return None
def _alive(pid):
    try: os.kill(pid, 0); return True
    except PermissionError: return True
    except OSError: return False

def setup_logging(state_dir, max_bytes=5_000_000, backups=10):
    """Persistent rotating log at <state_dir>/logs/legion.log (survives restarts/reboots)."""
    import logging
    from logging.handlers import RotatingFileHandler
    os.makedirs(os.path.join(state_dir, "logs"), exist_ok=True)
    h = RotatingFileHandler(os.path.join(state_dir, "logs", "legion.log"), maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger("legion"); root.setLevel(logging.INFO)
    if not any(isinstance(x, RotatingFileHandler) for x in root.handlers): root.addHandler(h)
    return root

def main(argv=None):                        # pragma: no cover - requires host credentials
    from .config import Limits
    from .ledger import Ledger
    from .sources import LocalDirSource, DriveApiSource
    from .engine import Orchestrator
    from .paper import PaperBroker
    from .market import RobinhoodMarket
    from .rh import RobinhoodClient, McpHttpTransport
    from .watcher import Watcher
    ap = argparse.ArgumentParser(); ap.add_argument("--config", required=True); a = ap.parse_args(argv)
    cfg = json.load(open(a.config)); sd = cfg["state_dir"]; os.makedirs(sd, exist_ok=True)
    setup_logging(sd)
    if os.path.exists(os.path.join(sd, "EMERGENCY_STOP")): print("EMERGENCY_STOP present; remove it deliberately to resume"); return 3
    if cfg.get("paper_start_equity") in (None, 0): print("paper_start_equity is not set: the owner must choose it explicitly"); return 4
    lock = acquire_lock(sd)
    if lock is None: print("another Legion service instance is running (state/service.lock)"); return 5
    src = LocalDirSource(cfg["local_dir"], settle_s=5) if cfg["source"] == "local" else DriveApiSource(
        cfg["drive_folder_id"], cfg.get("service_account_file"), cfg.get("oauth_token_file"))
    from .rh import ResilientTransport
    rh = RobinhoodClient(ResilientTransport(McpHttpTransport())); mk = RobinhoodMarket(rh)
    br = PaperBroker(os.path.join(sd, "paper_state.json"), os.path.join(sd, "paper_journal.jsonl"), cfg.get("paper_start_equity", 100000.0))
    from .store import SqliteLedger
    orch = Orchestrator(SqliteLedger(os.path.join(sd, "ledger.sqlite")), br, mk, rh, os.path.join(sd, "decisions.jsonl"), option_kinds=tuple(cfg.get("option_kinds", [])),
                        variants=cfg.get("strategy_variants", {}), require_report_evidence=True,       # production: unsupported PASS labels never count
                        state_dir=sd, fill_slippage=cfg.get("paper_fill_slippage", 0.001))
    return Service(cfg, Watcher(src, orch), orch, br, mk, rh).run()

if __name__ == "__main__": sys.exit(main())
