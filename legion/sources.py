"""File sources. LocalDirSource = a Google Drive for Desktop sync directory (or any folder).
DriveApiSource = authenticated Drive API v3 adapter (read-only scope); needs credentials, untested here."""
import os
from dataclasses import dataclass

@dataclass
class Item:
    name: str; size: int; read: callable; token: str   # token changes when content changes

class LocalDirSource:
    def __init__(self, path): self.path = path
    def list(self):
        for n in sorted(os.listdir(self.path)):
            p = os.path.join(self.path, n)
            if n.lower().endswith(".json") and os.path.isfile(p):
                st = os.stat(p)
                yield Item(n, st.st_size, lambda p=p: open(p, "rb").read(), f"{st.st_mtime_ns}:{st.st_size}")

class DriveApiSource:
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    def __init__(self, folder_id, credentials_file):
        from google.oauth2 import service_account          # pip install google-api-python-client google-auth
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(credentials_file, scopes=self.SCOPES)
        self.svc, self.folder = build("drive", "v3", credentials=creds), folder_id
    def list(self):
        q = f"'{self.folder}' in parents and trashed=false and mimeType='application/json'"
        for f in self.svc.files().list(q=q, fields="files(id,name,size,md5Checksum,modifiedTime)").execute()["files"]:
            yield Item(f["name"], int(f["size"]),
                       lambda i=f["id"]: self.svc.files().get_media(fileId=i).execute(),
                       f["md5Checksum"])
