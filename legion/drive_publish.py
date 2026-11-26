"""Drive outbox publisher (host only). Least-privilege scope `drive.file`: the app can only see/modify files IT created,
plus folders the owner explicitly opens with it. Each upload is read back and compared (md5Checksum) before it is
marked published; a ledger prevents re-publishing after restarts. UNTESTED against Google (no credentials in the build sandbox)."""
import hashlib, json, os

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDERS = {"PAPER_JOURNAL": "1YQndUh4eorXCmhK6nVvtuD8t-phytMgN", "RISK_REPORT": "1_LuRacmuH-frbZLTO0LQs-973Qub4zm9",
           "PERFORMANCE": "1XsBsJz0iSJhladFonX4B2bG5YckNjRg0", "ALERTS": "1YgAXgS78h9UWAQKavY5Iu2S8u42wty1c",
           "TRADE_PROPOSALS": "1Exr57Khkg_cVPKF08XJR28lzHMPOfCiI"}
class PublishError(RuntimeError): pass

def folder_for(name):
    for k, v in FOLDERS.items():
        if name.startswith(k): return v
    return FOLDERS["PERFORMANCE"]

class OutboxPublisher:
    def __init__(self, service, outbox_dir, ledger_path):
        self.svc, self.dir, self.lp = service, outbox_dir, ledger_path
        self.done = json.load(open(ledger_path)) if os.path.exists(ledger_path) else {}
    def _save(self):
        tmp = self.lp + ".tmp"; json.dump(self.done, open(tmp, "w"), indent=1); os.replace(tmp, self.lp)
    def publish_all(self):
        from googleapiclient.http import MediaInMemoryUpload            # pragma: no cover (real path)
        return self._publish_all(lambda b, mime: MediaInMemoryUpload(b, mimetype=mime, resumable=False))
    def _publish_all(self, media):
        out = []
        for n in sorted(os.listdir(self.dir)):
            p = os.path.join(self.dir, n); b = open(p, "rb").read(); sha = hashlib.sha256(b).hexdigest()
            if self.done.get(n, {}).get("sha256") == sha: continue                          # already published (restart-safe)
            mime = "application/json" if n.endswith(".json") else "text/markdown"
            f = self.svc.files().create(body={"name": n, "parents": [folder_for(n)]}, media_body=media(b, mime), fields="id,md5Checksum,size").execute()
            back = self.svc.files().get_media(fileId=f["id"]).execute()
            if hashlib.md5(back, usedforsecurity=False).hexdigest() != f.get("md5Checksum") or back != b:
                raise PublishError(f"{n}: readback mismatch; not marked published")
            self.done[n] = {"sha256": sha, "file_id": f["id"]}; self._save(); out.append((n, f["id"]))
        return out
