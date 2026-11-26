"""File sources. LocalDirSource = a Google Drive for Desktop sync directory (or any folder).
DriveApiSource = authenticated Drive API v3 adapter (read-only scope); needs credentials, untested here."""
import os
from dataclasses import dataclass

@dataclass
class Item:
    name: str; size: int; read: callable; token: str   # token changes when content changes
    age: float = 1e9            # seconds since last modification (partial-sync detection)
    md5: str | None = None

class LocalDirSource:
    """Google Drive for desktop sync folder (or any folder). Skips temp/partial names and files modified < settle_s ago."""
    TEMP = (".tmp", ".crdownload", ".partial", "~")
    def __init__(self, path, settle_s=0): self.path, self.settle = path, settle_s
    def list(self):
        import time
        for n in sorted(os.listdir(self.path)):
            p = os.path.join(self.path, n)
            if not n.lower().endswith(".json") or n.startswith((".", "~$")) or n.endswith(self.TEMP) or not os.path.isfile(p): continue
            st = os.stat(p); age = time.time() - st.st_mtime
            if age < self.settle: continue
            yield Item(n, st.st_size, lambda p=p: open(p, "rb").read(), f"{st.st_mtime_ns}:{st.st_size}", age)

class DriveApiSource:
    """Authenticated Drive API v3, read-only scope. UNTESTED in the build sandbox (no credentials existed).
    Credentials are read from files OUTSIDE the repository: a service-account key (folder must be shared with the
    service account) or an OAuth user token created by `python -m legion.drive_auth`."""
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    def __init__(self, folder_id, credentials_file=None, token_file=None):
        from googleapiclient.discovery import build            # pip install google-api-python-client google-auth google-auth-oauthlib
        if credentials_file:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(credentials_file, scopes=self.SCOPES)
        elif token_file:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
            if not creds.valid: creds.refresh(Request())
        else: raise ValueError("credentials_file or token_file required; none are stored in the repository")
        self.svc, self.folder = build("drive", "v3", credentials=creds, cache_discovery=False), folder_id
    def list(self):
        from datetime import datetime, timezone
        q, tok = f"'{self.folder}' in parents and trashed=false and name contains '.json'", None
        while True:
            r = self.svc.files().list(q=q, pageToken=tok, pageSize=200, fields="nextPageToken,files(id,name,size,md5Checksum,modifiedTime)").execute()
            for f in r["files"]:
                if not f["name"].lower().endswith(".json") or "md5Checksum" not in f: continue
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))).total_seconds()
                yield Item(f["name"], int(f["size"]), lambda i=f["id"]: self.svc.files().get_media(fileId=i).execute(),
                           f["md5Checksum"] + f["modifiedTime"], age, f["md5Checksum"])
            tok = r.get("nextPageToken")
            if not tok: return
