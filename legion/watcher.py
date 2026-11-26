"""Polling watcher (works for Drive sync dirs and the Drive API alike; no inotify dependency)."""
import time
class Watcher:
    def __init__(self, source, pipeline): self.src, self.p, self.seen = source, pipeline, set()
    def poll_once(self, now=None):
        out = []
        for it in self.src.list():
            key = (it.name, it.token)
            if key in self.seen: continue
            self.seen.add(key); out.append(self.p.ingest(it, now))
        return out
    def run(self, interval=30, stop=lambda: False):
        while not stop():
            self.poll_once(); time.sleep(interval)
